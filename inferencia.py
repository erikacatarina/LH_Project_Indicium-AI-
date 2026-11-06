"""Inferência de produção: previsão recursiva de 3 meses + quantis — LH Nautical.

Carrega o modelo campeão (Unity Catalog Model Registry, alias "champion"),
gera a previsão dos 3 meses seguintes ao último mês real disponível na mart
(MAX(mes_ref) — já reflete a quarentena aplicada, sem precisar de lógica
adicional de data), com quantis de incerteza (p10/p90), e escreve a tabela
Gold de previsões.

Executado como task Python serverless de um Databricks Job.
"""

import inspect
import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Descobre a raiz do bundle subindo os frames até achar o caminho deste arquivo."""
    frame = inspect.currentframe()
    while frame:
        caminho = frame.f_locals.get("filename")
        if caminho and Path(caminho).name == "inferencia.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from dateutil.relativedelta import relativedelta
from mlflow.tracking import MlflowClient

from src.forecast.data_job import carregar_mart_job
from src.forecast.features import adicionar_encoding_mes, criar_features_temporais

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO_MODELOS = "/Shared/forecast_lh_nautical/treino_modelos"
QUANTIL_INFERIOR = 0.10
QUANTIL_SUPERIOR = 0.90
HORIZONTE_MESES = 3

def carregar_modelo_campeao(catalog: str, pipeline: str) -> CatBoostRegressor:
    """Carrega o modelo campeão via alias 'champion' do Unity Catalog."""
    mlflow.set_registry_uri("databricks-uc")
    nome_modelo = f"{catalog}.gold.forecast_{pipeline}_catboost"
    return mlflow.catboost.load_model(f"models:/{nome_modelo}@champion")


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


def treinar_modelos_quantil(df_treino: pd.DataFrame, hiperparametros: dict):
    """Treina os modelos de quantil (p10/p90), mesma lógica já validada."""
    X_treino = df_treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    y_treino = df_treino["quantidade_mes"]

    modelo_p10 = CatBoostRegressor(
        **hiperparametros, loss_function=f"Quantile:alpha={QUANTIL_INFERIOR}",
        cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False,
    )
    modelo_p10.fit(X_treino, y_treino)

    modelo_p90 = CatBoostRegressor(
        **hiperparametros, loss_function=f"Quantile:alpha={QUANTIL_SUPERIOR}",
        cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False,
    )
    modelo_p90.fit(X_treino, y_treino)

    return modelo_p10, modelo_p90


def gerar_previsao_recursiva(pipeline: str, catalog: str, modelo_pontual, modelo_p10, modelo_p90) -> pd.DataFrame:
    """Gera a previsão recursiva dos HORIZONTE_MESES seguintes ao último mês real da mart.

    Args:
        pipeline: "store" ou "warehouse".
        catalog: Catálogo do ambiente atual do bundle.
        modelo_pontual, modelo_p10, modelo_p90: Modelos já treinados/carregados.

    Returns:
        DataFrame com uma linha por combinação × mês futuro, com previsão
        pontual e os dois quantis.
    """
    df = carregar_mart_job(pipeline, catalog=catalog)
    df = df[df["historico_suficiente"]].copy()
    df["mes_ref"] = pd.to_datetime(df["mes_ref"])  # mesmo cuidado já necessário em tarefas anteriores

    data_referencia = df["mes_ref"].max()
    meses_futuros = [data_referencia + relativedelta(months=i) for i in range(1, HORIZONTE_MESES + 1)]

    colunas_combinacao = ["product_variant_id", "location_id", "category_name", "location_name", "product_name", "location_type"]
    combinacoes = df[colunas_combinacao].drop_duplicates()

    historico_estendido = df.copy()
    previsoes_finais = []

    for mes_futuro in meses_futuros:
        linhas_futuras = combinacoes.copy()
        linhas_futuras["mes_ref"] = mes_futuro
        linhas_futuras["ano"] = mes_futuro.year
        linhas_futuras["mes"] = mes_futuro.month
        linhas_futuras["quantidade_mes"] = pd.NA
        linhas_futuras["historico_suficiente"] = True

        base_temporaria = pd.concat([historico_estendido, linhas_futuras], ignore_index=True)
        base_temporaria = criar_features_temporais(base_temporaria)
        base_temporaria = adicionar_encoding_mes(base_temporaria)

        linhas_prever = base_temporaria[base_temporaria["mes_ref"] == mes_futuro].copy()
        linhas_prever[COLUNA_CATEGORICA] = linhas_prever[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

        X = linhas_prever[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        linhas_prever["previsao_pontual"] = modelo_pontual.predict(X)
        linhas_prever["previsao_p10"] = modelo_p10.predict(X)
        linhas_prever["previsao_p90"] = modelo_p90.predict(X)

        previsoes_finais.append(
            linhas_prever[colunas_combinacao + ["mes_ref", "previsao_pontual", "previsao_p10", "previsao_p90"]]
        )

        # A previsão pontual deste mês vira "histórico" para calcular os lags do próximo —
        # é isso que torna a previsão recursiva (multi-step), não uma chamada única ao modelo.
        linha_para_historico = linhas_prever.copy()
        linha_para_historico["quantidade_mes"] = linha_para_historico["previsao_pontual"]
        colunas_historico = [c for c in historico_estendido.columns if c in linha_para_historico.columns]
        historico_estendido = pd.concat(
            [historico_estendido, linha_para_historico[colunas_historico]], ignore_index=True
        )

    return pd.concat(previsoes_finais, ignore_index=True)


def main():
    """Roda a inferência de produção e escreve a tabela Gold de previsões."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    modelo_pontual = carregar_modelo_campeao(args.catalog, args.location_type)

    df_treino_quantis = carregar_mart_job(args.location_type, catalog=args.catalog)
    df_treino_quantis = criar_features_temporais(df_treino_quantis)
    df_treino_quantis = adicionar_encoding_mes(df_treino_quantis)
    df_treino_quantis = df_treino_quantis[df_treino_quantis["historico_suficiente"]].copy()
    df_treino_quantis[COLUNA_CATEGORICA] = df_treino_quantis[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    hiperparametros = buscar_hiperparametros_selecionados(client, experimento.experiment_id, args.location_type)
    modelo_p10, modelo_p90 = treinar_modelos_quantil(df_treino_quantis, hiperparametros)

    previsao = gerar_previsao_recursiva(args.location_type, args.catalog, modelo_pontual, modelo_p10, modelo_p90)
    previsao["data_geracao"] = pd.Timestamp.now()
    previsao["modelo_utilizado"] = "catboost"

    from databricks.sdk.runtime import spark
    spark_df = spark.createDataFrame(previsao)

    tabela_destino = f"{args.catalog}.gold.fct_previsao_demanda"
    tabela_ja_existe = spark.catalog.tableExists(tabela_destino)

    escritor = spark_df.write.mode("overwrite").partitionBy("location_type")
    if tabela_ja_existe:
        escritor = escritor.option("replaceWhere", f"location_type = '{args.location_type}'")

    escritor.saveAsTable(tabela_destino)

    print(f"Previsão gravada: {len(previsao)} linhas, pipeline {args.location_type}, "
          f"meses {sorted(previsao['mes_ref'].dt.strftime('%Y-%m').unique())}")


if __name__ == "__main__":
    main()