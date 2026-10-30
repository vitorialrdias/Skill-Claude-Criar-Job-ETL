# Skill `{{NOME_SKILL}}`

Skill de agente (Claude) que **gera, migra, altera e valida jobs ETL Python/PySpark** no padrão
`{{PASTA_PROJETO}}` (camadas `ORIGEM` / `DIMENSOES` / `FATOS` + biblioteca `{{BIBLIOTECA_CORE}}`),
a partir de uma **nota de spec no Obsidian** e/ou de um **`.ktr`/`.kjb` do Pentaho** original.

> Este repositório é um **template**: os nomes específicos do projeto estão como variáveis
> `{{...}}`. Veja [`VARIAVEIS.md`](VARIAVEIS.md) para a lista completa e a seção
> [Como adaptar](#13-como-adaptar-este-template) abaixo.

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Quando a skill é acionada](#2-quando-a-skill-é-acionada)
3. [Estrutura de arquivos](#3-estrutura-de-arquivos)
4. [Instalação e requisitos](#4-instalação-e-requisitos)
5. [Arquitetura do job gerado](#5-arquitetura-do-job-gerado)
6. [Fluxos de uso](#6-fluxos-de-uso)
7. [Scripts — referência completa](#7-scripts--referência-completa)
8. [Formato do `spec.json`](#8-formato-do-specjson)
9. [Nota de spec no Obsidian](#9-nota-de-spec-no-obsidian)
10. [Contrato de retorno](#10-contrato-de-retorno)
11. [Regras de segurança](#11-regras-de-segurança)
12. [Limitações conhecidas](#12-limitações-conhecidas)
13. [Como adaptar este template](#13-como-adaptar-este-template)
14. [Perguntas frequentes](#14-perguntas-frequentes)

---

## 1. Visão geral

Migrar jobs do Pentaho para Python é, em grande parte, trabalho repetitivo: mapear colunas,
montar `SELECT`, montar `MERGE`, registrar log, enviar alerta. A regra de negócio, que exige
julgamento humano, fica concentrada em poucos pontos. A skill separa as duas coisas:

| Quem | Faz o quê |
|---|---|
| **Claude** | Lê a nota de spec, interpreta a regra de negócio em prosa, monta o `spec.json` (overrides, chave de MERGE, colunas de update), conversa com o usuário e resume o resultado |
| **Scripts Python** | Parsing do `.ktr`, geração de código por template, alteração incremental e validação estática — tudo determinístico e reprodutível |
| **Usuário** | Revisa a spec, decide regras ambíguas, revisa o código e faz o commit |

Resultado: código sempre no mesmo padrão dos jobs já migrados (`{{JOB_REFERENCIA_1}}`,
`{{JOB_REFERENCIA_2}}`, `{{JOB_REFERENCIA_3}}`), sem regra de negócio inventada.

## 2. Quando a skill é acionada

O agente usa a skill quando o pedido envolve:

- criar um job ETL novo ("preciso subir a tabela X pro DW");
- migrar um job do Pentaho ("migra esse .ktr", "gera o Python a partir do Pentaho");
- adicionar campo ou tabela a um job existente ("adiciona esse campo no job de {{NOME_JOB_EXEMPLO_1}}");
- revisar/validar um job já escrito no padrão.

O gatilho é definido no campo `description` do frontmatter de `SKILL.md`.

## 3. Estrutura de arquivos

```
{{NOME_SKILL}}/
├── SKILL.md                         # Instruções para o agente (ponto de entrada)
├── README.md                        # Este arquivo (para humanos)
├── VARIAVEIS.md                     # Legenda das variáveis do template
├── references/
│   ├── padrao_codigo.md             # Convenção de código — fonte da verdade
│   └── spec_exemplo.json            # spec.json completo de exemplo (STG + DM)
├── assets/
│   └── Template - {{TIPO_JOB}}.md   # Template da nota de spec para o Obsidian
├── scripts/
│   ├── parse_ktr.py                 # .ktr do Pentaho → rascunho de spec
│   ├── read_frontmatter.py          # Lê o YAML da nota do Obsidian
│   ├── generate_job.py              # spec.json → árvore completa do job
│   ├── apply_change.py              # Campo novo / tabela nova em job existente
│   └── validate_job.py              # Validação estática + sugestões
└── docs/
    └── DOCUMENTACAO_ACADEMICA.md    # Documentação conceitual (NÃO usada pela skill)
```

| Pasta | Lida pelo agente? | Observação |
|---|---|---|
| `SKILL.md` | Sim, sempre | Carregado quando a skill é ativada |
| `references/` | Sim, sob demanda | `padrao_codigo.md` deve ser lido antes de gerar/validar |
| `assets/` | Sim | Copiado para o vault do Obsidian |
| `scripts/` | Executados | Não precisam ser lidos para serem usados |
| `README.md`, `VARIAVEIS.md`, `docs/` | **Não** | Apenas para leitores humanos |

## 4. Instalação e requisitos

1. Copie a pasta `{{NOME_SKILL}}/` para o local de skills do seu ambiente (plugin, projeto ou
   configurações de skills da conta).
2. Requisitos para os scripts:
   - Python 3 (o código **gerado** evita sintaxe exclusiva de 3.12+);
   - apenas biblioteca padrão, exceto `read_frontmatter.py`, que usa **PyYAML**:
     `pip install pyyaml --break-system-packages`.
3. Requisitos para o **job gerado** rodar:
   - pacote `{{BIBLIOTECA_CORE}}` instalado (em `{{CAMINHO_BIBLIOTECA}}`);
   - arquivo `{{ARQUIVO_CREDENCIAIS}}` com as seções de conexão
     (`{{SECAO_CONEXAO_ORIGEM}}`, `{{SECAO_CONEXAO_STAGING}}`, `{{SECAO_CONEXAO_DW}}`,
     `{{SECAO_CONEXAO_AUX}}`).

Nenhum script acessa banco de dados.

## 5. Arquitetura do job gerado

```
Job_<Nome>/<NOME_PASTA>/
├── .gitignore                         # logs/  __pycache__/  {{PACOTE_CORE_PY}}.egg-info/
├── Python_Job_<Nome>.py               # Orquestrador
├── ORIGEM/                            # STG — extração (overwrite)
│   ├── Load_STG_<TABELA>.py
│   └── Campos/CamposSTG_<TABELA>.json
├── DIMENSOES/                         # DM — MERGE com versionamento (opcional)
│   ├── Load_DM_<TABELA>.py
│   └── Campos/CamposDM_<TABELA>.json
├── FATOS/                             # FT — fatos (opcional)
│   ├── Load_FT_<TABELA>.py
│   └── Campos/CamposFT_<TABELA>.json
└── logs/                              # criado em runtime, nunca manualmente
```

**Camadas**

| Camada | Prefixo | O que o `Load_*.py` faz |
|---|---|---|
| ORIGEM | `STG_` | Monta `SELECT` a partir de `Campos/*.json` + `OVERRIDES_SELECT`, lê da origem e grava em staging com `write(..., 'overwrite')` |
| DIMENSOES | `DM_` | Monta `MERGE ... AS T USING (...) AS S ON (COLUNAS_CHAVE)`, atualiza só colunas fora de `COLUNAS_AUDITORIA`, incrementa `version`, executa com `execute()` |
| FATOS | `FT_` | Igual à STG, lendo da staging/dimensões e gravando no DW; tem ponto marcado para pós-processamento |

**Orquestrador (`Python_Job_<Nome>.py`)**

- `load_files = {0: [...], 1: [...]}` — define a **ordem** de execução por grupos (as strings
  são substrings do nome do arquivo, ex.: `"STG_X"` → `Load_STG_X.py`);
- carrega cada `Load_*.py` dinamicamente, executa com retry e envia e-mail em caso de erro;
- grava auditoria em `{{TABELA_LOG_ATUALIZACAO}}` / `{{TABELA_LOG_DT}}` via `registrar_log()`
  (reconecta se a conexão cair);
- opcionalmente atualiza datasets do Power BI ao final (`datasets_powerbi`).

**Biblioteca `{{BIBLIOTECA_CORE}}`** — toda infraestrutura vem dela, nunca é reimplementada:

| Módulo | Uso |
|---|---|
| `core.configs.ConfigLoader` | credenciais, nome do job, ambiente (PROD/HOMOLOG/DEV), descoberta e ordenação dos `Load_*.py` |
| `core.connection` | configuração de conexão por seção |
| `core.logging.LoggerSetup` | log diário em `logs/` |
| `core.send_mail.EmailSender` | e-mail de erro |
| `core.log_tables.TableLogs` | tabelas de auditoria |
| `core.api_powerbi.PowerbiRequest` | atualização de datasets |
| `core.spark_configs.spark_facade.Spark` | `conectar`, `read`, `write`, `execute`, `desconectar` |

## 6. Fluxos de uso

### 6.1 Job novo (sem Pentaho)

1. Copiar `assets/Template - {{TIPO_JOB}}.md` para o vault e preencher (ou o agente preenche a
   partir da conversa e pede confirmação).
2. `python scripts/read_frontmatter.py <nota.md>` → o agente lê também as seções `## <TABELA>`
   e monta o `spec.json`.
3. `python scripts/generate_job.py <spec.json> --out-dir <pasta_destino> [--dry-run]`.
4. `python scripts/validate_job.py <pasta_destino>` — corrigir bloqueantes.
5. Resumo: arquivos criados, `# TODO-REVISAO` pendentes, lembrete de que nada foi commitado.

### 6.2 Migração do Pentaho

1. `python scripts/parse_ktr.py <arquivo.ktr> --markdown` para cada transformação
   (`Load_STG_X.ktr`, `Load_DM_X.ktr`, … em `PENTAHO/<NOME>/{STG,DW,ODS}`).
2. Colar o rascunho na nota de spec e **revisar com o usuário**:
   - steps não traduzidos (`DatabaseJoin`, `Calculator`, `JavaScript`…);
   - múltiplas origens (ex.: `{{TABELA_ATUAL_EXEMPLO}}` + `{{TABELA_HISTORICO_EXEMPLO}}`) — a
     forma de combinar é decisão do usuário;
   - chave de MERGE sugerida pode estar incompleta — sempre confirmar.
3. Seguir os passos 2–5 do fluxo 6.1.

### 6.3 Melhoria incremental

```bash
# Novo campo (rodar uma vez por camada em que o campo precisa existir)
python scripts/apply_change.py add-field <pasta_job> <CAMADA> <TABELA> \
       --destino X --origem Y [--tipo T] [--tamanho N] [--override "SQL"]

# Nova tabela em job existente
python scripts/apply_change.py add-table <pasta_job> <tabela.json>
```

Sempre rodar `validate_job.py` depois.

### 6.4 Só validar

`python scripts/validate_job.py <pasta_job>` → o agente apresenta bloqueantes, depois
sugestões, depois a lista de `TODO-REVISAO`.

## 7. Scripts — referência completa

### `parse_ktr.py`

```
python scripts/parse_ktr.py <arquivo.ktr> [--json | --markdown]
```

Lê o XML do `.ktr` e interpreta:

| Step | Extrai |
|---|---|
| `TableInput` | SQL e conexão de origem |
| `TableOutput` | tabela e colunas de destino |
| `SelectValues` | renomeações origem → destino |
| `DimensionLookup` | tabela, chave natural e colunas de update → `merge_sugerido` |

Saída: steps encontrados, campos sugeridos, sugestão de MERGE e **avisos** (steps não
traduzíveis, steps desconhecidos, múltiplos `TableInput`, múltiplos `DimensionLookup`).

### `read_frontmatter.py`

```
python scripts/read_frontmatter.py <nota.md>
```

Imprime em JSON o frontmatter YAML (job, conexões, pasta_destino, datasets_powerbi).

### `generate_job.py`

```
python scripts/generate_job.py <spec.json> [--out-dir CAMINHO] [--dry-run]
```

Gera `.gitignore`, `Campos/*.json` e `Load_*.py` de cada tabela, e o orquestrador.
**Nunca sobrescreve**: arquivos existentes aparecem no resumo como "já existia — NÃO
sobrescrito". `--dry-run` mostra a lista sem escrever.

### `apply_change.py`

| Subcomando | Efeito |
|---|---|
| `add-field <job> <CAMADA> <TABELA> --destino ...` | Acrescenta o campo ao `Campos/*.json` (se ainda não existir) e, com `--override`, uma entrada em `OVERRIDES_SELECT`. Não propaga para outras camadas |
| `add-table <job> <tabela.json>` | Cria `Load_*.py` + `Campos/*.json` e insere a tabela em `load_files`. O JSON tem o formato `{"tabela": {...}, "spec_contexto": {...}}` |

### `validate_job.py`

```
python scripts/validate_job.py <pasta_job> [--json]
```

| Checagem | Tipo |
|---|---|
| Sintaxe Python (`ast.parse`) | Bloqueante |
| `return` com as 9 posições do contrato | Bloqueante |
| `Campos/*.json`: JSON válido, lista, `destino` preenchido, sem duplicados | Bloqueante |
| `COLUNAS_CHAVE` não vazio e presente nos campos | Bloqueante |
| Chaves de `OVERRIDES_SELECT` presentes nos campos | Bloqueante |
| `Python_Job_*.py` existe; `load_files` aponta para arquivos reais | Bloqueante |
| `Load_*.py` fora de `load_files` (não seria executado) | Sugestão |
| Campo sem chave `origem` | Sugestão |
| Comentários `# TODO-REVISAO` | Sugestão |

> Jobs antigos como `{{ARQUIVO_EXEMPLO_STG}}` / `{{ARQUIVO_EXEMPLO_FT}}` usam f-strings do
> Python 3.12+. Validar com Python < 3.12 gera falso positivo de sintaxe.

## 8. Formato do `spec.json`

Exemplo completo em `references/spec_exemplo.json`.

**Nível do job**

| Chave | Descrição |
|---|---|
| `job` | Nome do job (gera `Python_Job_<job>.py`) |
| `log_name` | Nome usado em logs e assunto de e-mail |
| `projeto` | Projeto/área (padrão `{{PROJETO}}`) |
| `pasta_destino` | Ex.: `{{RAIZ_JOBS}}/{{PASTA_PROJETO}}/Job_X/X` |
| `conexoes` | `origem`, `staging`, `dw`, `aux` — seções de `{{ARQUIVO_CREDENCIAIS}}` |
| `datasets_powerbi` | `workspace` + lista de `{nome, id}` (opcional) |
| `tabelas` | Lista de tabelas (abaixo) |

**Nível da tabela**

| Chave | Camadas | Descrição |
|---|---|---|
| `nome` | todas | `STG_X`, `DM_X` ou `FT_X` |
| `camada` | todas | `ORIGEM`, `DIMENSOES` ou `FATOS` |
| `grupo` | todas | Índice em `load_files` (ordem de execução) |
| `tabela_sql_origem` | todas | Tabela/view de leitura |
| `where` | opcional | Filtro do `SELECT` |
| `regra_negocio` | todas | Prosa — vira comentário no código |
| `overrides` | opcional | `{destino: "expressão SQL"}` |
| `chave_merge` | DM | Colunas do `ON` do MERGE |
| `colunas_update_merge` | DM | Colunas atualizadas (padrão: todas exceto chave/auditoria) |
| `campos` | todas | Lista `{origem, destino, tipo, tamanho?}`; `origem` vazio = campo calculado |

Colunas de auditoria padrão nas DM: `version`, `DT_INCLUSAO_SYSTEM`, `DT_ATUALIZACAO_SYSTEM`.

## 9. Nota de spec no Obsidian

O template `assets/Template - {{TIPO_JOB}}.md` é a **fonte da verdade** do job:

- **frontmatter**: `job`, `tipo` (`migracao_pentaho` | `novo_python`), `status`
  (`rascunho` → `em_revisao` → `aprovado` → `em_producao`), `log_name`, `projeto`,
  `pentaho_origem`, `pasta_destino`, `conexoes`, `datasets_powerbi`;
- **Contexto / objetivo**: prosa livre;
- **Tabelas**: uma seção `### <PREFIXO>_<TABELA>` por tabela, com camada, grupo, origem, filtro,
  chave/colunas de MERGE, regra de negócio, overrides e rascunho do Pentaho;
- **Pendências / dúvidas**: tudo que não está decidido vira `# TODO-REVISAO` no código.

O `Campos/*.json` **não** é escrito na nota; é gerado automaticamente.

## 10. Contrato de retorno

Toda `executar_select_e_update()` retorna, no sucesso e no erro:

```python
return tabela_origem, validacao, banco_origem, banco_destino, erro, hora_inicio, hora_fim, duracao, count
```

O orquestrador desempacota essa tupla para auditoria e alerta. Aridade errada quebra o pipeline
silenciosamente — é a primeira coisa que o validador confere.

## 11. Regras de segurança

- A skill **nunca** executa `git add`, `git commit`, `git push` ou qualquer comando que altere o
  histórico. Revisão e commit são sempre manuais.
- **Nunca** lê, gera ou altera `{{ARQUIVO_CREDENCIAIS}}` nem coloca segredos no código.
- **Nunca** inventa regra de negócio: ambiguidades viram `# TODO-REVISAO`.
- **Nunca** sobrescreve arquivos existentes sem avisar.

## 12. Limitações conhecidas

- O parser cobre só `TableInput`, `TableOutput`, `SelectValues` e `DimensionLookup`.
- Múltiplas origens não são combinadas automaticamente.
- Chave de MERGE vinda do Pentaho pode estar incompleta.
- Validação é estática (AST + regex): não garante que o SQL execute nem que os dados estejam
  corretos.
- `add-field` não propaga entre camadas.
- Lógica de pós-processamento em FATOS fica como `# TODO-REVISAO`.

## 13. Como adaptar este template

1. Abra [`VARIAVEIS.md`](VARIAVEIS.md) e defina o valor de cada `{{VARIAVEL}}`.
2. Faça localizar/substituir em **toda** a pasta (inclusive `scripts/`; ex.: no VS Code,
   *Replace in Files*; ou `sed -i 's/{{PASTA_PROJETO}}/MEU_PROJETO/g' $(grep -rl '{{' .)`).
3. Renomeie o arquivo `assets/Template - {{TIPO_JOB}}.md` e a pasta para `{{NOME_SKILL}}`.
4. Confira que não sobrou nada: `grep -rn '{{' . --exclude=README.md --exclude=VARIAVEIS.md`.
5. Ajuste `references/padrao_codigo.md` se o seu padrão diferir (é a fonte da verdade).
6. Teste: gere o exemplo com `--dry-run` e rode `validate_job.py`.

## 14. Perguntas frequentes

**A skill pode commitar para mim?** Não, por design.

**Posso regenerar um job existente?** O gerador não sobrescreve. Gere em outra pasta e compare
(diff) manualmente.

**Preciso escrever o `Campos/*.json`?** Não; ele vem do `spec.json`.

**O `docs/` é carregado pela skill?** Não; é só documentação para humanos.

**O validador acusou erro de sintaxe num job antigo.** Verifique a versão do Python (ver seção 7).