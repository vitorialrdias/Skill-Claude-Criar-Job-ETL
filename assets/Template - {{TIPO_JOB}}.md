---
job: NomeDoJob
tipo: migracao_pentaho        # migracao_pentaho | novo_python
status: rascunho               # rascunho | em_revisao | aprovado | em_producao
log_name: NomeDoJob
projeto: {{PROJETO}}
pentaho_origem: "PENTAHO/NOME_PASTA/Pentaho_MainJob_Nome.kjb"   # deixe vazio se tipo = novo_python
pasta_destino: "{{RAIZ_JOBS}}/{{PASTA_PROJETO}}/Job_NomeDoJob/NOME_PASTA"
conexoes:
  origem: {{SECAO_CONEXAO_ORIGEM}}
  staging: {{SECAO_CONEXAO_STAGING}}
  dw: {{SECAO_CONEXAO_DW}}
  aux: {{SECAO_CONEXAO_AUX}}
datasets_powerbi:
  workspace: ""
  datasets: []
---

# Job: NomeDoJob

> Preencha esta nota ANTES de pedir para o agente gerar/atualizar o código. O agente usa o
> frontmatter acima (conexões, pastas, datasets) e as seções de tabela abaixo como fonte da
> verdade. O `Campos/*.json` de cada tabela é **gerado automaticamente** — você não precisa (e não
> deve) escrever o JSON de campos na mão aqui; descreva a regra de negócio em prosa e, se for uma
> migração do Pentaho, deixe o agente extrair o mapeamento do `.ktr` primeiro.

## Contexto / objetivo

<!-- Prosa livre: o que esse job faz, por que existe, quem consome o resultado (ex.: qual dataset/relatório do Power BI). -->

## Tabelas

Repita esta seção para cada tabela do job. `## <NOME_TABELA>` deve começar com o prefixo da
camada: `STG_`, `DM_` ou `FT_`.

### STG_EXEMPLO

- **Camada:** ORIGEM
- **Grupo de execução:** 0
- **Tabela de origem (SQL):** dbo.TABELA_ORIGEM
- **Conexão de origem:** (herda de `conexoes.origem` se omitido)
- **Filtro (WHERE):** D_E_L_E_T_ = ''
- **Regra de negócio:** <!-- prosa: o que essa extração faz, por que, casos especiais -->
- **Campos com fórmula/override (opcional):** liste só os que NÃO são um simples `origem -> destino`
  - `NOME_DESTINO` = `EXPRESSAO SQL`
- **Rascunho do Pentaho:** <!-- cole aqui o resultado de `parse_ktr.py <arquivo>.ktr --markdown`, se for migração -->

### DM_EXEMPLO

- **Camada:** DIMENSOES
- **Grupo de execução:** 1
- **Tabela de origem (SQL):** STG_EXEMPLO
- **Chave natural (MERGE):** COD_EXEMPLO
- **Colunas de update (MERGE):** <!-- se omitido, o agente assume todas as colunas exceto chave/auditoria -->
- **Regra de negócio:** <!-- prosa -->
- **Campos com fórmula/override (opcional):**
  - `NOME_DESTINO` = `EXPRESSAO SQL`

### FT_EXEMPLO

- **Camada:** FATOS
- **Grupo de execução:** 1
- **Tabela de origem (SQL):** STG_EXEMPLO
- **Regra de negócio:** <!-- prosa -->
- **Pós-processamento (opcional):** <!-- ex.: colunas que precisam de cast/regex específico -->
- **Campos com fórmula/override (opcional):**
  - `NOME_DESTINO` = `EXPRESSAO SQL`

## Pendências / dúvidas

<!-- Qualquer coisa que ainda não está decidida. O agente NÃO deve inventar a resposta — ele deixa
um comentário `# TODO-REVISAO` no código gerado apontando pra cá. -->
