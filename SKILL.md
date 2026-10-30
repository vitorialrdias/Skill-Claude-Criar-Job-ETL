---
name: <nome-da-skill>
description: '<O que a skill faz e QUANDO usar. Inclua frases que o usuário diria, ex.: "migra esse .ktr", "adiciona um campo no job X". Inclua também o caso de revisar/validar.>'
---

# <Título da skill>

<1 parágrafo: problema que a skill resolve, padrão de código seguido e biblioteca compartilhada usada.>
**Leia `references/padrao_codigo.md` inteiro antes de gerar ou validar qualquer coisa.**

## Regra de segurança (não negociável)

- Nunca executar `git add`, `git commit`, `git push` ou alterar o histórico do repositório.
- Nunca ler/editar arquivos de credenciais nem colocar segredos no código.
- Só escrever arquivos locais e, no final, apresentar um resumo do que foi criado/alterado.

## Fluxos

### 1. Criar do zero
1. Preencher a nota de spec a partir de `assets/Template - Spec.md` (ou montar com o usuário e confirmar).
2. Ler o frontmatter: `python scripts/read_frontmatter.py <nota.md>`; montar o `spec.json`
   (formato em `references/padrao_codigo.md` e `references/spec_exemplo.json`).
3. Gerar: `python scripts/generate_job.py <spec.json> --out-dir <destino> [--dry-run]`.
4. Validar: `python scripts/validate_job.py <destino>`.
5. Resumir: arquivos criados, `TODO-REVISAO` pendentes, nada commitado.

### 2. Migrar a partir da ferramenta legada
1. `python scripts/parse_<origem>.py <arquivo> --markdown`.
2. Colar o rascunho na nota de spec; **o usuário revisa** (lógica não traduzida, múltiplas origens, chaves).
3. Seguir os passos 2–5 do fluxo 1.

### 3. Alteração incremental
- `python scripts/apply_change.py add-field <job> <CAMADA> <TABELA> --destino X [...]`
- `python scripts/apply_change.py add-table <job> <tabela.json>`
- Validar sempre ao final.

### 4. Só validar
`python scripts/validate_job.py <job>` → bloqueantes primeiro, depois sugestões e `TODO-REVISAO`.

## Onde as coisas ficam
- `references/padrao_codigo.md` — convenção de código (fonte da verdade).
- `references/spec_exemplo.json` — exemplo de spec.
- `assets/Template - Spec.md` — template da nota de spec.
- `scripts/` — parser, leitor de frontmatter, gerador, alteração incremental e validador.

> A pasta `docs/` é só de documentação para leitura humana e **não** deve ser carregada durante o uso da skill.
