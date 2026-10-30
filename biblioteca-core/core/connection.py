"""Configuração e criação de conexões a partir de uma seção do arquivo de credenciais.

Formato esperado de cada seção:
    "<secao>": {"host": "...", "port": 1433, "database": "...", "username": "...",
                "password": "...", "driver": "ODBC Driver 18 for SQL Server"}
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    host: str
    database: str
    username: str
    password: str
    port: int = 1433
    db_type: str = "sqlserver"
    driver: str = "ODBC Driver 18 for SQL Server"
    extras: dict = field(default_factory=dict)

    @classmethod
    def from_credentials(cls, credenciais: dict, secao: str, db_type: str = "sqlserver") -> "DatabaseConfig":
        if secao not in credenciais:
            raise KeyError(f"Seção '{secao}' não existe no arquivo de credenciais.")
        c = dict(credenciais[secao])
        return cls(
            host=c.pop("host"),
            database=c.pop("database"),
            username=c.pop("username"),
            password=c.pop("password"),
            port=int(c.pop("port", 1433)),
            db_type=db_type,
            driver=c.pop("driver", "ODBC Driver 18 for SQL Server"),
            extras=c,
        )

    def odbc_string(self) -> str:
        extra = ";".join(f"{k}={v}" for k, v in self.extras.items())
        base = (f"DRIVER={{{self.driver}}};SERVER={self.host},{self.port};DATABASE={self.database};"
                f"UID={self.username};PWD={self.password};TrustServerCertificate=yes")
        return base + (";" + extra if extra else "")

    def jdbc_url(self) -> str:
        return (f"jdbc:sqlserver://{self.host}:{self.port};databaseName={self.database};"
                f"encrypt=true;trustServerCertificate=true")


class Connections:
    @staticmethod
    def create_connection(cfg: DatabaseConfig):
        """Conexão DB-API (pyodbc). Devolve None em caso de falha (o orquestrador trata o retry)."""
        try:
            import pyodbc
            return pyodbc.connect(cfg.odbc_string(), autocommit=False)
        except Exception as e:
            logger.error(f"Falha ao conectar em {cfg.host}/{cfg.database}: {e}")
            return None
