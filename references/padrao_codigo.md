# Padrão de código dos jobs ETL ({{PASTA_PROJETO}})

Este documento é a "fonte da verdade" das convenções observadas nos jobs já migrados
(`{{RAIZ_JOBS}}/{{PASTA_PROJETO}}/{{JOB_REFERENCIA_1}}`, `{{JOB_REFERENCIA_2}}`, `{{JOB_REFERENCIA_3}}`).
Os scripts em `scripts/` geram código seguindo exatamente estas convenções. Leia isto antes de
gerar ou validar qualquer job — é o que garante que o código gerado pareça "escrito por quem já
escreveu os outros", e não um template genérico.

## 1. Árvore de pastas de um job

```
Job_<Nome>/                        <- repositório git próprio
  <NOME_PASTA>/                    <- pasta em CAIXA-ALTA-COM-HIFEN, ex.: {{PASTA_JOB_EXEMPLO_1}}, {{PASTA_JOB_EXEMPLO_2}}
    .gitignore                     <- sempre contém: logs/  __pycache__/  {{PACOTE_CORE_PY}}.egg-info/
    Python_Job_<Nome>.py           <- orquestrador (ver seção 4)
    ORIGEM/                        <- camada STG (extração das origens)
      Load_STG_<TABELA>.py
      Campos/CamposSTG_<TABELA>.json
    DIMENSOES/                     <- camada DM (dimensões, MERGE) — opcional, só se o job tiver dimensões
      Load_DM_<TABELA>.py
      Campos/CamposDM_<TABELA>.json
    FATOS/                         <- camada FT (fatos) — opcional, só se o job tiver fatos
      Load_FT_<TABELA>.py
      Campos/CamposFT_<TABELA>.json
    logs/                          <- log diário, criado em runtime — NUNCA criar manualmente, só está no .gitignore
```

Nem todo job tem as três camadas (ex.: {{NOME_JOB_EXEMPLO_2}} só tem ORIGEM+FATOS, sem DIMENSOES).
Gere apenas as pastas de camadas que a spec realmente define.

## 2. Biblioteca compartilhada `{{BIBLIOTECA_CORE}}`

Todo job importa de um pacote Python instalado (`{{BIBLIOTECA_CORE}}`, em
`{{CAMINHO_BIBLIOTECA}}`), nunca duplica essa lógica:

- `core.configs.ConfigLoader as configs` — carrega credenciais (`configs.carregar_credenciais()`),
  identifica o nome do job pelo arquivo `Python_Job_*.py` na pasta (`configs.get_job_name`), decide o
  ambiente (PROD/HOMOLOG/DEV) por `configs.ambienteAtual`, e descobre/ordena os `Load_*.py` das
  camadas (`configs.recupera_tabelas`).
- `core.connection.DatabaseConfig` / `Connections` — monta a config de conexão a partir de uma
  "seção" do arquivo de credenciais (`secao="{{SECAO_CONEXAO_STAGING}}"`, `"{{SECAO_CONEXAO_DW}}"`, `"{{SECAO_CONEXAO_ORIGEM}}"`, `"{{SECAO_CONEXAO_AUX}}"`, etc.)
- `core.logging.LoggerSetup` — configura o logger do job, gravando em `logs/`.
- `core.send_mail.EmailSender` — envia e-mail de erro (`EmailSender.enviar_email(assunto, mensagem, credenciais['email'])`).
- `core.log_tables.TableLogs` — grava as tabelas de auditoria (`{{TABELA_LOG_ATUALIZACAO}}`, `{{TABELA_LOG_DT}}`).
- `core.api_powerbi.PowerbiRequest as pr` — dispara atualização de dataset do Power BI no fim do job.
- `core.spark_configs.spark_facade.Spark` — a "conexão" de fato usada nos `Load_*.py` (tem `.conectar()`,
  `.read(sql, nome_tabela)`, `.write(df, tabela, modo)`, `.execute(sql)`, `.desconectar()`).

Nunca gere um `Load_*.py` que reimplemente conexão/log/e-mail na mão — sempre via `core.*`.

## 3. Contrato de retorno de `executar_select_e_update()`

Toda função `executar_select_e_update()` em qualquer `Load_*.py` retorna **sempre** esta tupla de 9
posições, nesta ordem, tanto no caminho de sucesso quanto no de erro:

```python
return tabela_origem, validacao, banco_origem, banco_destino, erro, hora_inicio, hora_fim, duracao, count
```

O orquestrador desempacota essa tupla para logar em `TableLogs.{{TABELA_LOG_ATUALIZACAO}}` e decidir se
manda e-mail de erro. Gerar essa assinatura errada quebra silenciosamente o pipeline inteiro —
é o ponto mais importante para a validação estática conferir.

## 4. Orquestrador `Python_Job_<Nome>.py`

Estrutura fixa (função `main()`), com pouquíssimas partes variáveis por job:

- `load_files`: dicionário `{0: [...nomes de tabelas STG...], 1: [...nomes de tabelas DM/FT...]}`.
  As strings são *substrings* do nome do arquivo (ex.: `"STG_VA"` casa com `{{ARQUIVO_EXEMPLO_STG}}`), usadas
  por `core.configs.recupera_tabelas` só para **ordenar** os arquivos descobertos automaticamente nas
  pastas `ORIGEM/DIMENSOES/FATOS` — não é uma lista exaustiva redundante, é a ordem de execução.
- `log` / nome do job: string usada nos logs e no assunto do e-mail de erro.
- Bloco final (`if __name__ == "__main__":`) opcionalmente dispara `pr.update_dataset(...)` para um
  ou mais datasets do Power BI, se a spec indicar `datasets_powerbi`.
- Use a variante com `registrar_log()` (reconexão automática ao banco de auditoria antes de logar) —
  é a versão mais robusta observada (`{{ARQUIVO_ORQUESTRADOR_REFERENCIA}}`), prefira-a como padrão para
  jobs novos.

## 5. `Load_STG_<TABELA>.py` (camada ORIGEM)

- Lê `Campos/CamposSTG_<TABELA>.json` (lista de `{origem, destino, tipo, tamanho}`).
- `OVERRIDES_SELECT`: dict `{destino: "expressão SQL"}` para colunas que não são um simples
  `origem AS destino` (cálculos, `GETDATE()`, `SUBSTRING`, `CASE WHEN`, etc.)
- Monta um `SELECT` dinamicamente a partir de `campos` + `OVERRIDES_SELECT`, lê da origem
  (`conexao_origem.read(sql, tabela)`) e grava na staging com `conexao_destino.write(df, 'STG_X', 'overwrite')`.
- Quando a tabela de origem no Pentaho tinha múltiplos `Table Input` (ex.: tabela + histórico, como
  `{{TABELA_ATUAL_EXEMPLO}}`+`{{TABELA_HISTORICO_EXEMPLO}}`), isso é regra de negócio específica (geralmente um `UNION`/`unionByName`) — o
  gerador **não** tenta inventar essa lógica sozinho; marca como `# TODO-REVISAO` e pede pra
  descrever em prosa na nota de spec.

## 6. `Load_DM_<TABELA>.py` (camada DIMENSOES)

- Mesma leitura de `Campos/CamposDM_<TABELA>.json` e `OVERRIDES_SELECT`.
- Define `COLUNAS_CHAVE` (colunas de match do `MERGE`, tipicamente a chave natural da dimensão) e
  `COLUNAS_AUDITORIA` (`version`, `DT_INCLUSAO_SYSTEM`, `DT_ATUALIZACAO_SYSTEM` — sempre excluídas do
  `UPDATE SET` genérico).
- Monta um `MERGE <TABELA> AS T USING (<select da staging>) AS S ON (<chave>) WHEN MATCHED ... THEN
  UPDATE SET ... WHEN NOT MATCHED THEN INSERT ...`, incrementando `T.version = T.version + 1`.
- `count = conexao_destino.execute(merge_sql)` (não usa `.write()`, porque o MERGE já escreve).

## 7. `Load_FT_<TABELA>.py` (camada FATOS)

- Igual à STG na forma (`SELECT` dinâmico + `OVERRIDES_SELECT`), mas lendo da staging/dimensões e
  gravando no DW (`conexao_destino.write(df, 'FT_X', 'overwrite')`).
- Pode ter pós-processamento de colunas específicas (regex, cast) — isso também é regra de negócio
  específica; o gerador deixa um bloco `# TODO-REVISAO` comentado indicando onde entraria, sem
  inventar transformação.

## 8. `Campos/*.json`

Lista de objetos, sempre com a mesma forma:

```json
[
  { "origem": "VA_ID", "destino": "VA_ID", "tipo": "nvarchar", "tamanho": "-1" },
  { "origem": "", "destino": "DATA_INCLUSAO", "tipo": "datetime" }
]
```

`origem` vazio é válido (campo calculado, sem correspondente na origem — normalmente também está em
`OVERRIDES_SELECT`). `tamanho` é opcional (omitido quando não se aplica, como em `datetime`).

## 9. O que NÃO fazer

- Nunca rodar `git commit`, `git add`, `git push` ou qualquer comando que altere o histórico do
  repositório — os scripts desta skill só escrevem arquivos no disco local. Quem revisa e commita é
  o usuário.
- Nunca gerar/alterar o arquivo de credenciais (`{{ARQUIVO_CREDENCIAIS}}`) nem hardcodar segredos.
- Nunca inventar regra de negócio que não esteja na nota de spec (prosa do usuário) ou extraída
  literalmente do `.ktr` — quando há ambiguidade, gerar o esqueleto com um comentário
  `# TODO-REVISAO: ...` explicando o que falta decidir, em vez de adivinhar.
