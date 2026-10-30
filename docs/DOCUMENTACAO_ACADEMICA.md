# Documentação Acadêmica — Skill `criar-job-etl`

> **Aviso de uso:** este documento tem finalidade exclusivamente acadêmica e descritiva.
> Ele **não faz parte das instruções operacionais da skill**: não é referenciado pelo
> `SKILL.md`, não deve ser carregado pelo agente durante a execução e não deve ser
> anexado como contexto ao usar a skill. As fontes operacionais continuam sendo
> `SKILL.md`, `references/` e `assets/`.

---

## 1. Introdução

A skill `criar-job-etl` é um pacote de instruções e scripts que estende um agente de IA
(Claude) para automatizar a parte mecânica da **migração de jobs ETL do Pentaho Data
Integration (PDI/Kettle) para Python/PySpark**, além da criação e manutenção de jobs
novos dentro de um padrão de código já estabelecido no projeto (o padrão `MIGRACAO`).

O problema que ela endereça é recorrente em projetos de modernização de dados:
centenas de transformações gráficas (`.ktr`) e jobs (`.kjb`) precisam ser reescritos em
código, e a maior parte desse trabalho é repetitiva (mapear colunas, montar `SELECT`,
montar `MERGE`, registrar logs). A parte que exige julgamento humano — a regra de
negócio — fica concentrada em poucos pontos. A skill separa explicitamente essas duas
naturezas de trabalho.

### 1.1 Objetivos

1. Reduzir o tempo de escrita de jobs repetitivos, gerando código a partir de uma
   especificação estruturada.
2. Garantir **consistência**: todo código gerado segue o mesmo padrão dos jobs já
   migrados manualmente.
3. Acelerar a extração de metadados de arquivos Pentaho (`.ktr`).
4. Detectar estaticamente erros de contrato antes da execução em produção.
5. Manter o humano no controle das decisões de negócio e do versionamento.

---

## 2. Conceitos fundamentais

### 2.1 O que é uma skill

Uma skill é uma pasta com um arquivo `SKILL.md` (instruções em linguagem natural com um
cabeçalho YAML de `name` e `description`) e recursos auxiliares. O agente decide usar a
skill com base na `description`; ao ativá-la, lê o `SKILL.md` e, sob demanda, os demais
arquivos. Esse modelo é chamado de *progressive disclosure*: só o necessário entra no
contexto do modelo.

### 2.2 Divisão de responsabilidades: LLM × código determinístico

Uma decisão de projeto central é dividir o trabalho entre:

| Responsável | O que faz | Por quê |
|---|---|---|
| **Modelo (Claude)** | Interpreta prosa da regra de negócio, decide `overrides`, chave de `MERGE`, colunas de update; conversa com o usuário; resume resultados | Tarefas que exigem interpretação semântica |
| **Scripts Python** | Parsing de XML, geração de arquivos, validação estática, alteração incremental | Tarefas que precisam ser reprodutíveis e exatas |

Assim, a geração de código **não é feita pelo modelo "escrevendo Python livre"**, e sim
por templates determinísticos alimentados por uma especificação (`spec.json`) que o
modelo monta. Isso reduz alucinação e garante uniformidade.

### 2.3 Arquitetura em camadas do job gerado

Os jobs seguem uma arquitetura clássica de *data warehouse*:

- **ORIGEM (STG)** — extração das fontes para tabelas de *staging* (`overwrite`).
- **DIMENSOES (DM)** — dimensões atualizadas via `MERGE` (upsert), com versionamento
  (`version`) e colunas de auditoria.
- **FATOS (FT)** — tabelas fato carregadas a partir da staging/dimensões.

Toda conexão, log, e-mail e integração com Power BI vem de uma biblioteca compartilhada,
`etl-core`, que nunca é reimplementada nos jobs.

---

## 3. Estrutura da skill

```
criar-job-etl/
├── SKILL.md                       # Instruções operacionais (ponto de entrada)
├── references/
│   ├── padrao_codigo.md           # Especificação do padrão de código (fonte da verdade)
│   └── spec_exemplo.json          # Exemplo completo de especificação
├── assets/
│   └── Template - Job ETL.md      # Template de nota de spec para o Obsidian
├── scripts/
│   ├── parse_ktr.py               # Extrai metadados de .ktr do Pentaho
│   ├── read_frontmatter.py        # Lê o YAML de uma nota do Obsidian
│   ├── generate_job.py            # Gera o job completo a partir do spec.json
│   ├── apply_change.py            # Alterações incrementais (campo/tabela)
│   └── validate_job.py            # Validação estática do job
└── docs/
    └── DOCUMENTACAO_ACADEMICA.md  # Este documento (não operacional)
```

---

## 4. Fluxo geral de funcionamento

```
         ┌──────────────────┐        ┌──────────────────────┐
         │ .ktr do Pentaho  │        │ Conversa com usuário │
         └────────┬─────────┘        └──────────┬───────────┘
                  │ parse_ktr.py                │
                  ▼                             ▼
         ┌──────────────────────────────────────────────┐
         │   Nota de spec no Obsidian (Markdown + YAML) │  ◄── revisão humana
         └───────────────────────┬──────────────────────┘
                                 │ read_frontmatter.py + interpretação do Claude
                                 ▼
                         ┌───────────────┐
                         │   spec.json   │
                         └───────┬───────┘
                                 │ generate_job.py
                                 ▼
         ┌──────────────────────────────────────────────┐
         │ Árvore do job: orquestrador, Load_*.py,      │
         │ Campos/*.json, .gitignore                    │
         └───────────────────────┬──────────────────────┘
                                 │ validate_job.py
                                 ▼
                 Relatório: problemas bloqueantes,
                 sugestões e TODO-REVISAO → usuário
                                 │
                                 ▼
                  Revisão e commit MANUAIS pelo usuário
```

A **nota de spec no Obsidian** funciona como documento intermediário legível por humanos
e é a fonte da verdade do job. O `spec.json` é sua tradução estruturada para máquina.

---

## 5. Os quatro fluxos de uso

### 5.1 Job novo (sem Pentaho)
1. Criação/preenchimento da nota a partir do template.
2. Leitura do frontmatter e montagem do `spec.json` pelo modelo.
3. Geração do código (`generate_job.py`, opcionalmente com `--dry-run`).
4. Validação (`validate_job.py`).
5. Resumo ao usuário, listando pendências `TODO-REVISAO`.

### 5.2 Migração a partir do Pentaho
1. `parse_ktr.py --markdown` em cada transformação.
2. O rascunho é colado na nota de spec e **revisado pelo usuário**, com atenção a:
   steps não traduzíveis, múltiplas origens e chave de `MERGE` possivelmente incompleta.
3. Segue os passos 2–5 do fluxo anterior.

### 5.3 Melhoria incremental
- `apply_change.py add-field` — adiciona um campo a uma tabela de uma camada.
- `apply_change.py add-table` — adiciona uma tabela nova e a registra no orquestrador.
- Validação sempre ao final.

### 5.4 Apenas validação
- `validate_job.py` sobre um job existente, com tradução dos achados para o usuário.

---

## 6. Descrição dos componentes

### 6.1 `parse_ktr.py` — extração do Pentaho
Um `.ktr` é um XML com `step`s (etapas) e `hop`s (ligações). O script percorre os steps e
aplica um parser específico para os tipos que sabe interpretar:

| Step Pentaho | Informação extraída |
|---|---|
| `TableInput` | SQL e conexão de origem |
| `TableOutput` | Tabela e colunas de destino |
| `SelectValues` | Renomeações de campos (origem → destino) |
| `DimensionLookup` | Tabela, chave natural e colunas de update → sugestão de `MERGE` |

Steps com lógica não traduzível (ex.: `DatabaseJoin`, `Calculator`, `JavaScript`) geram
**avisos** em vez de tradução. Também há aviso quando existem múltiplos `TableInput`
(origens combinadas). Saída em JSON (`--json`) ou Markdown pronto para a nota (`--markdown`).

### 6.2 `read_frontmatter.py`
Lê o cabeçalho YAML da nota do Obsidian (job, conexões, pasta de destino, datasets do
Power BI). Única dependência externa da skill: PyYAML.

### 6.3 `generate_job.py` — geração de código
Recebe o `spec.json` e produz, por template em Python puro (sem Jinja2):
- `.gitignore` padrão;
- para cada tabela: `Campos/Campos<CAMADA>_<TABELA>.json` e `Load_<TABELA>.py`, usando o
  gerador da camada (STG: `SELECT` + `write overwrite`; DM: `MERGE` com `COLUNAS_CHAVE`,
  `COLUNAS_AUDITORIA` e incremento de `version`; FT: `SELECT` + ponto de pós-processamento);
- o orquestrador `Python_Job_<Nome>.py`, com `load_files` (ordem de execução por grupos),
  retry, envio de e-mail de erro, log com reconexão (`registrar_log`) e disparo opcional
  de atualização do Power BI.

Propriedade importante: **idempotência conservadora** — arquivos existentes nunca são
sobrescritos; o resumo informa "criado" ou "já existia — NÃO sobrescrito".

### 6.4 `apply_change.py` — alterações incrementais
- `add-field`: acrescenta o campo ao `Campos/*.json` (se não existir) e, opcionalmente,
  insere uma entrada em `OVERRIDES_SELECT` do `Load_*.py`. Não propaga entre camadas
  (decisão deliberada: propagar exigiria inferir regra de negócio).
- `add-table`: gera os arquivos da nova tabela e a insere no `load_files`.

### 6.5 `validate_job.py` — validação estática
Executa sem acessar banco de dados. Classifica achados em **problemas** (bloqueantes) e
**sugestões**:

| Checagem | O que verifica |
|---|---|
| Sintaxe | `ast.parse` de cada arquivo Python |
| Contrato de retorno | Todo `return` de `executar_select_e_update()` tem as 9 posições |
| `Campos/*.json` | JSON válido, lista de objetos, `destino` preenchido, sem duplicados |
| `MERGE` (DM) | `COLUNAS_CHAVE` não vazio e contido nos campos |
| Overrides | Toda chave de `OVERRIDES_SELECT` existe nos campos |
| Orquestrador | Existe `Python_Job_*.py`; `load_files` × arquivos reais consistentes |
| Pendências | Lista comentários `# TODO-REVISAO` |

---

## 7. O contrato de retorno

O ponto de integração mais crítico do padrão é a tupla devolvida por cada `Load_*.py`:

```python
return tabela_origem, validacao, banco_origem, banco_destino, erro, hora_inicio, hora_fim, duracao, count
```

O orquestrador desempacota essa tupla para auditoria (`tb_log_atualizacao`) e decisão de
alerta. Uma aridade errada quebra o pipeline silenciosamente, por isso é a primeira
verificação do validador e um invariante de todos os geradores.

---

## 8. Princípios de projeto

1. **Humano no circuito (human-in-the-loop):** toda informação extraída automaticamente
   passa por revisão antes de virar código.
2. **Não inventar regra de negócio:** ambiguidades viram `# TODO-REVISAO`, nunca suposições.
3. **Segurança operacional:** a skill nunca executa `git add/commit/push` e nunca lê ou
   altera credenciais; apenas escreve arquivos locais.
4. **Determinismo:** geração e validação por scripts, não por texto livre do modelo.
5. **Não destrutividade:** nada é sobrescrito sem aviso.
6. **Portabilidade:** apenas biblioteca padrão do Python (+ PyYAML); o código gerado evita
   sintaxe exclusiva do Python 3.12+.
7. **Reuso:** toda infraestrutura vem da biblioteca `etl-core`.

---

## 9. Limitações conhecidas

- O parser cobre apenas os tipos de step mais comuns; lógica em `JavaScript`,
  `Calculator`, joins etc. exige reimplementação manual.
- Múltiplas origens (ex.: tabela atual + histórico) não são combinadas automaticamente.
- A chave de `MERGE` sugerida pelo Pentaho pode estar incompleta.
- A validação é estática (baseada em AST e expressões regulares): não garante que o SQL
  execute nem que os dados estejam corretos.
- Alterações de campo não se propagam entre camadas.
- Falsos positivos de sintaxe em jobs antigos que usam recursos do Python 3.12 quando
  validados com versões anteriores.

---

## 10. Considerações finais

A skill exemplifica um padrão de uso de IA generativa em engenharia de dados no qual o
modelo atua como **orquestrador e intérprete**, enquanto ferramentas determinísticas
fazem o trabalho que exige exatidão. O resultado é uma aceleração da migração
Pentaho → Python sem abrir mão de padronização, rastreabilidade e controle humano sobre
regras de negócio e versionamento.
