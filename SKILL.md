---
name: {{NOME_SKILL}}
description: 'Gera, migra e mantém jobs ETL Python/PySpark no padrão {{PASTA_PROJETO}} (ORIGEM/DIMENSOES/FATOS + {{BIBLIOTECA_CORE}}) usado neste projeto de migração de Pentaho para Python, a partir de uma nota de spec do Obsidian e/ou de um .ktr/.kjb do Pentaho original. Use esta skill sempre que o usuário pedir para criar um job ETL novo, migrar um job do Pentaho, adicionar uma tabela ou um campo a um job já existente na pasta {{PASTA_PROJETO}}, ou pedir para "gerar o Python a partir do Pentaho" — mesmo que ele não use essas palavras exatas (ex.: "preciso subir a tabela X pro DW", "adiciona esse campo no job de {{NOME_JOB_EXEMPLO_1}}", "migra esse .ktr"). Também use para revisar/validar um job já escrito nesse padrão e sugerir melhorias.'
---

# Criar Job ETL (padrão {{PASTA_PROJETO}})

Esta skill automatiza a parte mecânica de criar e manter jobs ETL que seguem o padrão
observado nos jobs já migrados do Pentaho para Python (`{{RAIZ_JOBS}}/{{PASTA_PROJETO}}/Job_*`): uma
árvore de pastas fixa (`ORIGEM/DIMENSOES/FATOS`), tudo importando da biblioteca
compartilhada `{{BIBLIOTECA_CORE}}`, e um contrato de retorno rígido entre cada `Load_*.py` e o
orquestrador. **Leia `references/padrao_codigo.md` inteiro antes de gerar ou validar
qualquer coisa** — é a especificação exata do que o código gerado precisa parecer.

## Regra de segurança (não negociável)

Esta skill **nunca** executa `git add`, `git commit`, `git push` ou qualquer comando que
altere o histórico do repositório, e nunca lê/edita o arquivo de credenciais. Ela só
escreve arquivos `.py`/`.json` no disco local. No final de qualquer geração ou alteração,
apresente ao usuário um resumo detalhado do que foi criado/alterado (a saída dos scripts já
faz isso) e deixe claro que a revisão e o commit são manuais. Se o usuário pedir para
commitar, explique que essa skill foi desenhada de propósito para não fazer isso.

## Quando usar cada fluxo

### 1. Job novo (sem Pentaho de origem)

O usuário quer um job Python novo, sem migração. Passos:

1. Se ainda não existe uma nota de spec no Obsidian para esse job, copie
   `assets/Template - Job ETL.md` para o vault (pergunte o caminho certo, geralmente ao
   lado dos outros jobs de `{{PASTA_PROJETO}}`) e peça para o usuário preencher — ou, se ele já te
   deu as informações na conversa (conexões, tabelas, regra de negócio), preencha você
   mesmo e mostre pra ele confirmar antes de gerar código.
2. Leia o frontmatter da nota com `scripts/read_frontmatter.py <nota.md>` (dá o JSON com
   job, conexões, pasta_destino, datasets_powerbi). Leia você mesmo o corpo Markdown da
   nota (seções `## <TABELA>`) e monte o `spec.json` completo — é você (Claude) quem
   interpreta a prosa da regra de negócio e decide `overrides`, `chave_merge`,
   `colunas_update_merge`, etc. Veja o formato exato do spec em
   `references/padrao_codigo.md` (seção 8) e no exemplo `references/spec_exemplo.json`.
3. Gere o código: `python scripts/generate_job.py <spec.json> --out-dir <pasta_destino>`.
   Rode com `--dry-run` primeiro se quiser conferir a lista de arquivos antes de escrever.
4. Valide: `python scripts/validate_job.py <pasta_destino>`. Corrija problemas bloqueantes
   antes de considerar terminado; leia as sugestões em voz alta para o usuário.
5. Resuma pro usuário: o que foi criado, quais `# TODO-REVISAO` ficaram no código (grep por
   `TODO-REVISAO`), e que nada foi commitado.

### 2. Migração a partir de um `.ktr`/`.kjb` do Pentaho

1. Rode `python scripts/parse_ktr.py <arquivo.ktr> --markdown` para cada transformação
   Pentaho relevante (normalmente uma por tabela: `Load_STG_X.ktr`, `Load_DM_X.ktr`, etc. —
   veja a pasta `PENTAHO/<NOME>/{STG,DW,ODS}` irmã da pasta em migração).
2. Isso devolve um rascunho em Markdown (SQL de origem, mapeamento origem→destino, chave e
   colunas de update sugeridas para MERGE, e uma lista de avisos). Cole esse rascunho na
   seção da tabela correspondente na nota de spec do Obsidian (crie a nota a partir do
   template se ainda não existir) e mostre ao usuário — ele precisa revisar antes de gerar
   código, principalmente:
   - steps que o parser não traduz (`DatabaseJoin`, `Calculator`, `JavaScript`, etc. — o
     parser avisa quando encontra) — normalmente é lógica que virou regra de negócio no
     Python e precisa ser reimplementada manualmente;
   - múltiplas origens (`Table Input` combinados, ex. tabela atual + histórico) — o
     parser não decide como combinar, isso é decisão do usuário;
   - a chave de MERGE sugerida pode ser incompleta (o Pentaho às vezes só marca uma
     coluna como `<key>` mesmo quando o código Python final usa mais de uma) — sempre
     pergunte/confirme com o usuário antes de aceitar a sugestão como está.
3. Depois de revisado, siga os passos 2-5 do fluxo "job novo" acima para gerar e validar.
4. No resumo final, deixe claro que o rascunho veio de parsing automático do Pentaho e
   precisa da mesma revisão de qualquer migração manual — esta skill acelera a extração,
   não substitui a revisão.

### 3. Melhoria incremental num job existente (novo campo / nova tabela)

Use `scripts/apply_change.py`, que nunca sobrescreve nada sem avisar:

- **Adicionar campo:**
  `python scripts/apply_change.py add-field <pasta_job> <CAMADA> <TABELA> --destino X --origem Y [--tipo T] [--tamanho N] [--override "SQL"]`
  Lembre o usuário: se o campo precisa aparecer em mais de uma camada (ex.: também na
  camada seguinte STG→DM), rode o comando de novo para cada camada — não propaga sozinho.
- **Adicionar tabela nova a um job que já existe:** monte um JSON com `{"tabela": {...},
  "spec_contexto": {...}}` (mesmo formato de um item de `tabelas` do spec.json + o contexto
  do job) e rode `python scripts/apply_change.py add-table <pasta_job> <arquivo.json>`. Isso
  cria o `Load_*.py`/`Campos/*.json` novos e insere a tabela no `load_files` do orquestrador
  automaticamente.
- Sempre rode `scripts/validate_job.py <pasta_job>` depois de qualquer alteração incremental
  — é barato e pega problemas de contrato/chave antes do usuário perceber em produção.

### 4. Só validar/revisar um job já existente

Rode `python scripts/validate_job.py <pasta_job>` e traduza a saída para o usuário:
problemas bloqueantes primeiro (sintaxe, contrato de retorno errado, chave de MERGE
ausente/inconsistente, arquivo fora do `load_files`), depois sugestões. Se houver
`TODO-REVISAO` no código, liste-os explicitamente — são pontos que uma geração anterior
deixou pendentes de decisão humana.

**Nota sobre versão do Python:** o validador roda `ast.parse` com o interpretador do
ambiente atual. Alguns jobs já existentes (ex.: `{{ARQUIVO_EXEMPLO_STG}}`, `{{ARQUIVO_EXEMPLO_FT}}` do job de
{{NOME_JOB_EXEMPLO_1}}) usam uma sintaxe de f-string que só existe a partir do Python 3.12 (barra
invertida dentro da expressão). Se o validador acusar erro de sintaxe nesses arquivos e o
ambiente estiver rodando Python < 3.12, não é um bug no arquivo — é uma diferença de versão
do interpretador; rode a validação com Python 3.12+ para não ter falso positivo. O código
que esta skill *gera* evita essa sintaxe de propósito, então funciona em uma faixa mais
ampla de interpretadores que alguns dos arquivos originais.

## Onde as coisas ficam

- `references/padrao_codigo.md` — a convenção de código completa (leia primeiro, sempre).
- `references/spec_exemplo.json` — um `spec.json` de exemplo completo (2 tabelas,
  STG+DM), pronto para copiar/adaptar.
- `assets/Template - Job ETL.md` — template da nota de spec para o Obsidian.
- `scripts/parse_ktr.py` — extrai rascunho de um `.ktr` do Pentaho.
- `scripts/read_frontmatter.py` — lê o frontmatter YAML de uma nota do Obsidian.
- `scripts/generate_job.py` — gera a árvore completa de um job a partir de um spec.json.
- `scripts/apply_change.py` — aplica alterações incrementais (campo novo / tabela nova).
- `scripts/validate_job.py` — validações estáticas + sugestões (sem tocar em banco real).

Todos os scripts são Python puro (stdlib + PyYAML só para `read_frontmatter.py`) — sem
dependência de Jinja2 ou outra engine de template, para rodar em qualquer ambiente que já
tenha Python. Se `import yaml` falhar, rode `pip install pyyaml --break-system-packages`.
