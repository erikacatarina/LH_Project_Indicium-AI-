"""Treino condicional do modelo campeão, com registro no Model Registry — LH Nautical.

Retreina o CatBoost campeão mensalmente e registra a versão no Unity
Catalog Model Registry, com alias "champion".

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
        if caminho and Path(caminho).name == "treino_condicional.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import mlflow
from catboost import CatBoostRegressor
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


from mlflow.models import infer_signature


def treinar_modelo_final(pipeline: str, catalog: str, hiperparametros: dict):
    """Treina o CatBoost campeão com todo o histórico disponível (combinações maduras).

    Returns:
        Tupla (modelo treinado, DataFrame de features usado no treino) — o
        segundo item serve só para inferir a assinatura do modelo, exigida
        pelo Unity Catalog Model Registry.
    """
    df = carregar_mart_job(pipeline, catalog=catalog)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]
    df[COLUNA_CATEGORICA] = df[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    X = df[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    y = df["quantidade_mes"]

    modelo = CatBoostRegressor(**hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False)
    modelo.fit(X, y)
    return modelo, X


def main():
    """Treina o modelo campeão e registra no Unity Catalog Model Registry, com alias 'champion'."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")

    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)
    hiperparametros = buscar_hiperparametros_selecionados(client, experimento.experiment_id, args.location_type)

    modelo, X_treino = treinar_modelo_final(args.location_type, args.catalog, hiperparametros)

    nome_modelo_registrado = f"{args.catalog}.gold.forecast_{args.location_type}_catboost"

    # Unity Catalog exige assinatura de entrada/saída para registrar um modelo — uma amostra
    # pequena basta, já que a assinatura só precisa da estrutura (nomes/tipos), não do dado inteiro.
    amostra_entrada = X_treino.head(5)
    amostra_saida = modelo.predict(amostra_entrada)
    assinatura = infer_signature(amostra_entrada, amostra_saida)

    # Define o experimento ativo — sem isso, start_run tenta usar experiment_id=None
    # e falha com RESOURCE_DOES_NOT_EXIST.
    mlflow.set_experiment(EXPERIMENTO_MODELOS)
    with mlflow.start_run(run_name=f"treino_final_{args.location_type}"):
        mlflow.log_params(hiperparametros)
        info_modelo = mlflow.catboost.log_model(
            modelo, "modelo",
            registered_model_name=nome_modelo_registrado,
            signature=assinatura,
            input_example=amostra_entrada,
        )

    nova_versao = info_modelo.registered_model_version
    client.set_registered_model_alias(nome_modelo_registrado, "champion", nova_versao)

    print(f"Modelo registrado: {nome_modelo_registrado}, versão {nova_versao}, alias 'champion'")


if __name__ == "__main__":
    main()