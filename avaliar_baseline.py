"""Avaliação da baseline de médias móveis — LH Nautical.

Uso:
    python -m src.forecast.avaliar_baseline --location-type store
    python -m src.forecast.avaliar_baseline --location-type warehouse

Roda a baseline obrigatória sobre o conjunto de teste
(últimos 3 meses, mesmo horizonte do forecast oficial) e registra as
métricas no MLflow, como referência de comparação para os 4 modelos de
regressão.
"""

import argparse

import mlflow

from src.forecast import carregar_mart, criar_features_temporais, split_temporal
from src.forecast.baseline import calcular_metricas, prever_baseline


def main():
    """Executa a baseline de médias móveis para um pipeline e registra no MLflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    args = parser.parse_args()

    df = carregar_mart(args.location_type)
    df = criar_features_temporais(df)

    df_maduras = df[df["historico_suficiente"]]

    _, _, teste = split_temporal(df_maduras)
    teste = prever_baseline(teste)
    metricas = calcular_metricas(teste)

    print(f"Pipeline: {args.location_type}")
    print(f"Linhas no conjunto de teste: {len(teste)}")
    print(metricas)

    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment("/Shared/forecast_lh_nautical/baseline_medias_moveis")
    with mlflow.start_run(run_name=f"baseline_{args.location_type}"):
        mlflow.log_param("location_type", args.location_type)
        mlflow.log_param("modelo", "media_movel_3_meses")
        mlflow.log_metric("mae", metricas["mae"])
        mlflow.log_metric("rmse", metricas["rmse"])
        mlflow.log_metric("mape", metricas["mape"])
        mlflow.log_metric("linhas_excluidas_mape", metricas["linhas_excluidas_mape"])


if __name__ == "__main__":
    main()