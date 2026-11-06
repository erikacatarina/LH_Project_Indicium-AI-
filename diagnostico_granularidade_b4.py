"""Diagnóstico de granularidade e faixa de preço.

Investiga se o MAE/MAPE observado no backtesting está distorcido pela
granularidade fina (product_variant_id) ou concentrado em faixas específicas
de preço — sem fundir nenhum SKU entre si (decisão de negócio: previsão por
SKU é a que orienta reposição de estoque, agregar por product_id perderia
essa informação).

Execução 100% local — reaproveita src.forecast (importável fora do Job) e
reimplementa só a parte específica de janelas/CatBoost, que em
src/forecast/backtesting.py está pensada para rodar dentro do Job.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.diagnostico_granularidade_b4
"""

import os

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from databricks import sql
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

from src.forecast import adicionar_encoding_mes, carregar_mart, criar_features_temporais

load_dotenv(override=True)

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO = "/Shared/forecast_lh_nautical/treino_modelos"
N_JANELAS = 3
MESES_TESTE_POR_JANELA = 3

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


def gerar_janelas_rolling_origin(df: pd.DataFrame, n_janelas=N_JANELAS, meses_teste=MESES_TESTE_POR_JANELA):
    """Mesma lógica de fatiamento — reimplementada aqui de propósito."""
    meses_ordenados = sorted(df["mes_ref"].unique())
    janelas = []
    for numero_janela in range(1, n_janelas + 1):
        deslocamento = n_janelas - numero_janela
        indice_fim_teste = len(meses_ordenados) - 1 - deslocamento
        indice_inicio_teste = indice_fim_teste - meses_teste + 1
        meses_teste_janela = meses_ordenados[indice_inicio_teste : indice_fim_teste + 1]
        mes_fim_treino = meses_ordenados[indice_inicio_teste - 1]

        treino = df[df["mes_ref"] <= mes_fim_treino]
        teste = df[df["mes_ref"].isin(meses_teste_janela)]
        janelas.append((numero_janela, treino, teste))
    return janelas


def buscar_hiperparametros_selecionados(client: MlflowClient, experimento_id: str, pipeline: str) -> dict:
    """Busca os hiperparâmetros do CatBoost marcado como selecionado."""
    runs = client.search_runs(
        experiment_ids=[experimento_id],
        filter_string=f"tags.mlflow.runName = 'estudo_{pipeline}_catboost' and tags.selecionado_b3 = 'true'",
    )
    if not runs:
        raise RuntimeError(f"Nenhuma run selecionada encontrada para {pipeline}/catboost.")
    params = runs[0].data.params
    return {
        "iterations": int(params["melhor_iterations"]),
        "depth": int(params["melhor_depth"]),
        "learning_rate": float(params["melhor_learning_rate"]),
    }


def treinar_e_prever(treino: pd.DataFrame, teste: pd.DataFrame, hiperparametros: dict) -> pd.DataFrame:
    """Treina o CatBoost e retorna as previsões linha a linha (não só a métrica agregada).

    Args:
        treino: DataFrame de treino da janela.
        teste: DataFrame de teste da janela.
        hiperparametros: Hiperparâmetros já tunados.

    Returns:
        DataFrame com product_variant_id, mes_ref, quantidade_mes (real) e previsao.
    """
    treino = treino.copy()
    teste = teste.copy()
    treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
    teste[COLUNA_CATEGORICA] = teste[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    modelo = CatBoostRegressor(
        **hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False
    )
    modelo.fit(treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]], treino["quantidade_mes"])
    previsao = modelo.predict(teste[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]])

    resultado = teste[["product_variant_id", "mes_ref", "quantidade_mes"]].copy()
    resultado["previsao"] = previsao
    return resultado


def calcular_metricas_segmentadas(previsoes: pd.DataFrame, precos: pd.DataFrame) -> pd.DataFrame:
    """Calcula MAE, MAE em R$ e MAPE ponderado por volume, por faixa de preço.

    Args:
        previsoes: DataFrame com product_variant_id, quantidade_mes, previsao.
        precos: DataFrame com product_variant_id, sale_price.

    Returns:
        DataFrame com uma linha por faixa de preço e as métricas de cada uma.
    """
    df = previsoes.merge(precos, on="product_variant_id", how="left")
    df["erro_abs"] = (df["quantidade_mes"] - df["previsao"]).abs()
    df["erro_reais"] = df["erro_abs"] * df["sale_price"]

    df["faixa_preco"] = pd.qcut(df["sale_price"], q=3, labels=["baixo_ticket", "medio_ticket", "alto_ticket"])

    linhas = []
    for faixa, grupo in df.groupby("faixa_preco", observed=True):
        mape_ponderado = grupo["erro_abs"].sum() / grupo["quantidade_mes"].abs().sum() * 100
        linhas.append({
            "faixa_preco": faixa,
            "n_linhas": len(grupo),
            "mae_unidades": grupo["erro_abs"].mean(),
            "mae_reais": grupo["erro_reais"].mean(),
            "mape_ponderado": mape_ponderado,
        })
    return pd.DataFrame(linhas)


def main():
    """Roda o diagnóstico de granularidade/preço para os dois pipelines, todas as janelas."""
    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO)

    for pipeline in ["store", "warehouse"]:
        print(f"\n=========== {pipeline} ===========")

        df = carregar_mart(pipeline)
        df = criar_features_temporais(df)
        df = adicionar_encoding_mes(df)
        df = df[df["historico_suficiente"]]

        precos = run_query("SELECT DISTINCT product_variant_id, sale_price FROM dim_produtos")
        # sale_price vem como decimal.Decimal do databricks-sql-connector (coluna DECIMAL no
        # warehouse) — sem essa conversão, multiplicar por um float (erro_abs) quebra com
        # TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'.
        precos["sale_price"] = precos["sale_price"].astype(float)

        hiperparametros = buscar_hiperparametros_selecionados(client, experimento.experiment_id, pipeline)

        for numero_janela, treino, teste in gerar_janelas_rolling_origin(df):
            previsoes = treinar_e_prever(treino, teste, hiperparametros)

            # MAPE ponderado por volume, no pipeline inteiro
            erro_abs = (previsoes["quantidade_mes"] - previsoes["previsao"]).abs()
            mape_ponderado_geral = erro_abs.sum() / previsoes["quantidade_mes"].abs().sum() * 100

            print(f"\n--- Janela {numero_janela} ---")
            print(f"MAPE ponderado por volume (pipeline inteiro): {mape_ponderado_geral:.2f}%")

            tabela_segmentada = calcular_metricas_segmentadas(previsoes, precos)
            print(tabela_segmentada.to_string(index=False))


if __name__ == "__main__":
    main()
