# Variáveis do template

Os arquivos deste template são idênticos aos da skill original. A única diferença é que os
nomes específicos do projeto foram trocados por variáveis `{{...}}`. Para adaptar a skill
a outro projeto, substitua cada variável pelo valor correspondente (por exemplo, com
localizar/substituir em toda a pasta) e renomeie a pasta para o valor de `{{NOME_SKILL}}`.

| Variável | O que representa | Exemplo |
|---|---|---|
| `{{NOME_SKILL}}` | Nome da skill (= nome da pasta) | `criar-job-etl` |
| `{{PASTA_PROJETO}}` | Pasta-raiz dos jobs migrados | `MIGRACAO` |
| `{{RAIZ_JOBS}}` | Pasta que contém os jobs Python | `PYTHON JOBS` |
| `{{CAMINHO_BIBLIOTECA}}` | Caminho da biblioteca compartilhada | `PYTHON JOBS/LIBRARY-PYTHON/LIBRARY` |
| `{{BIBLIOTECA_CORE}}` | Nome do pacote compartilhado | `etl-core` |
| `{{PACOTE_CORE_PY}}` | Nome do pacote em formato Python | `etl_core` |
| `{{ARQUIVO_CREDENCIAIS}}` | Arquivo de credenciais (nunca editado) | `credenciais.json` |
| `{{SECAO_CONEXAO_ORIGEM}}` | Seção de conexão da origem | `sql_portal` |
| `{{SECAO_CONEXAO_STAGING}}` | Seção de conexão da staging | `sql_stg` |
| `{{SECAO_CONEXAO_DW}}` | Seção de conexão do DW | `sql_dw` |
| `{{SECAO_CONEXAO_AUX}}` | Seção de conexão de auditoria | `sql_aux_tables` |
| `{{TABELA_LOG_ATUALIZACAO}}` | Tabela de log de execução | `tb_log_atualizacao` |
| `{{TABELA_LOG_DT}}` | Tabela de log de datas | `tb_log_dt` |
| `{{PROJETO}}` | Projeto/área de negócio | `Folha` |
| `{{TIPO_JOB}}` | Nome do template de nota | `Job ETL` |
| `{{JOB_REFERENCIA_1..3}}` | Jobs reais usados como referência do padrão | `Job_Beneficios`, ... |
| `{{ARQUIVO_ORQUESTRADOR_REFERENCIA}}` | Orquestrador de referência | `Python_Job_Congela_Pedidos.py` |
| `{{NOME_JOB_EXEMPLO_1/2}}`, `{{PASTA_JOB_EXEMPLO_1/2}}` | Nomes e pastas de jobs citados como exemplo | `Benefícios` / `BENEFICIOS` |
| `{{ARQUIVO_EXEMPLO_STG}}`, `{{ARQUIVO_EXEMPLO_FT}}` | Arquivos citados como exemplo | `Load_STG_VA.py` |
| `{{TABELA_ATUAL_EXEMPLO}}`, `{{TABELA_HISTORICO_EXEMPLO}}` | Tabelas de exemplo de origem múltipla | `BEN_VA`, `BEN_VAH` |

A pasta `docs/` contém apenas a documentação acadêmica e não é usada pela skill.
