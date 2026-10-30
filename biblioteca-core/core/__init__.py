"""Biblioteca centralizada usada pelos jobs ETL gerados pela skill {{NOME_SKILL}}.

Módulos (mesma API esperada pelo código gerado):
    core.configs                    -> ConfigLoader (credenciais, nome do job, ambiente, ordem das tabelas)
    core.connection                 -> DatabaseConfig, Connections (conexão DB-API via pyodbc)
    core.logging                    -> LoggerSetup (log diário em logs/)
    core.send_mail                  -> EmailSender (alerta de erro via SMTP)
    core.log_tables                 -> TableLogs (tabelas de auditoria)
    core.api_powerbi                -> PowerbiRequest (refresh de datasets)
    core.spark_configs.spark_facade -> Spark (leitura/escrita via JDBC)
"""
__version__ = "0.1.0"
