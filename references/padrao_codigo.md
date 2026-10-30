# Padrão de código — <nome do projeto>

> Fonte da verdade do código gerado. Descreva o que já existe nos jobs reais, não o ideal.

## 1. Árvore de pastas
```
Job_<Nome>/<NOME_PASTA>/
  .gitignore
  Python_Job_<Nome>.py        # orquestrador
  <CAMADA_1>/Load_<PREFIXO>_<TABELA>.py + Campos/*.json
  <CAMADA_2>/...
```

## 2. Biblioteca compartilhada
<Módulos e o que cada um faz: credenciais, conexão, log, e-mail, auditoria, BI.>

## 3. Contrato entre arquivos e orquestrador
```python
return <campo1>, <campo2>, ...   # ordem e quantidade fixas
```

## 4. Orquestrador
<Ordem de execução, retry, logs, alertas, gatilhos finais.>

## 5–7. Um arquivo por camada
<O que cada Load_* lê, transforma e grava; onde ficam os overrides; MERGE/chaves.>

## 8. Formato de `Campos/*.json`
```json
[{ "origem": "COL", "destino": "COL", "tipo": "nvarchar", "tamanho": "-1" }]
```

## 9. O que NÃO fazer
- Não commitar, não mexer em credenciais, não inventar regra de negócio (use `# TODO-REVISAO`).
