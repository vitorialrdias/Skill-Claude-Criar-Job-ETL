"""Fachada única de leitura/escrita usada pelos Load_*.py.

Leitura e escrita via Spark JDBC (SQL Server). Comandos (MERGE etc.) via pyodbc.
Requer o driver JDBC do SQL Server: defina SPARK_JARS_PACKAGES (padrão abaixo) ou SPARK_JARS.
"""
import os
import logging

logger = logging.getLogger(__name__)
PACOTE_JDBC_PADRAO = "com.microsoft.sqlserver:mssql-jdbc:12.6.1.jre11"


class Spark:
    _session = None  # SparkSession compartilhada por todo o processo

    def __init__(self, host, database, user, password, port=1433,
                 bulk_insert_database=None, bulk_insert_credentials=None):
        self.host, self.database, self.user, self.password, self.port = host, database, user, password, int(port)
        # Mantidos por compatibilidade com o código gerado; não usados nesta implementação.
        self.bulk_insert_database = bulk_insert_database
        self.bulk_insert_credentials = bulk_insert_credentials
        self._odbc = None

    @property
    def url(self):
        return (f"jdbc:sqlserver://{self.host}:{self.port};databaseName={self.database};"
                f"encrypt=true;trustServerCertificate=true")

    @property
    def _props(self):
        return {"user": self.user, "password": self.password,
                "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver"}

    def conectar(self):
        if Spark._session is None:
            from pyspark.sql import SparkSession
            b = SparkSession.builder.appName(os.environ.get("SPARK_APP_NAME", "etl-job"))
            if os.environ.get("SPARK_JARS"):
                b = b.config("spark.jars", os.environ["SPARK_JARS"])
            else:
                b = b.config("spark.jars.packages", os.environ.get("SPARK_JARS_PACKAGES", PACOTE_JDBC_PADRAO))
            Spark._session = b.getOrCreate()
        return Spark._session

    def read(self, sql: str, nome_tabela: str = ""):
        logger.info(f"Lendo {nome_tabela or 'consulta'} de {self.database}")
        return (Spark._session.read.format("jdbc").option("url", self.url)
                .option("query", sql).options(**self._props).load())

    def write(self, df, tabela: str, modo: str = "overwrite") -> int:
        qtd = df.count()
        (df.write.format("jdbc").option("url", self.url).option("dbtable", tabela)
           .option("truncate", "true").options(**self._props).mode(modo).save())
        logger.info(f"{qtd} registros gravados em {self.database}.{tabela} ({modo})")
        return qtd

    def execute(self, sql: str) -> int:
        import pyodbc
        if self._odbc is None:
            driver = os.environ.get("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")
            self._odbc = pyodbc.connect(
                f"DRIVER={{{driver}}};SERVER={self.host},{self.port};DATABASE={self.database};"
                f"UID={self.user};PWD={self.password};TrustServerCertificate=yes", autocommit=False)
        cur = self._odbc.cursor()
        cur.execute(sql)
        qtd = cur.rowcount
        self._odbc.commit()
        return qtd

    def desconectar(self):
        if self._odbc is not None:
            self._odbc.close()
            self._odbc = None
        # A SparkSession é mantida para as próximas tabelas do mesmo job.
