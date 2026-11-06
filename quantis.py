"""Quantis de incerteza do modelo final (CatBoost) — LH Nautical.

Treina, para cada pipeline, dois modelos adicionais de CatBoost com função de
perda Quantile — um para o percentil 10 (limite inferior) e outro para o
percentil 90 (limite superior) — usando os mesmos hiperparâmetros e features
do modelo campeão, formando um intervalo de 80% de confiança em torno
da previsão pontual já existente.

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
        if caminho and Path(caminho).name == "quantis.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from mlflow.tracking import MlflowClient

from src.forecast.data_job import carregar_mart_job
from src.forecast.features import adicionar_encoding_mes, criar_features_temporais, split_temporal

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO_MODELOS = "/Shared/forecast_lh_nautical/treino_modelos"
EXPERIMENTO_QUANTIS = "/Shared/forecast_lh_nautical/quantis_incerteza"
QUANTIL_INFERIOR = 0.10
QUANTIL_SUPERIOR = 0.90

def buscar_hiperparametros_selecionados(client: MlflowClient, experimento_id: str, pipeline: str) -> dict:
    """Busca os hiperparâmetros do CatBoost marcado com tag."""
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
    
def preparar_dados_catboost(treino: pd.DataFrame, teste: pd.DataFrame):
    """Aplica o pré-processamento do CatBoost a um par treino/teste."""
    treino = treino.copy()
    teste = teste.copy()
    treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
    teste[COLUNA_CATEGORICA] = teste[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    X_teste = teste[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    return X_treino, treino["quantidade_mes"], X_teste, teste["quantidade_mes"]

def treinar_modelo_quantil(treino: pd.DataFrame, teste: pd.DataFrame, hiperparametros: dict, quantil: float):
    """Treina um CatBoost com função de perda Quantile e retorna as previsões no teste.

    Args:
        treino: DataFrame de treino (combinações com histórico suficiente).
        teste: DataFrame de teste.
        hiperparametros: Hiperparâmetros de estrutura do modelo campeão.
        quantil: Percentil a prever (ex.: 0.10 para o limite inferior).

    Returns:
        Array de previsões do quantil, uma por linha de teste.
    """
    X_treino, y_treino, X_teste, _ = preparar_dados_catboost(treino, teste)

    modelo = CatBoostRegressor(
        **hiperparametros,
        loss_function=f"Quantile:alpha={quantil}",
        cat_features=[COLUNA_CATEGORICA],
        random_state=42,
        verbose=False,
    )
    modelo.fit(X_treino, y_treino)
    return modelo.predict(X_teste)

def calcular_cobertura(y_real: pd.Series, previsao_inferior, previsao_superior) -> float:
    """Calcula a fração de valores reais que caem dentro do intervalo previsto.

    Args:
        y_real: Valores reais observados.
        previsao_inferior: Previsões do limite inferior (percentil 10).
        previsao_superior: Previsões do limite superior (percentil 90).

    Returns:
        Fração (0 a 1) de valores reais dentro do intervalo [inferior, superior].
    """
    dentro_do_intervalo = (y_real.values >= previsao_inferior) & (y_real.values <= previsao_superior)
    return dentro_do_intervalo.mean()

def main():
    """Treina os modelos de quantil para um pipeline e registra cobertura no MLflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    client = MlflowClient()
    experimento_modelos = client.get_experiment_by_name(EXPERIMENTO_MODELOS)
    hiperparametros = buscar_hiperparametros_selecionados(client, experimento_modelos.experiment_id, args.location_type)

    df = carregar_mart_job(args.location_type, catalog=args.catalog)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]

    treino, validacao, teste = split_temporal(df)
    treino_completo = pd.concat([treino, validacao])  # mesma base maior para o modelo final de produção

    previsao_inferior = treinar_modelo_quantil(treino_completo, teste, hiperparametros, QUANTIL_INFERIOR)
    previsao_superior = treinar_modelo_quantil(treino_completo, teste, hiperparametros, QUANTIL_SUPERIOR)

    cobertura = calcular_cobertura(teste["quantidade_mes"], previsao_inferior, previsao_superior)
    largura_media = (previsao_superior - previsao_inferior).mean()

    mlflow.set_experiment(EXPERIMENTO_QUANTIS)
    with mlflow.start_run(run_name=f"quantis_{args.location_type}"):
        mlflow.log_param("location_type", args.location_type)
        mlflow.log_param("quantil_inferior", QUANTIL_INFERIOR)
        mlflow.log_param("quantil_superior", QUANTIL_SUPERIOR)
        mlflow.log_metric("cobertura_real", cobertura)
        mlflow.log_metric("cobertura_esperada", QUANTIL_SUPERIOR - QUANTIL_INFERIOR)
        mlflow.log_metric("largura_media_intervalo", largura_media)

    print(f"Pipeline: {args.location_type}")
    print(f"Cobertura esperada: {QUANTIL_SUPERIOR - QUANTIL_INFERIOR:.0%} | Cobertura real: {cobertura:.1%}")
    print(f"Largura média do intervalo: {largura_media:.2f} unidades")


if __name__ == "__main__":
    main()