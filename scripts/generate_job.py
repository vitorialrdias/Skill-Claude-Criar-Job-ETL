#!/usr/bin/env python3
"""
Gera (ou complementa) a árvore de um job ETL seguindo o padrão descrito em
references/padrao_codigo.md, a partir de uma especificação estruturada (dict/JSON).

Este script NUNCA roda comandos git (nem commit, nem add, nem push) e nunca lê/edita
o arquivo de credenciais. Ele só escreve arquivos .py/.json dentro da pasta de destino
informada na spec. Quem revisa e decide commitar é o usuário.

Uso:
    python generate_job.py <spec.json> [--out-dir CAMINHO] [--dry-run]

Ver references/spec_schema.md para o formato esperado do spec.json (ou peça pro
Claude gerar o spec.json a partir da nota do Obsidian antes de chamar este script).
"""
import sys
import json
import argparse
from pathlib import Path

CAMADA_PREFIXO = {"ORIGEM": "STG", "DIMENSOES": "DM", "FATOS": "FT"}
CAMADA_PASTA = {"ORIGEM": "ORIGEM", "DIMENSOES": "DIMENSOES", "FATOS": "FATOS"}
COLUNAS_AUDITORIA_PADRAO = ["version", "DT_INCLUSAO_SYSTEM", "DT_ATUALIZACAO_SYSTEM"]


def _dict_literal(d: dict, indent: str = "    ") -> str:
    """Renderiza um dict Python como texto de código-fonte, uma chave por linha."""
    if not d:
        return ""
    linhas = []
    for k, v in d.items():
        linhas.append(f'{indent}"{k}": "{v}",')
    return "\n".join(linhas)


def _set_literal(valores) -> str:
    if not valores:
        return "set()"
    itens = ", ".join(f'"{v}"' for v in valores)
    return "{" + itens + "}"


def gerar_campos_json(campos: list) -> str:
    """Gera o conteúdo de Campos/Campos<TIPO>_<TABELA>.json (mesmo formato observado nos jobs reais)."""
    saida = []
    for c in campos:
        item = {"origem": c.get("origem", ""), "destino": c["destino"], "tipo": c.get("tipo", "nvarchar")}
        if c.get("tamanho") is not None:
            item["tamanho"] = str(c["tamanho"])
        saida.append(item)
    return json.dumps(saida, ensure_ascii=False, indent=4)


def _nome_arquivo_json(tabela_nome: str) -> str:
    # STG_VA -> CamposSTG_VA.json  (tabela_nome já vem como "STG_VA"/"DM_VA"/"FT_VA")
    return f"Campos{tabela_nome}.json"


def gerar_load_stg(tabela: dict) -> str:
    overrides_txt = _dict_literal(tabela.get("overrides", {}))
    where_txt = tabela.get("where", "")
    where_bloco = f"WHERE {where_txt}" if where_txt else "-- TODO-REVISAO: confirme se falta um WHERE (ex.: filtro de exclusão lógica / competência)"
    regra = tabela.get("regra_negocio", "").strip()
    regra_comentario = f"        # Regra de negócio (da spec): {regra}\n" if regra else ""
    fontes = tabela.get("fontes_multiplas", [])
    aviso_fontes = ""
    if fontes:
        aviso_fontes = (
            "        # TODO-REVISAO: esta tabela tinha múltiplas origens no Pentaho "
            f"({', '.join(fontes)}) que precisam ser combinadas (ex.: union) — "
            "implemente a combinação manualmente aqui.\n"
        )

    return f'''import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from core.configs import ConfigLoader as configs
from core.connection import DatabaseConfig
from core.spark_configs import spark_facade
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Carrega o mapeamento de campos (origem -> destino) definido no json da tabela
ARQUIVO_CAMPOS = Path(__file__).resolve().parent / "Campos" / "{_nome_arquivo_json(tabela['nome'])}"
with open(ARQUIVO_CAMPOS, "r", encoding="utf-8") as f:
    campos = json.load(f)

# Expressões SQL para colunas que não são um simples "origem AS destino"
OVERRIDES_SELECT = {{
{overrides_txt}
}}


def executar_select_e_update():
    credenciais = configs.carregar_credenciais()

    validacao = False
    tabela_origem = '{tabela.get("tabela_sql_origem", tabela["nome"])}'
    banco_origem = credenciais['{tabela["conexao_origem"]}']['database']
    banco_destino = credenciais['{tabela["conexao_destino"]}']['database']
    count = None
    try:
        hora_inicio = datetime.now()

        conexao_origem = DatabaseConfig.from_credentials(credenciais, secao="{tabela["conexao_origem"]}", db_type="sqlserver")
        conexao_destino = DatabaseConfig.from_credentials(credenciais, secao="{tabela["conexao_destino"]}", db_type="sqlserver")

        conexao_origem = spark_facade.Spark(host=conexao_origem.host,
                                            database=conexao_origem.database,
                                            user=conexao_origem.username,
                                            password=conexao_origem.password)
        conexao_destino = spark_facade.Spark(host=conexao_destino.host,
                                        database=conexao_destino.database,
                                        user=conexao_destino.username,
                                        password=conexao_destino.password,
                                        bulk_insert_database="stg",
                                        bulk_insert_credentials=credenciais,
                                        )

        conexao_origem.conectar()
        conexao_destino.conectar()

{regra_comentario}{aviso_fontes}        select_campos = [
            f"{{OVERRIDES_SELECT.get(c['destino'], c['origem'])}} AS {{c['destino']}}"
            for c in campos
        ]

        select_campos_txt = ",\\n            ".join(select_campos)
        select_sql = f"""
            SELECT

            {{select_campos_txt}}

            FROM {tabela.get("tabela_sql_origem", tabela["nome"])}

            {where_bloco}
        """

        df = conexao_origem.read(select_sql, '{tabela.get("tabela_sql_origem", tabela["nome"])}')

        count = conexao_destino.write(df, '{tabela["nome"]}', 'overwrite')

        if not count:
            raise ValueError("ERROR: Nenhum registro foi inserido ou atualizado.")

        hora_fim = datetime.now()
        logger.info(f"Fim do processamento: {{hora_fim.strftime('%Y-%m-%d %H:%M:%S')}}")
        duracao = hora_fim - hora_inicio
        logger.info(f"Duração: {{duracao}}")

        conexao_origem.desconectar()
        conexao_destino.desconectar()

        validacao = True
        return tabela_origem, validacao, banco_origem, banco_destino, None, hora_inicio, hora_fim, duracao, count

    except Exception as erro:
        logger.error(f"Erro durante o processamento: {{erro}}")
        hora_fim = datetime.now()
        duracao = hora_fim - hora_inicio
        return tabela_origem, validacao, banco_origem, banco_destino, erro, hora_inicio, hora_fim, duracao, count


if __name__ == "__main__":
    from core.logging import LoggerSetup

    log = '{tabela.get("log_name", tabela["nome"])}'
    job = configs.get_job_name(configs.caminho_base.parent)

    job_logger = LoggerSetup(
        projeto="{tabela.get("projeto", "{{PROJETO}}")}",
        caminho=configs.caminho_base.parent.parent,
        job=job
    )
    job_logger = job_logger.setup_logging()
    executar_select_e_update()
'''


def gerar_load_dm(tabela: dict) -> str:
    overrides_txt = _dict_literal(tabela.get("overrides", {}))
    chave = tabela.get("chave_merge", [])
    update_cols = tabela.get("colunas_update_merge", [])
    if not chave:
        chave_comentario = "# TODO-REVISAO: nenhuma chave de MERGE foi definida na spec — preencha COLUNAS_CHAVE antes de usar."
    else:
        chave_comentario = ""
    regra = tabela.get("regra_negocio", "").strip()
    regra_comentario = f"        # Regra de negócio (da spec): {regra}\n" if regra else ""

    return f'''import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from core.configs import ConfigLoader as configs
from core.connection import DatabaseConfig
from core.spark_configs import spark_facade
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Carrega o mapeamento de campos (origem -> destino) definido no json da tabela
ARQUIVO_CAMPOS = Path(__file__).resolve().parent / "Campos" / "{_nome_arquivo_json(tabela['nome'])}"
with open(ARQUIVO_CAMPOS, "r", encoding="utf-8") as f:
    campos = json.load(f)

# Expressões SQL para colunas que não são um simples "origem AS destino"
OVERRIDES_SELECT = {{
{overrides_txt}
}}

{chave_comentario}
# Colunas que fazem parte da chave de match (ON) do MERGE e não entram no UPDATE SET
COLUNAS_CHAVE = {_set_literal(chave)}
# Colunas de auditoria com tratamento próprio (não entram no UPDATE SET genérico)
COLUNAS_AUDITORIA = {_set_literal(COLUNAS_AUDITORIA_PADRAO)}

DESTINOS = [c["destino"] for c in campos]
ORIGEM_POR_DESTINO = {{c["destino"]: c["origem"] for c in campos}}


def executar_select_e_update():
    credenciais = configs.carregar_credenciais()

    validacao = False
    tabela_origem = '{tabela.get("tabela_sql_origem", tabela["nome"])}'
    banco_origem = credenciais['{tabela["conexao_origem"]}']['database']
    banco_destino = credenciais['{tabela["conexao_destino"]}']['database']
    count = None
    try:
        hora_inicio = datetime.now()

        conexao_origem = DatabaseConfig.from_credentials(credenciais, secao="{tabela["conexao_origem"]}", db_type="sqlserver")
        conexao_destino = DatabaseConfig.from_credentials(credenciais, secao="{tabela["conexao_destino"]}", db_type="sqlserver")

        conexao_origem = spark_facade.Spark(host=conexao_origem.host,
                                        database=conexao_origem.database,
                                        user=conexao_origem.username,
                                        password=conexao_origem.password,
                                        bulk_insert_database="stg",
                                        bulk_insert_credentials=credenciais,
                                        )
        conexao_destino = spark_facade.Spark(host=conexao_destino.host,
                                        database=conexao_destino.database,
                                        user=conexao_destino.username,
                                        password=conexao_destino.password,
                                        bulk_insert_database="dw",
                                        bulk_insert_credentials=credenciais,
                                        )

        conexao_origem.conectar()
        conexao_destino.conectar()

{regra_comentario}        select_campos = [f"{{OVERRIDES_SELECT.get(d, ORIGEM_POR_DESTINO[d])}} AS {{d}}" for d in DESTINOS]
        colunas_update = [
            d for d in DESTINOS
            if d not in COLUNAS_CHAVE and d not in COLUNAS_AUDITORIA
        ]

        select_txt = ",\\n                ".join(select_campos)
        colunas_txt = ",\\n            ".join(DESTINOS)
        valores_txt = ",\\n            ".join(f"S.{{d}}" for d in DESTINOS)
        update_txt = ",\\n            ".join(f"T.{{d}} = S.{{d}}" for d in colunas_update)
        on_txt = " AND ".join(f"T.{{k}} = S.{{k}}" for k in COLUNAS_CHAVE) or "1 = 0 /* TODO-REVISAO: sem chave definida */"

        merge_sql = f"""
        MERGE {tabela["nome"]} AS T
        USING
        (
            SELECT
                {{select_txt}}
            FROM {tabela.get("tabela_sql_origem", tabela["nome"])}
        ) AS S

        ON (
            {{on_txt}}
        )

        WHEN MATCHED THEN
        UPDATE SET
            {{update_txt}},
            T.DT_ATUALIZACAO_SYSTEM = GETDATE(),
            T.version = T.version + 1

        WHEN NOT MATCHED THEN
        INSERT
        (
            {{colunas_txt}}
        )
        VALUES
        (
            {{valores_txt}}
        );
        """

        count = conexao_destino.execute(merge_sql)

        hora_fim = datetime.now()
        logger.info(f"Fim do processamento: {{hora_fim.strftime('%Y-%m-%d %H:%M:%S')}}")
        duracao = hora_fim - hora_inicio
        logger.info(f"Duração: {{duracao}}")

        conexao_origem.desconectar()
        conexao_destino.desconectar()

        validacao = True
        return tabela_origem, validacao, banco_origem, banco_destino, None, hora_inicio, hora_fim, duracao, count

    except Exception as erro:
        logger.error(f"Erro durante o processamento: {{erro}}")
        hora_fim = datetime.now()
        duracao = hora_fim - hora_inicio
        return tabela_origem, validacao, banco_origem, banco_destino, erro, hora_inicio, hora_fim, duracao, count


if __name__ == "__main__":
    from core.logging import LoggerSetup

    log = '{tabela.get("log_name", tabela["nome"])}'
    job = configs.get_job_name(configs.caminho_base.parent)

    job_logger = LoggerSetup(
        projeto="{tabela.get("projeto", "{{PROJETO}}")}",
        caminho=configs.caminho_base.parent.parent,
        job=job
    )
    job_logger = job_logger.setup_logging()
    executar_select_e_update()
'''


def gerar_load_ft(tabela: dict) -> str:
    # A camada FATOS reaproveita a mesma forma da STG (SELECT dinâmico + write overwrite),
    # só que lendo de staging/dimensões e gravando no DW.
    conteudo = gerar_load_stg(tabela)
    aviso = (
        "\n# TODO-REVISAO: se esta tabela de fatos precisar de pós-processamento "
        "(regex/cast em colunas específicas, deleção prévia por competência, joins com "
        "dimensões), adicione manualmente — o gerador não inventa essa lógica.\n"
    )
    # injeta o aviso logo após os imports
    marcador = "logger = logging.getLogger(__name__)\n"
    return conteudo.replace(marcador, marcador + aviso, 1)


GERADORES = {"ORIGEM": gerar_load_stg, "DIMENSOES": gerar_load_dm, "FATOS": gerar_load_ft}


def gerar_orquestrador(spec: dict) -> str:
    tabelas = spec["tabelas"]
    grupo0 = [t["nome"] for t in tabelas if t.get("grupo", 0) == 0]
    grupo1 = [t["nome"] for t in tabelas if t.get("grupo", 0) != 0]

    load_files_txt = "            0: [\n"
    load_files_txt += ",\n".join(f'                "{n}"' for n in grupo0)
    load_files_txt += "\n            ],\n            1: [\n"
    load_files_txt += ",\n".join(f'                "{n}"' for n in grupo1)
    load_files_txt += "\n            ],"

    pbi = spec.get("datasets_powerbi")
    tem_pbi = bool(pbi and pbi.get("datasets"))
    imports_pbi = "from core.api_powerbi import PowerbiRequest as pr\n" if tem_pbi else ""

    if tem_pbi:
        itens = ",\n            ".join(
            f'{{\n                "nome": "{d["nome"]}",\n                "id": "{d["id"]}"\n            }}'
            for d in pbi["datasets"]
        )
        rodape = f'''if __name__ == "__main__":
    credenciais = configs.carregar_credenciais()
    sucesso = main()
    if sucesso:
        logger.info("=" * 100)
        logger.info("SUCESSO NA OPERAÇÃO PRINCIPAL.")
        logger.info("Iniciando atualização dos datasets.")
        logger.info("=" * 100)

        workspace_id = '{pbi.get("workspace", "TODO-REVISAO-workspace-id")}'
        datasets = [
            {itens}
        ]

        pr.update_dataset(credenciais, workspace_id, datasets)
'''
    else:
        rodape = '''if __name__ == "__main__":
    main()
'''

    return f'''import os
import sys
import time
import logging
import importlib
from pathlib import Path
from datetime import datetime

from core.logging import LoggerSetup
from core.log_tables import TableLogs
from core.send_mail import EmailSender
from core.configs import ConfigLoader as configs
from core.connection import DatabaseConfig, Connections
{imports_pbi}
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main() -> bool:
    """ EXECUÇÃO MAIN JOB COMPLETO """
    MAX_TENTATIVAS = 3
    conexao_aux = None
    credenciais = None

    def conectar_aux():
        cfg = DatabaseConfig.from_credentials(credenciais, secao="{{SECAO_CONEXAO_AUX}}", db_type="sqlserver")
        return Connections.create_connection(cfg)

    def registrar_log(func_log, *args):
        """Executa uma função de log do TableLogs, reconectando se a conexão tiver caído."""
        nonlocal conexao_aux
        try:
            func_log(conexao_aux, *args)
        except Exception:
            logger.warning("Conexão com o banco de log inválida, reconectando...")
            try:
                conexao_aux.rollback()
            except Exception:
                pass

            for tentativa in range(3):
                conexao_aux = conectar_aux()
                if conexao_aux is not None:
                    break
                logger.warning(f"Reconexão falhou (tentativa {{tentativa + 1}}/3), aguardando...")
                time.sleep(5)

            if conexao_aux is None:
                raise RuntimeError("Não foi possível reconectar ao banco de log ({{SECAO_CONEXAO_AUX}}) após múltiplas tentativas.")

            func_log(conexao_aux, *args)

    def carregar_modulo(caminho):
        """Carrega um módulo Python a partir do caminho do arquivo."""
        nome = os.path.splitext(os.path.basename(caminho))[0]
        spec = importlib.util.spec_from_file_location(nome, caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo, nome.replace("Load_", "")

    def executar_com_retry(func, tabela_destino, credenciais):
        """Executa a função com retry e envia e-mail em caso de falha."""
        sucesso = False
        tentativas = 0
        resultado = None

        while not sucesso and tentativas < MAX_TENTATIVAS:
            hora_inicio = datetime.now()
            logger.info(f"🟢 Executando executar_select_e_update() de {{tabela_destino}} | Início: {{hora_inicio}}")

            resultado = func()
            tabela_origem, sucesso, banco_origem, banco_destino, erro, data_inicio_tabela, data_fim_tabela, duracao, qtd_registros = resultado
            tentativas += 1

        if not sucesso:
            assunto = f"ERRO Python_Job_{{tabela_destino}} - {{configs.ambienteAtual(credenciais)}}"
            mensagem = (
                f"O processamento do job não foi concluído com sucesso... {{erro}}. "
                f"| {{data_fim_tabela.strftime('%Y-%m-%d %H:%M:%S')}} | "
                f"Duração: | {{data_fim_tabela - data_inicio_tabela}} |."
            )
            EmailSender.enviar_email(assunto, mensagem, credenciais['email'])

        return resultado

    def pipeline_tables(credenciais, job):
        """Função de execução das tabelas"""
        try:
            caminho_tabelas = Path(configs.caminho_base).resolve().parent
            resultado = None

            # Dicionario contendo a ordem e arquivos das tabelas do job
            load_files = {{
{load_files_txt}
            }}
            for tab in configs.recupera_tabelas(caminho_tabelas, load_files):
                modulo, tabela_destino = carregar_modulo(tab)

                if not hasattr(modulo, 'executar_select_e_update'):
                    logger.warning(f"⚠️ Módulo {{tabela_destino}} não possui executar_select_e_update(). Pulando.")
                    continue

                func = modulo.executar_select_e_update

                resultado = executar_com_retry(func, tabela_destino, credenciais)

                tabela_origem, sucesso, banco_origem, banco_destino, erro, data_inicio_tabela, data_fim_tabela, duracao, qtd_registros = resultado

                if tabela_origem:
                    registrar_log(TableLogs.{{TABELA_LOG_ATUALIZACAO}}, tabela_destino, tabela_origem, sucesso, banco_origem, banco_destino, data_inicio_tabela.replace(microsecond=0), data_fim_tabela.replace(microsecond=0), duracao, qtd_registros or 0, data_inicio_tabela.strftime("%d/%m/%Y %H:%M:%S"), data_fim_tabela.strftime("%d/%m/%Y %H:%M:%S"), job)

            return resultado

        except Exception as e:
            logger.error(f"Erro no processo principal de Load: {{e}}")
            raise

    # ------------------------------------------------------------------

    try:
        validacao = False
        hora_inicio = datetime.now()

        credenciais = configs.carregar_credenciais()

        job = configs.get_job_name(configs.caminho_base)
        log = '{spec.get("log_name", spec["job"])}'

        conexao_aux = DatabaseConfig.from_credentials(credenciais, secao="{{SECAO_CONEXAO_AUX}}", db_type="sqlserver")
        conexao_aux = Connections.create_connection(conexao_aux)
        job_logger = LoggerSetup(
            projeto="{spec.get("projeto", "{{PROJETO}}")}",
            caminho=configs.caminho_base.parent,
            job=job
        )

        job_logger = job_logger.setup_logging()

        # ------------ INICIO PROCESSO  ------------

        pipeline_tables(credenciais, job)  # -> pipeline do etl

        hora_fim = datetime.now()

        job_logger.info(f"Fim processamento principal: {{hora_fim}}")

        duracao = hora_fim - hora_inicio
        job_logger.info(f"Duração: {{duracao}}")

        validacao = True
        registrar_log(TableLogs.{{TABELA_LOG_DT}}, validacao, hora_inicio.replace(microsecond=0), log, job)

        return True
    except Exception as e:
        hora_fim = datetime.now()
        logger.error(f'Erro no Main Job {{e}}')

        assunto = f"ERRO {{job}} - {{configs.ambienteAtual(credenciais)}}"
        mensagem = f"O processamento do job não foi concluído com sucesso. \\n{{e}}"

        registrar_log(TableLogs.{{TABELA_LOG_DT}}, validacao, hora_inicio.replace(microsecond=0), log, job)
        EmailSender.enviar_email(assunto, mensagem, credenciais['email'])

        return False


# ====================================================================

{rodape}'''


def _preparar_tabela(t: dict, spec: dict) -> dict:
    """Preenche campos derivados (conexão origem/destino por camada) antes de gerar."""
    t = dict(t)
    conexoes = spec.get("conexoes", {})
    camada = t["camada"]
    if camada == "ORIGEM":
        t.setdefault("conexao_origem", conexoes.get("origem", "{{SECAO_CONEXAO_ORIGEM}}"))
        t.setdefault("conexao_destino", conexoes.get("staging", "{{SECAO_CONEXAO_STAGING}}"))
    elif camada == "DIMENSOES":
        t.setdefault("conexao_origem", conexoes.get("staging", "{{SECAO_CONEXAO_STAGING}}"))
        t.setdefault("conexao_destino", conexoes.get("dw", "{{SECAO_CONEXAO_DW}}"))
    elif camada == "FATOS":
        t.setdefault("conexao_origem", conexoes.get("staging", "{{SECAO_CONEXAO_STAGING}}"))
        t.setdefault("conexao_destino", conexoes.get("dw", "{{SECAO_CONEXAO_DW}}"))
    t.setdefault("log_name", spec.get("log_name", spec["job"]))
    t.setdefault("projeto", spec.get("projeto", "{{PROJETO}}"))
    return t


def gerar_job(spec: dict, out_dir: str, dry_run: bool = False) -> dict:
    """Gera a árvore completa do job. Retorna um resumo {arquivo: 'criado'|'já existe (não sobrescrito)'}."""
    out = Path(out_dir)
    resumo = {}

    def escrever(caminho: Path, conteudo: str):
        rel = str(caminho)
        if caminho.exists():
            resumo[rel] = "já existia — NÃO sobrescrito (gere em pasta separada e diff manualmente se quiser atualizar)"
            return
        resumo[rel] = "criado"
        if not dry_run:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            caminho.write_text(conteudo, encoding="utf-8")

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    gitignore = "logs/\n__pycache__/\n{{PACOTE_CORE_PY}}.egg-info/\n"
    escrever(out / ".gitignore", gitignore)

    for t_raw in spec["tabelas"]:
        t = _preparar_tabela(t_raw, spec)
        camada = t["camada"]
        pasta_camada = out / CAMADA_PASTA[camada]

        campos_json = gerar_campos_json(t.get("campos", []))
        escrever(pasta_camada / "Campos" / _nome_arquivo_json(t["nome"]), campos_json)

        gerador = GERADORES[camada]
        codigo = gerador(t)
        escrever(pasta_camada / f"Load_{t['nome']}.py", codigo)

    orquestrador = gerar_orquestrador(spec)
    escrever(out / f"Python_Job_{spec['job']}.py", orquestrador)

    return resumo


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", help="Caminho do spec.json")
    ap.add_argument("--out-dir", help="Pasta de destino (sobrepõe spec['pasta_destino'])")
    ap.add_argument("--dry-run", action="store_true", help="Não escreve nada, só mostra o que faria")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out_dir = args.out_dir or spec.get("pasta_destino")
    if not out_dir:
        print("Erro: informe --out-dir ou 'pasta_destino' no spec.json", file=sys.stderr)
        sys.exit(1)

    resumo = gerar_job(spec, out_dir, dry_run=args.dry_run)

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Resumo — pasta destino: {out_dir}\n")
    for arquivo, status in sorted(resumo.items()):
        print(f"  [{status:55s}] {arquivo}")
    print(f"\n{sum(1 for s in resumo.values() if s == 'criado')} arquivo(s) criado(s). "
          f"Nenhum comando git foi executado — revise e commite manualmente.")


if __name__ == "__main__":
    main()
