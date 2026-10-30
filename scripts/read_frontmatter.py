#!/usr/bin/env python3
"""
Extrai o frontmatter YAML (bloco entre --- no topo) de uma nota do Obsidian e
devolve como JSON. É a única parte "determinística" da leitura da nota — o corpo
(seções de tabela em prosa) é lido e interpretado pelo próprio Claude ao montar o
spec.json completo (ver SKILL.md), porque a regra de negócio é texto livre por
design (assim o usuário não precisa aprender uma sintaxe rígida no Obsidian).

Uso:
    python read_frontmatter.py <nota.md>
"""
import sys
import json

try:
    import yaml
except ImportError:
    print(
        "Erro: PyYAML não está instalado neste ambiente. Rode:\n"
        "    pip install pyyaml --break-system-packages\n"
        "e tente de novo.",
        file=sys.stderr,
    )
    sys.exit(1)


def read_frontmatter(caminho: str) -> dict:
    texto = open(caminho, encoding="utf-8").read()
    if not texto.startswith("---"):
        raise ValueError(f"{caminho} não começa com um bloco de frontmatter '---'.")
    partes = texto.split("---", 2)
    if len(partes) < 3:
        raise ValueError(f"{caminho}: não encontrei o fechamento do frontmatter ('---').")
    frontmatter_txt = partes[1]
    corpo = partes[2]
    dados = yaml.safe_load(frontmatter_txt) or {}
    dados["_corpo_markdown"] = corpo
    return dados


def main():
    if len(sys.argv) != 2:
        print("Uso: python read_frontmatter.py <nota.md>", file=sys.stderr)
        sys.exit(1)
    dados = read_frontmatter(sys.argv[1])
    print(json.dumps(dados, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
