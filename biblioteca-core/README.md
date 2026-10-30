# Biblioteca `{{BIBLIOTECA_CORE}}` (versão aberta)

Implementação centralizada de conexões, log, auditoria, alertas e Power BI com **a mesma API**
que o código gerado pela skill espera (`from core.... import ...`). Use-a quando você **não tiver
acesso** à biblioteca interna original — os jobs gerados rodam sem nenhuma alteração.

## Instalação
```bash
pip install -e ./biblioteca-core            # base (pyodbc, requests)
pip install -e "./biblioteca-core[spark]"   # + pyspark
```
Requisitos de sistema: driver ODBC do SQL Server (ex.: "ODBC Driver 18 for SQL Server") e Java
para o Spark. O driver JDBC é baixado automaticamente (`SPARK_JARS_PACKAGES`) ou indicado
por `SPARK_JARS`.

## Configuração (centralizada)
1. Copie `exemplos/{{ARQUIVO_CREDENCIAIS}}.exemplo` para `{{ARQUIVO_CREDENCIAIS}}` e preencha.
2. Coloque o arquivo numa pasta **acima** dos jobs (é procurado subindo a partir do script)
   ou aponte com a variável de ambiente `ETL_CREDENCIAIS`.
3. **Nunca** versione esse arquivo (adicione ao `.gitignore`).
4. Rode `exemplos/ddl_tabelas_log.sql` no banco de auditoria.

## Variáveis de ambiente
| Variável | Uso |
|---|---|
| `ETL_CREDENCIAIS` | Caminho do arquivo de credenciais |
| `SPARK_JARS_PACKAGES` / `SPARK_JARS` | Driver JDBC |
| `SPARK_APP_NAME` | Nome da aplicação Spark |
| `ODBC_DRIVER` | Driver ODBC usado no `execute()` |

## Módulos
| Módulo | API |
|---|---|
| `core.configs.ConfigLoader` | `caminho_base`, `carregar_credenciais()`, `get_job_name(p)`, `ambienteAtual(cred)`, `recupera_tabelas(p, load_files)` |
| `core.connection` | `DatabaseConfig.from_credentials(cred, secao, db_type)`, `Connections.create_connection(cfg)` |
| `core.logging.LoggerSetup` | `LoggerSetup(projeto, caminho, job).setup_logging()` |
| `core.send_mail.EmailSender` | `enviar_email(assunto, mensagem, cred['email'])` |
| `core.log_tables.TableLogs` | `{{TABELA_LOG_ATUALIZACAO}}(...)`, `{{TABELA_LOG_DT}}(...)` |
| `core.api_powerbi.PowerbiRequest` | `update_dataset(cred, workspace_id, datasets)` |
| `core.spark_configs.spark_facade.Spark` | `conectar()`, `read(sql, nome)`, `write(df, tabela, modo)`, `execute(sql)`, `desconectar()` |

Para usar outro banco (Postgres, BigQuery…), altere apenas `connection.py` e `spark_facade.py`:
os jobs não mudam.
