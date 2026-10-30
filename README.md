# Template de skill — gerador de jobs ETL

Modelo genérico baseado na skill `criar-job-etl`, para leitores do projeto que queiram
entender ou replicar a abordagem. Não contém dados, credenciais nem IDs reais.

## Como usar
1. Copie esta pasta e renomeie (o nome da pasta = `name` do `SKILL.md`).
2. Preencha os `<...>` em `SKILL.md`, `references/` e `assets/`.
3. Implemente os scripts em `scripts/` (há só esqueletos).
4. Documentação conceitual: `docs/DOCUMENTACAO_ACADEMICA.md` (somente leitura, não usada pela skill).

## Estrutura
| Pasta | Papel | Usada pelo agente? |
|---|---|---|
| `SKILL.md` | Instruções e gatilho | Sim |
| `references/` | Padrão de código e exemplo de spec | Sim, sob demanda |
| `assets/` | Template da nota de spec | Sim |
| `scripts/` | Ferramentas determinísticas | Sim |
| `docs/` | Documentação acadêmica | **Não** |
