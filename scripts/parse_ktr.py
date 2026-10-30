#!/usr/bin/env python3
"""
Parser de arquivos .ktr (Pentaho/Kettle) para extrair um RASCUNHO da especificação
de uma tabela: conexao de origem/destino, SQL de origem, mapeamento origem->destino,
overrides (expressoes calculadas), e (quando existe um step DimensionLookup) a
chave e as colunas de update do MERGE.

Isto e so um RASCUNHO para revisao humana -- nunca gere codigo Python direto daqui
sem antes deixar o usuario conferir o resultado (veja o campo "avisos" no retorno).

Uso:
    python parse_ktr.py <caminho.ktr> [--json] [--markdown]

Sem flags, imprime um resumo legivel. --json imprime o dict cru (para uso por
generate_job.py). --markdown imprime um bloco pronto para colar na nota de spec
do Obsidian.
"""
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def _text(el, path, default=None):
    found = el.find(path)
    if found is None or found.text is None:
        return default
    return found.text


def _parse_table_input(step_el):
    return {
        "step_nome": _text(step_el, "name"),
        "conexao": _text(step_el, "connection"),
        "sql": (_text(step_el, "sql") or "").strip(),
    }


def _parse_table_output(step_el):
    fields = []
    for f in step_el.findall("./fields/field"):
        fields.append({
            "coluna_destino": _text(f, "column_name"),
            "campo_origem_stream": _text(f, "stream_name"),
        })
    return {
        "step_nome": _text(step_el, "name"),
        "conexao": _text(step_el, "connection"),
        "tabela": _text(step_el, "table"),
        "schema": _text(step_el, "schema"),
        "campos": fields,
    }


def _parse_select_values(step_el):
    """Mapa campo-de-entrada -> nome renomeado (o que normalmente vira o 'destino' final)."""
    renames = {}
    for meta in step_el.findall("./fields/meta"):
        nome = _text(meta, "name")
        rename = _text(meta, "rename")
        if nome:
            renames[nome] = rename if rename else nome
    # Campos apenas selecionados (sem bloco <meta>, so <field><name>/<rename>)
    for f in step_el.findall("./fields/field"):
        nome = _text(f, "name")
        rename = _text(f, "rename")
        if nome and nome not in renames:
            renames[nome] = rename if rename else nome
    return {"step_nome": _text(step_el, "name"), "renomeios": renames}


def _parse_dimension_lookup(step_el):
    chave = []
    for k in step_el.findall("./fields/key"):
        chave.append({"campo": _text(k, "name"), "lookup": _text(k, "lookup")})

    colunas_update = []
    for f in step_el.findall("./fields/field"):
        colunas_update.append({
            "campo": _text(f, "name"),
            "lookup": _text(f, "lookup"),
            "update": _text(f, "update"),
        })

    retorno = step_el.find("./fields/return")
    sk = _text(retorno, "name") if retorno is not None else None

    return {
        "step_nome": _text(step_el, "name"),
        "conexao": _text(step_el, "connection"),
        "tabela": _text(step_el, "table"),
        "schema": _text(step_el, "schema"),
        "chave_natural": [k["campo"] for k in chave],
        "colunas_update": [c["campo"] for c in colunas_update if c.get("update") == "Update"],
        "surrogate_key": sk,
    }


STEP_PARSERS = {
    "TableInput": _parse_table_input,
    "TableOutput": _parse_table_output,
    "SelectValues": _parse_select_values,
    "DimensionLookup": _parse_dimension_lookup,
}

# Steps conhecidos que carregam logica de negocio dificil de extrair 1:1 (joins,
# calculos, scripts) -- o parser so avisa que existem, nao tenta traduzir.
STEPS_REVISAO_MANUAL = {
    "DatabaseJoin", "MergeJoin", "StreamLookup", "Calculator", "ScriptValueMod",
    "JavaScript", "FilterRows", "GroupBy", "Sort", "DatabaseLookup",
}


def parse_ktr(caminho: str) -> dict:
    caminho = Path(caminho)
    tree = ET.parse(caminho)
    root = tree.getroot()

    info_name = _text(root, "./info/name", caminho.stem)

    steps_by_type = {}
    avisos = []
    ordem_nomes = []

    for step_el in root.findall("./step"):
        nome = _text(step_el, "name")
        tipo = _text(step_el, "type")
        ordem_nomes.append((nome, tipo))

        parser = STEP_PARSERS.get(tipo)
        if parser:
            steps_by_type.setdefault(tipo, []).append(parser(step_el))
        elif tipo in STEPS_REVISAO_MANUAL:
            avisos.append(
                f"Step '{nome}' (tipo {tipo}) contém lógica que o parser não traduz "
                f"automaticamente (join/cálculo/script) — descreva a regra em prosa na "
                f"nota de spec e revise o SQL gerado."
            )
        else:
            avisos.append(f"Step '{nome}' (tipo {tipo}) não reconhecido — ignorado pelo parser.")

    hops = []
    for hop in root.findall("./order/hop"):
        hops.append((_text(hop, "from"), _text(hop, "to")))

    table_inputs = steps_by_type.get("TableInput", [])
    table_outputs = steps_by_type.get("TableOutput", [])
    select_values = steps_by_type.get("SelectValues", [])
    dim_lookups = steps_by_type.get("DimensionLookup", [])

    if len(table_inputs) > 1:
        avisos.append(
            f"Encontradas {len(table_inputs)} origens (Table Input) neste .ktr "
            f"({', '.join(ti['step_nome'] for ti in table_inputs)}). O padrão Python trata "
            f"múltiplas origens combinadas (ex.: união de histórico + atual) como regra de "
            f"negócio manual — descreva como combiná-las na nota de spec."
        )

    # Monta o mapeamento origem -> destino combinando SelectValues (rename) com
    # TableOutput (nome final de coluna) ou DimensionLookup (merge).
    renomeios = {}
    for sv in select_values:
        renomeios.update(sv["renomeios"])

    campos = []
    if table_outputs:
        # Camada STG: TableOutput já traz a lista final de colunas de destino.
        for out in table_outputs:
            for f in out["campos"]:
                destino = f["coluna_destino"]
                origem_stream = f["campo_origem_stream"]
                campos.append({"origem": origem_stream, "destino": destino})
    elif renomeios:
        # Sem TableOutput explícito (ex.: DimensionLookup) — usa o rename do SelectValues.
        for origem_stream, destino in renomeios.items():
            campos.append({"origem": origem_stream, "destino": destino})

    resultado = {
        "job_ktr": info_name,
        "arquivo_origem": str(caminho),
        "steps_encontrados": ordem_nomes,
        "table_input": table_inputs,
        "table_output": table_outputs,
        "select_values": select_values,
        "dimension_lookup": dim_lookups,
        "campos_sugeridos": campos,
        "avisos": avisos,
    }

    if dim_lookups:
        dl = dim_lookups[0]
        resultado["merge_sugerido"] = {
            "tabela_destino": dl["tabela"],
            "conexao_destino": dl["conexao"],
            "chave_natural": dl["chave_natural"],
            "colunas_update": dl["colunas_update"],
        }
        if len(dim_lookups) > 1:
            avisos.append(
                "Mais de um step DimensionLookup encontrado — revise manualmente qual "
                "define a chave/colunas de update corretas."
            )

    return resultado


def to_markdown(spec: dict) -> str:
    """Gera um bloco Markdown pronto para colar na nota de spec do Obsidian."""
    linhas = [f"<!-- Rascunho gerado automaticamente a partir de {spec['arquivo_origem']} -->", ""]

    if spec["table_input"]:
        for ti in spec["table_input"]:
            linhas.append(f"**Conexão de origem (Pentaho: `{ti['conexao']}`):** confirme a seção correspondente em `{{ARQUIVO_CREDENCIAIS}}`")
            linhas.append("")
            linhas.append("**SQL de origem (Pentaho, revisar antes de usar):**")
            linhas.append("```sql")
            linhas.append(ti["sql"])
            linhas.append("```")
            linhas.append("")

    if spec.get("merge_sugerido"):
        m = spec["merge_sugerido"]
        linhas.append(f"**Tabela destino (MERGE):** `{m['tabela_destino']}` (conexão Pentaho: `{m['conexao_destino']}`)")
        linhas.append(f"**Chave natural sugerida:** {', '.join(m['chave_natural']) or '_(não identificada — preencher manualmente)_'}")
        linhas.append(f"**Colunas de update sugeridas:** {', '.join(m['colunas_update']) or '_(nenhuma identificada)_'}")
        linhas.append("")

    if spec["campos_sugeridos"]:
        linhas.append("| origem | destino |")
        linhas.append("|---|---|")
        for c in spec["campos_sugeridos"]:
            linhas.append(f"| {c['origem'] or '_(calculado)_'} | {c['destino']} |")
        linhas.append("")

    if spec["avisos"]:
        linhas.append("**⚠️ Pontos para revisão humana:**")
        for a in spec["avisos"]:
            linhas.append(f"- {a}")
        linhas.append("")

    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ktr", help="Caminho do arquivo .ktr")
    ap.add_argument("--json", action="store_true", help="Imprime o dict cru em JSON")
    ap.add_argument("--markdown", action="store_true", help="Imprime bloco Markdown para a spec")
    args = ap.parse_args()

    spec = parse_ktr(args.ktr)

    if args.json:
        print(json.dumps(spec, ensure_ascii=False, indent=2))
    elif args.markdown:
        print(to_markdown(spec))
    else:
        print(f"Job (Pentaho): {spec['job_ktr']}")
        print(f"Steps: {spec['steps_encontrados']}")
        print(f"Campos sugeridos: {len(spec['campos_sugeridos'])}")
        if spec.get("merge_sugerido"):
            print(f"MERGE sugerido: {spec['merge_sugerido']}")
        if spec["avisos"]:
            print("\nAVISOS:")
            for a in spec["avisos"]:
                print(f" - {a}")


if __name__ == "__main__":
    main()
