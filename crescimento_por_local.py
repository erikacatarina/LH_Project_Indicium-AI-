"""Crescimento de demanda por centro de distribuição e ponto de venda — LH Nautical.

Usa a Janela 3 do backtesting — o modelo prevendo o trimestre mais
recente sem tê-lo visto no treino — como substituto para "o horizonte
previsto", enquanto a previsão de produção
real não está pronta. Mesma metodologia de cálculo de crescimento
será reaplicada com a previsão real.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.crescimento_por_local
"""

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from mlflow.tracking import MlflowClient

from src.forecast import carregar_mart, criar_features_temporais, adicionar_encoding_mes

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO_MODELOS = "/Shared/forecast_lh_nautical/treino_modelos"
N_JANELAS = 3
MESES_TESTE_POR_JANELA = 3


def gerar_janelas_rolling_origin(df: pd.DataFrame, n_janelas=N_JANELAS, meses_teste=MESES_TESTE_POR_JANELA):
    """Mesma lógica de fatiamento — reimplementada aqui de propósito (evita importar
    backtesting.py, que tem um ajuste de sys.path específico para rodar dentro do Job)."""
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
    """Busca os hiperparâmetros do CatBoost marcado como selecionado na tag."""
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
    
def gerar_previsao_janela_3(pipeline: str, client: MlflowClient, experimento_id: str) -> pd.DataFrame:
    """Treina o CatBoost e prevê a Janela 3 (o trimestre mais recente do backtesting), preservando location_id.

    Args:
        pipeline: "store" ou "warehouse".
        client: Cliente do MLflow.
        experimento_id: ID do experimento onde os hiperparâmetros vencedores estão.

    Returns:
        DataFrame com location_id, location_name, product_variant_id, mes_ref,
        quantidade_mes (real) e previsao.
    """
    df = carregar_mart(pipeline)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]

    # mes_ref vem como datetime.date do driver — convertendo cedo evita problemas de
    # comparação/junção mais adiante.
    df["mes_ref"] = pd.to_datetime(df["mes_ref"])

    janelas = gerar_janelas_rolling_origin(df)
    _, treino_janela_3, teste_janela_3 = janelas[2]

    hiperparametros = buscar_hiperparametros_selecionados(client, experimento_id, pipeline)

    treino = treino_janela_3.copy()
    teste = teste_janela_3.copy()
    treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
    teste[COLUNA_CATEGORICA] = teste[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    modelo = CatBoostRegressor(**hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False)
    modelo.fit(treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]], treino["quantidade_mes"])

    resultado = teste[["location_id", "location_name", "product_variant_id", "mes_ref", "quantidade_mes"]].copy()
    resultado["previsao"] = modelo.predict(teste[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]])
    return resultado

def calcular_crescimento_yoy(previsao: pd.DataFrame, pipeline: str) -> pd.DataFrame:
    """Calcula o crescimento YoY por location_id: previsão do trimestre-alvo vs. real do ano anterior.

    Args:
        previsao: DataFrame de gerar_previsao_janela_3, com a previsão da Janela 3.
        pipeline: "store" ou "warehouse" — usado para recarregar o histórico completo.

    Returns:
        DataFrame por location_id, com a demanda prevista, a demanda real do
        mesmo trimestre no ano anterior, e o crescimento percentual.
    """
    previsto_por_local = (
        previsao.groupby(["location_id", "location_name"])["previsao"].sum().reset_index(name="previsto_trimestre")
    )

    meses_alvo = sorted(previsao["mes_ref"].unique())
    meses_ano_anterior = pd.to_datetime([pd.Timestamp(m) - pd.DateOffset(years=1) for m in meses_alvo])

    df_historico = carregar_mart(pipeline)
    df_historico["mes_ref"] = pd.to_datetime(df_historico["mes_ref"])

    real_ano_anterior = (
        df_historico[df_historico["mes_ref"].isin(meses_ano_anterior)]
        .groupby(["location_id", "location_name"])["quantidade_mes"]
        .sum()
        .reset_index(name="real_ano_anterior")
    )

    crescimento = previsto_por_local.merge(real_ano_anterior, on=["location_id", "location_name"], how="left")
    crescimento["crescimento_pct"] = (
        (crescimento["previsto_trimestre"] - crescimento["real_ano_anterior"]) / crescimento["real_ano_anterior"] * 100
    )
    return crescimento.sort_values("crescimento_pct", ascending=False)

def main():
    """Roda a análise de crescimento YoY para os dois pipelines e imprime o ranking."""
    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    for pipeline in ["store", "warehouse"]:
        rotulo = "Ponto de venda" if pipeline == "store" else "Centro de Distribuição"
        print(f"\n=========== {rotulo}s ({pipeline}) ===========")

        previsao = gerar_previsao_janela_3(pipeline, client, experimento.experiment_id)
        crescimento = calcular_crescimento_yoy(previsao, pipeline)

        print(crescimento.to_string(index=False))
        vencedor = crescimento.iloc[0]
        print(f"\n>>> Maior crescimento: {vencedor['location_name']} "
              f"({vencedor['crescimento_pct']:.1f}%)")


if __name__ == "__main__":
    main()