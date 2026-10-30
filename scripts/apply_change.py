#!/usr/bin/env python3
"""
Aplica alterações INCREMENTAIS num job que já existe: adicionar um campo a uma
tabela existente, ou adicionar uma tabela nova (Load_*.py + Campos/*.json) a um
job que já tem outras tabelas.

Assim como generate_job.py, este script nunca roda git e nunca sobrescreve um
arquivo já existente sem avisar — sempre devolve um resumo detalhado do que foi
alterado para revisão humana.

Uso:
    python apply_change.py add-field  <job_dir> <camada> <tabela> --destino X --origem Y [--tipo T] [--tamanho N] [--override "EXPR SQL"]
    python apply_change.py add-table  <job_dir> <tabela_spec.json>

Onde <tabela_spec.json> tem o mesmo formato de um item de "tabelas" no spec.json
usado por generate_job.py (ver references/padrao_codigo.md).
"""
import re
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_job import (  # noqa: E402
    GERADORES, CAMADA_PASTA, _nome_arquivo_json, _preparar_tabela, gerar_campos_json,
)


def add_field(job_dir: str, camada: str, tabela_nome: str, destino: str, origem: str = "",
              tipo: str = "nvarchar", tamanho: str = None, override: str = None) -> dict:
    job_dir = Path(job_dir)
    pasta_camada = job_dir / CAMADA_PASTA[camada]
    campos_path = pasta_camada / "Campos" / _nome_arquivo_json(tabela_nome)
    load_path = pasta_camada / f"Load_{tabela_nome}.py"

    resumo = {"arquivo_campos": str(campos_path), "arquivo_load": str(load_path), "acoes": []}

    if not campos_path.is_file():
        resumo["acoes"].append(f"ERRO: {campos_path} não existe — confirme camada/nome da tabela.")
        return resumo

    campos = json.loads(campos_path.read_text(encoding="utf-8"))
    if any(c["destino"] == destino for c in campos):
        resumo["acoes"].append(f"Campo '{destino}' já existe em {campos_path.name} — nada foi alterado.")
        return resumo

    novo = {"origem": origem, "destino": destino, "tipo": tipo}
    if tamanho is not None:
        novo["tamanho"] = str(tamanho)
    campos.append(novo)
    campos_path.write_text(json.dumps(campos, ensure_ascii=False, indent=4), encoding="utf-8")
    resumo["acoes"].append(f"Campo '{destino}' adicionado a {campos_path.name}.")

    if override and load_path.is_file():
        texto = load_path.read_text(encoding="utf-8")
        m = re.search(r"(OVERRIDES_SELECT\s*=\s*\{)(.*?)(\n\})", texto, re.S)
        if m:
            nova_linha = f'    "{destino}": "{override}",'
            if f'"{destino}"' in m.group(2):
                resumo["acoes"].append(
                    f"AVISO: '{destino}' já tinha uma entrada em OVERRIDES_SELECT — não mexi, "
                    f"confira manualmente se precisa trocar o valor."
                )
            else:
                novo_bloco = m.group(1) + m.group(2) + f"\n{nova_linha}" + m.group(3)
                texto = texto[: m.start()] + novo_bloco + texto[m.end():]
                load_path.write_text(texto, encoding="utf-8")
                resumo["acoes"].append(f"Override '{destino}' = \"{override}\" adicionado a {load_path.name}.")
        else:
            resumo["acoes"].append(
                f"AVISO: não encontrei o dict OVERRIDES_SELECT em {load_path.name} — "
                f"adicione manualmente: \"{destino}\": \"{override}\""
            )
    elif override:
        resumo["acoes"].append(f"AVISO: pedi para adicionar override mas {load_path} não existe.")

    resumo["acoes"].append(
        "LEMBRETE: se este campo também precisa aparecer numa camada seguinte (ex.: STG->DM->FT), "
        "adicione-o lá também com esta mesma função — o gerador não propaga automaticamente entre camadas."
    )
    return resumo


def add_table(job_dir: str, tabela: dict, spec_contexto: dict) -> dict:
    """spec_contexto precisa ter pelo menos 'conexoes', 'log_name'/'job', 'projeto' —
    o mesmo nível do spec.json usado por generate_job.py, para resolver as conexões."""
    job_dir = Path(job_dir)
    resumo = {"acoes": []}

    t = _preparar_tabela(tabela, spec_contexto)
    camada = t["camada"]
    pasta_camada = job_dir / CAMADA_PASTA[camada]

    campos_path = pasta_camada / "Campos" / _nome_arquivo_json(t["nome"])
    load_path = pasta_camada / f"Load_{t['nome']}.py"

    if load_path.exists() or campos_path.exists():
        resumo["acoes"].append(
            f"ERRO: {load_path.name} e/ou {campos_path.name} já existem — use add-field para alterar "
            f"uma tabela existente, não add-table."
        )
        return resumo

    campos_path.parent.mkdir(parents=True, exist_ok=True)
    campos_path.write_text(gerar_campos_json(t.get("campos", [])), encoding="utf-8")
    resumo["acoes"].append(f"Criado {campos_path}.")

    codigo = GERADORES[camada](t)
    load_path.write_text(codigo, encoding="utf-8")
    resumo["acoes"].append(f"Criado {load_path}.")

    orquestradores = list(job_dir.glob("Python_Job_*.py"))
    if not orquestradores:
        resumo["acoes"].append("AVISO: não encontrei o orquestrador Python_Job_*.py — adicione a tabela manualmente ao load_files.")
        return resumo

    orq = orquestradores[0]
    texto = orq.read_text(encoding="utf-8")
    grupo = str(t.get("grupo", 0))

    m = re.search(rf"({grupo}:\s*\[)(.*?)(\n\s*\])", texto, re.S)
    if not m:
        resumo["acoes"].append(
            f"AVISO: não encontrei o grupo {grupo} em load_files de {orq.name} — "
            f"adicione \"{t['nome']}\" manualmente."
        )
        return resumo

    if f'"{t["nome"]}"' in m.group(2):
        resumo["acoes"].append(f"'{t['nome']}' já estava listado em load_files[{grupo}] — nada a fazer.")
        return resumo

    conteudo_grupo = m.group(2).rstrip()
    separador = ",\n                " if conteudo_grupo.strip() else "\n                "
    novo_grupo = m.group(1) + conteudo_grupo + (separador if conteudo_grupo.strip() else "") + f'"{t["nome"]}"' + m.group(3)
    texto = texto[: m.start()] + novo_grupo + texto[m.end():]
    orq.write_text(texto, encoding="utf-8")
    resumo["acoes"].append(f"'{t['nome']}' adicionado a load_files[{grupo}] em {orq.name}.")

    return resumo


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add_field = sub.add_parser("add-field")
    p_add_field.add_argument("job_dir")
    p_add_field.add_argument("camada", choices=["ORIGEM", "DIMENSOES", "FATOS"])
    p_add_field.add_argument("tabela")
    p_add_field.add_argument("--destino", required=True)
    p_add_field.add_argument("--origem", default="")
    p_add_field.add_argument("--tipo", default="nvarchar")
    p_add_field.add_argument("--tamanho", default=None)
    p_add_field.add_argument("--override", default=None)

    p_add_table = sub.add_parser("add-table")
    p_add_table.add_argument("job_dir")
    p_add_table.add_argument("tabela_spec_json", help="Arquivo JSON com a definição da nova tabela + contexto do job")

    args = ap.parse_args()

    if args.cmd == "add-field":
        resumo = add_field(args.job_dir, args.camada, args.tabela, args.destino, args.origem,
                            args.tipo, args.tamanho, args.override)
    else:
        dados = json.loads(Path(args.tabela_spec_json).read_text(encoding="utf-8"))
        resumo = add_table(args.job_dir, dados["tabela"], dados["spec_contexto"])

    for a in resumo["acoes"]:
        print(f"  - {a}")


if __name__ == "__main__":
    main()
