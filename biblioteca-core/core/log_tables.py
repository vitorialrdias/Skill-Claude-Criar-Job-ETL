"""Gravação das tabelas de auditoria. DDL em exemplos/ddl_tabelas_log.sql.

Os nomes dos métodos são os nomes das tabelas ({{TABELA_LOG_ATUALIZACAO}} e {{TABELA_LOG_DT}}),
pois o orquestrador gerado chama TableLogs.<nome_tabela>(conexao, ...).
"""


class TableLogs:
    @staticmethod
    def {{TABELA_LOG_ATUALIZACAO}}(conexao, tabela_destino, tabela_origem, sucesso, banco_origem, banco_destino,
                     data_inicio, data_fim, duracao, qtd_registros, data_inicio_txt, data_fim_txt, job):
        sql = """
            INSERT INTO {{TABELA_LOG_ATUALIZACAO}}
                (JOB, TABELA_DESTINO, TABELA_ORIGEM, SUCESSO, BANCO_ORIGEM, BANCO_DESTINO,
                 DATA_INICIO, DATA_FIM, DURACAO, QTD_REGISTROS, DATA_INICIO_TXT, DATA_FIM_TXT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cur = conexao.cursor()
        cur.execute(sql, (job, tabela_destino, str(tabela_origem), int(bool(sucesso)), banco_origem, banco_destino,
                          data_inicio, data_fim, str(duracao), int(qtd_registros or 0), data_inicio_txt, data_fim_txt))
        conexao.commit()

    @staticmethod
    def {{TABELA_LOG_DT}}(conexao, sucesso, data_inicio, log, job):
        sql = """
            INSERT INTO {{TABELA_LOG_DT}} (JOB, LOG_NAME, SUCESSO, DATA_INICIO, DATA_REGISTRO)
            VALUES (?, ?, ?, ?, GETDATE())
        """
        cur = conexao.cursor()
        cur.execute(sql, (job, log, int(bool(sucesso)), data_inicio))
        conexao.commit()
