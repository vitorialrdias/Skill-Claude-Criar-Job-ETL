"""Carregamento de credenciais e utilitários de descoberta do job.

O arquivo de credenciais é localizado, nesta ordem:
  1. variável de ambiente ETL_CREDENCIAIS (caminho completo);
  2. {{ARQUIVO_CREDENCIAIS}} na pasta do script em execução ou em qualquer pasta acima dela.
"""
import os
import sys
import json
from pathlib import Path

NOME_ARQUIVO_CREDENCIAIS = "{{ARQUIVO_CREDENCIAIS}}"
CAMADAS = ("ORIGEM", "DIMENSOES", "FATOS")


class ConfigLoader:
    # Caminho do script que iniciou o processo (orquestrador ou Load_*.py executado direto)
    caminho_base = Path(sys.argv[0]).resolve()

    @staticmethod
    def _localizar_credenciais() -> Path:
        env = os.environ.get("ETL_CREDENCIAIS")
        if env:
            return Path(env)
        pasta = ConfigLoader.caminho_base if ConfigLoader.caminho_base.is_dir() else ConfigLoader.caminho_base.parent
        for p in [pasta, *pasta.parents]:
            candidato = p / NOME_ARQUIVO_CREDENCIAIS
            if candidato.is_file():
                return candidato
        raise FileNotFoundError(
            f"Arquivo de credenciais '{NOME_ARQUIVO_CREDENCIAIS}' não encontrado. "
            f"Defina ETL_CREDENCIAIS ou coloque o arquivo numa pasta acima do job."
        )

    @staticmethod
    def carregar_credenciais() -> dict:
        with open(ConfigLoader._localizar_credenciais(), "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def get_job_name(caminho) -> str:
        """Nome do job a partir do arquivo Python_Job_*.py (procura no caminho e até 2 níveis acima)."""
        caminho = Path(caminho)
        if caminho.is_file() and caminho.name.startswith("Python_Job_"):
            return caminho.stem.replace("Python_Job_", "")
        pasta = caminho if caminho.is_dir() else caminho.parent
        for p in [pasta, pasta.parent, pasta.parent.parent]:
            achados = sorted(p.glob("Python_Job_*.py"))
            if achados:
                return achados[0].stem.replace("Python_Job_", "")
        return pasta.name

    @staticmethod
    def ambienteAtual(credenciais) -> str:
        """PROD / HOMOLOG / DEV — lido de credenciais['ambiente'] (padrão DEV)."""
        if not credenciais:
            return "DESCONHECIDO"
        return str(credenciais.get("ambiente", "DEV")).upper()

    @staticmethod
    def recupera_tabelas(caminho_job, load_files: dict) -> list:
        """Descobre os Load_*.py em ORIGEM/DIMENSOES/FATOS e devolve na ordem de load_files.

        load_files = {0: ["STG_A", ...], 1: ["DM_A", "FT_B", ...]}
        Arquivos que não casam com nenhuma entrada NÃO são executados.
        """
        caminho_job = Path(caminho_job)
        arquivos = []
        for camada in CAMADAS:
            pasta = caminho_job / camada
            if pasta.is_dir():
                arquivos.extend(sorted(pasta.glob("Load_*.py")))

        ordenados = []
        for grupo in sorted(load_files):
            for nome in load_files[grupo]:
                for arq in arquivos:
                    if arq.stem == f"Load_{nome}" and arq not in ordenados:
                        ordenados.append(arq)
        return [str(a) for a in ordenados]
