"""Configuração de log do job: console + arquivo diário em <caminho>/logs/<job>_<AAAA-MM-DD>.log"""
import logging as _logging
from pathlib import Path
from datetime import date


class LoggerSetup:
    def __init__(self, projeto: str, caminho, job: str):
        self.projeto = projeto
        self.caminho = Path(caminho)
        self.job = job

    def setup_logging(self) -> _logging.Logger:
        pasta_logs = self.caminho / "logs"
        pasta_logs.mkdir(parents=True, exist_ok=True)
        arquivo = pasta_logs / f"{self.job}_{date.today():%Y-%m-%d}.log"

        fmt = _logging.Formatter(f"%(asctime)s | {self.projeto} | {self.job} | %(levelname)s | %(name)s | %(message)s")
        raiz = _logging.getLogger()
        raiz.setLevel(_logging.INFO)
        for h in list(raiz.handlers):
            raiz.removeHandler(h)
        fh = _logging.FileHandler(arquivo, encoding="utf-8")
        fh.setFormatter(fmt)
        sh = _logging.StreamHandler()
        sh.setFormatter(fmt)
        raiz.addHandler(fh)
        raiz.addHandler(sh)
        return _logging.getLogger(self.job)
