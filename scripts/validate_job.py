#!/usr/bin/env python3
"""
Validações estáticas de um job (recém-gerado ou já existente) — nada aqui conecta
em banco de dados real; são checagens de forma, não de resultado. O objetivo é
pegar cedo o tipo de erro que só apareceria em produção (contrato de retorno errado,
chave de MERGE ausente, campo referenciado no override mas inexistente no JSON,
arquivo esquecido fora da ordem de execução do orquestrador).

Uso:
    python validate_job.py <pasta_do_job>   # ex.: .../{{JOB_REFERENCIA_1}}/{{PASTA_JOB_EXEMPLO_1}}

Imprime uma lista de problemas (bloqueantes) e sugestões (não bloqueantes).
Saída não-zero se houver problema bloqueante.
"""
import re
import sys
import ast
import json
import argparse
from pathlib import Path

CAMADAS = ["ORIGEM", "DIMENSOES", "FATOS"]
RETORNO_ESPERADO = [
    "tabela_origem", "validacao", "banco_origem", "banco_destino",
    "erro", "hora_inicio", "hora_fim", "duracao", "count",
]


def _erro(problemas, msg):
    problemas.append(msg)


def _aviso(sugestoes, msg):
    sugestoes.append(msg)


def checar_sintaxe(caminho: Path, problemas: list):
    try:
        ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except SyntaxError as e:
        _erro(problemas, f"[SINTAXE] {caminho}: {e}")


def checar_contrato_retorno(caminho: Path, problemas: list):
    """Confere que executar_select_e_update() devolve a tupla de 9 posições esperada,
    na ordem certa, tanto no caminho de sucesso quanto no de erro."""
    if "executar_select_e_update" not in caminho.name and "Load_" not in caminho.name:
        return
    texto = caminho.read_text(encoding="utf-8")
    returns = re.findall(r"return\s+(.+)", texto)
    returns = [r for r in returns if "tabela_origem" in r]
    if not returns:
        _erro(problemas, f"[CONTRATO] {caminho}: não encontrei nenhum 'return tabela_origem, ...' — "
                          f"o orquestrador espera essa tupla de 9 posições.")
        return
    for r in returns:
        partes = [p.strip() for p in r.split(",")]
        if len(partes) != len(RETORNO_ESPERADO):
            _erro(problemas, f"[CONTRATO] {caminho}: 'return' com {len(partes)} valores, "
                              f"esperado {len(RETORNO_ESPERADO)} ({', '.join(RETORNO_ESPERADO)}). "
                              f"Encontrado: {r.strip()}")


def checar_campos_json(caminho: Path, problemas: list, sugestoes: list) -> set:
    """Valida o Campos/*.json e devolve o conjunto de nomes de destino (para outras checagens)."""
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _erro(problemas, f"[JSON] {caminho}: JSON inválido — {e}")
        return set()

    if not isinstance(dados, list):
        _erro(problemas, f"[JSON] {caminho}: esperava uma lista de objetos, veio {type(dados).__name__}")
        return set()

    destinos = []
    for i, item in enumerate(dados):
        if "destino" not in item or not item["destino"]:
            _erro(problemas, f"[JSON] {caminho}: item {i} sem 'destino' preenchido — {item}")
            continue
        destinos.append(item["destino"])
        if "origem" not in item:
            _aviso(sugestoes, f"[JSON] {caminho}: item '{item['destino']}' sem chave 'origem' "
                               f"(ok se for campo 100% calculado, mas confirme).")

    duplicados = {d for d in destinos if destinos.count(d) > 1}
    if duplicados:
        _erro(problemas, f"[JSON] {caminho}: destino(s) duplicado(s): {sorted(duplicados)}")

    return set(destinos)


def checar_load_dm(caminho: Path, destinos: set, problemas: list, sugestoes: list):
    texto = caminho.read_text(encoding="utf-8")
    if "DimensionLookup" in texto:
        pass  # não deveria aparecer em código Python, só sanity
    m_chave = re.search(r"COLUNAS_CHAVE\s*=\s*(\{[^}]*\}|set\(\))", texto)
    if not m_chave:
        return
    chave_txt = m_chave.group(1)
    chaves = set(re.findall(r'"([^"]+)"', chave_txt))
    if not chaves:
        _erro(problemas, f"[MERGE] {caminho}: COLUNAS_CHAVE está vazio — o MERGE gerado não teria "
                          f"condição de match (ON) válida.")
    else:
        faltando = chaves - destinos
        if faltando:
            _erro(problemas, f"[MERGE] {caminho}: chave(s) {sorted(faltando)} não aparecem no "
                              f"Campos/*.json correspondente — o MERGE vai falhar em runtime.")

    m_overrides = re.search(r"OVERRIDES_SELECT\s*=\s*\{(.*?)\n\}", texto, re.S)
    if m_overrides:
        overrides_keys = set(re.findall(r'"([^"]+)":', m_overrides.group(1)))
        orfaos = overrides_keys - destinos
        if orfaos:
            _erro(problemas, f"[OVERRIDES] {caminho}: override(s) para coluna(s) {sorted(orfaos)} que "
                              f"não existem em Campos/*.json — remova o override ou adicione o campo.")


def checar_todos_pendentes(caminho: Path, sugestoes: list):
    for i, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = linha.strip()
        # só conta como pendência real quando é comentário (#) ou docstring/SQL comentado (--),
        # não quando "TODO-REVISAO" aparece dentro de uma string usada como fallback em runtime
        if "TODO-REVISAO" in linha and (stripped.startswith("#") or stripped.startswith("--")):
            _aviso(sugestoes, f"[PENDÊNCIA] {caminho}:{i}: {stripped}")


def checar_orquestrador(job_dir: Path, problemas: list, sugestoes: list):
    orquestradores = list(job_dir.glob("Python_Job_*.py"))
    if not orquestradores:
        _erro(problemas, f"[ESTRUTURA] {job_dir}: nenhum arquivo Python_Job_*.py encontrado "
                          f"(o core.configs.get_job_name depende dele para identificar o job).")
        return
    orq = orquestradores[0]
    texto = orq.read_text(encoding="utf-8")

    m = re.search(r"load_files\s*=\s*\{(.*?)\n\s*\}\s*\n", texto, re.S)
    referenciados = set(re.findall(r'"([A-Za-z0-9_]+)"', m.group(1))) if m else set()

    arquivos_reais = set()
    for camada in CAMADAS:
        pasta = job_dir / camada
        if pasta.is_dir():
            for f in pasta.glob("Load_*.py"):
                arquivos_reais.add(f.stem.replace("Load_", ""))

    sem_arquivo = referenciados - arquivos_reais
    sem_referencia = arquivos_reais - referenciados
    if sem_arquivo:
        _erro(problemas, f"[ORQUESTRADOR] {orq}: load_files referencia {sorted(sem_arquivo)}, mas "
                          f"não encontrei Load_<isso>.py correspondente em ORIGEM/DIMENSOES/FATOS.")
    if sem_referencia:
        _aviso(sugestoes, f"[ORQUESTRADOR] {orq}: existe(m) Load_*.py para {sorted(sem_referencia)} "
                           f"que não aparecem em nenhuma entrada de load_files — o arquivo não vai ser "
                           f"executado (core.configs.recupera_tabelas só ordena o que casa com load_files).")

    for retorno in ["tabela_origem, sucesso, banco_origem, banco_destino, erro"]:
        if retorno not in texto:
            _aviso(sugestoes, f"[ORQUESTRADOR] {orq}: não encontrei o desempacotamento padrão da tupla "
                               f"de retorno — confira se o contrato de 9 posições está sendo respeitado.")


def validar_job(job_dir: str) -> dict:
    job_dir = Path(job_dir)
    problemas, sugestoes = [], []

    if not job_dir.is_dir():
        return {"problemas": [f"Pasta não encontrada: {job_dir}"], "sugestoes": []}

    for camada in CAMADAS:
        pasta = job_dir / camada
        if not pasta.is_dir():
            continue
        for load_py in pasta.glob("Load_*.py"):
            checar_sintaxe(load_py, problemas)
            checar_contrato_retorno(load_py, problemas)
            checar_todos_pendentes(load_py, sugestoes)

            campos_json = pasta / "Campos" / f"Campos{load_py.stem.replace('Load_', '')}.json"
            destinos = set()
            if campos_json.is_file():
                destinos = checar_campos_json(campos_json, problemas, sugestoes)
            else:
                _erro(problemas, f"[ESTRUTURA] {load_py}: não encontrei {campos_json.name} correspondente.")

            if camada == "DIMENSOES":
                checar_load_dm(load_py, destinos, problemas, sugestoes)

    for orq in job_dir.glob("Python_Job_*.py"):
        checar_sintaxe(orq, problemas)
        checar_todos_pendentes(orq, sugestoes)

    checar_orquestrador(job_dir, problemas, sugestoes)

    gitignore = job_dir / ".gitignore"
    if not gitignore.is_file():
        _aviso(sugestoes, f"[HIGIENE] {job_dir}: sem .gitignore — logs/ e __pycache__/ podem acabar indo pro git.")
    elif "logs/" not in gitignore.read_text(encoding="utf-8"):
        _aviso(sugestoes, f"[HIGIENE] {gitignore}: não ignora 'logs/' — confira antes do primeiro commit.")

    return {"problemas": problemas, "sugestoes": sugestoes}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("job_dir", help="Pasta do job (ex.: .../{{JOB_REFERENCIA_1}}/{{PASTA_JOB_EXEMPLO_1}})")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    resultado = validar_job(args.job_dir)

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        sys.exit(1 if resultado["problemas"] else 0)

    if resultado["problemas"]:
        print(f"❌ {len(resultado['problemas'])} problema(s) bloqueante(s):\n")
        for p in resultado["problemas"]:
            print(f"  - {p}")
        print()
    else:
        print("✅ Nenhum problema bloqueante encontrado.\n")

    if resultado["sugestoes"]:
        print(f"💡 {len(resultado['sugestoes'])} sugestão(ões) / pendência(s) para revisar:\n")
        for s in resultado["sugestoes"]:
            print(f"  - {s}")

    sys.exit(1 if resultado["problemas"] else 0)


if __name__ == "__main__":
    main()
