"""Confirma quais meses caem em cada janela de teste do backtesting.

Reimplementação local, só da lógica de fatiamento de meses — sem importar
src/forecast/backtesting.py, que tem um ajuste de sys.path específico para
rodar dentro do Job. Se a lógica de janelas mudar lá, replicar aqui.
"""

import os

import pandas as pd
from databricks import sql
from dotenv import load_dotenv

load_dotenv(override=True)

connection = sql.connect(
    server_hostname=os.environ["DATABRICKS_HOST"],
    http_path=os.environ["DATABRICKS_HTTP_PATH"],
    access_token=os.environ["DATABRICKS_TOKEN"],
    catalog=os.environ.get("DATABRICKS_CATALOG", "dev"),
    schema="gold",
)


def run_query(query: str) -> pd.DataFrame:
    """Executa uma query no SQL Warehouse e retorna um DataFrame pandas."""
    with connection.cursor() as cursor:
        cursor.execute(query)
        if cursor.description is None:
            return pd.DataFrame()
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return pd.DataFrame(rows, columns=columns)


def gerar_janelas_rolling_origin(meses_ordenados, n_janelas=3, meses_teste=3):
    """Mesma lógica de fatiamento — reimplementada aqui de propósito (ver docstring do módulo).

    Args:
        meses_ordenados: Lista de datas (mes_ref) já ordenadas cronologicamente.
        n_janelas: Quantidade de janelas a gerar.
        meses_teste: Tamanho fixo (em meses) do bloco de teste de cada janela.

    Returns:
        Lista de tuplas (numero_da_janela, lista_de_meses_de_teste).
    """
    janelas = []
    for numero_janela in range(1, n_janelas + 1):
        deslocamento = n_janelas - numero_janela
        indice_fim_teste = len(meses_ordenados) - 1 - deslocamento
        indice_inicio_teste = indice_fim_teste - meses_teste + 1
        meses_teste_janela = meses_ordenados[indice_inicio_teste : indice_fim_teste + 1]
        janelas.append((numero_janela, meses_teste_janela))
    return janelas


for pipeline in ["store", "warehouse"]:
    df = run_query(f"""
        SELECT DISTINCT mes_ref
        FROM fct_demanda_mensal_produto_local
        WHERE location_type = '{pipeline}' AND historico_suficiente = true
        ORDER BY mes_ref
    """)
    meses_ordenados = sorted(df["mes_ref"].tolist())
    janelas = gerar_janelas_rolling_origin(meses_ordenados)

    print(f"\n=== {pipeline} ===")
    for numero_janela, meses in janelas:
        resumo = ", ".join(
            f"{m.strftime('%Y-%m')} ({'ALTA TEMPORADA' if m.month in (12, 1, 2, 3) else 'baixa temporada'})"
            for m in meses
        )
        print(f"Janela {numero_janela}: {resumo}")
