---
job: NomeDoJob
tipo: migracao          # migracao | novo
status: rascunho        # rascunho | em_revisao | aprovado | em_producao
log_name: NomeDoJob
projeto: <Projeto>
origem_legada: ""
pasta_destino: ""
conexoes:
  origem: <secao>
  staging: <secao>
  dw: <secao>
datasets_powerbi:
  workspace: ""
  datasets: []
---

# Job: NomeDoJob

## Contexto / objetivo
<!-- O que o job faz e quem consome -->

## Tabelas

### STG_EXEMPLO
- **Camada:** ORIGEM
- **Grupo de execução:** 0
- **Tabela de origem:** 
- **Filtro (WHERE):** 
- **Regra de negócio:** 
- **Overrides:** `DESTINO` = `EXPRESSAO SQL`
- **Rascunho da ferramenta legada:** 

### DM_EXEMPLO
- **Camada:** DIMENSOES
- **Chave natural (MERGE):** 
- **Colunas de update:** 
- **Regra de negócio:** 

## Pendências / dúvidas
<!-- O agente não inventa respostas: vira # TODO-REVISAO -->
