"""Validação direcionada em janela de alta temporada histórica — LH Nautical.

Testa se a vantagem do modelo sobre a baseline é maior num trimestre de
alta temporada já ocorrido no passado — dado real, não futuro, não fere
a quarentena aplicada à mart.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.validacao_alta_temporada
"""

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from mlflow.tracking import MlflowClient

from src.forecast import carregar_mart, criar_features_temporais, adicionar_encoding_mes
from src.forecast.baseline import calcular_metricas, prever_baseline

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO_MODELOS = "/Shared/forecast_lh_nautical/treino_modelos"

# 👇 ajustar conforme o Passo 3.1 confirmar a janela disponível
MES_FIM_TREINO = "2024-12-01"
MESES_ALTA_TEMPORADA_TESTE = ["2025-12-01", "2026-01-01", "2026-02-01"]


def buscar_hiperparametros_selecionados(client: MlflowClient, experimento_id: str, pipeline: str) -> dict:
    """Busca os hiperparâmetros do CatBoost marcado como selecionado no MLflow para o pipeline dado."""
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


def validar_janela_alta_temporada(pipeline: str, client: MlflowClient, experimento_id: str) -> dict:
    """Treina até MES_FIM_TREINO, prevê a janela de alta temporada, e compara modelo vs. baseline."""
    df = carregar_mart(pipeline)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]

    # mes_ref vem do databricks-sql-connector como datetime.date (coluna DATE do warehouse) —
    # comparar direto com uma string ("2024-11-01") quebra com TypeError. Convertendo os dois
    # lados para pandas Timestamp aqui resolve de forma consistente.
    df["mes_ref"] = pd.to_datetime(df["mes_ref"])
    mes_fim_treino = pd.Timestamp(MES_FIM_TREINO)
    meses_teste = pd.to_datetime(MESES_ALTA_TEMPORADA_TESTE)

    treino = df[df["mes_ref"] <= mes_fim_treino].copy()
    teste = df[df["mes_ref"].isin(meses_teste)].copy()

    if teste.empty:
        raise RuntimeError(
            f"Nenhuma linha encontrada para {MESES_ALTA_TEMPORADA_TESTE} — "
            "confirme a janela disponível no antes de rodar."
        )

    treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
    teste[COLUNA_CATEGORICA] = teste[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    hiperparametros = buscar_hiperparametros_selecionados(client, experimento_id, pipeline)
    modelo = CatBoostRegressor(**hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False)
    modelo.fit(treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]], treino["quantidade_mes"])

    avaliacao_modelo = teste[["quantidade_mes"]].copy()
    avaliacao_modelo["previsao_baseline"] = modelo.predict(teste[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]])
    metricas_modelo = calcular_metricas(avaliacao_modelo)

    avaliacao_baseline = prever_baseline(teste)
    metricas_baseline = calcular_metricas(avaliacao_baseline)

    ganho_pct = (metricas_baseline["mae"] - metricas_modelo["mae"]) / metricas_baseline["mae"] * 100

    return {
        "pipeline": pipeline,
        "mae_modelo": metricas_modelo["mae"],
        "mae_baseline": metricas_baseline["mae"],
        "ganho_pct": ganho_pct,
        "n_linhas_teste": len(teste),
    }


def main():
    """Roda a validação direcionada para os dois pipelines e imprime a comparação."""
    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    print(f"Janela de alta temporada testada: {MESES_ALTA_TEMPORADA_TESTE}")
    print(f"Treino até: {MES_FIM_TREINO}\n")

    for pipeline in ["store", "warehouse"]:
        resultado = validar_janela_alta_temporada(pipeline, client, experimento.experiment_id)
        print(f"[{pipeline}] MAE modelo={resultado['mae_modelo']:.3f} | "
              f"MAE baseline={resultado['mae_baseline']:.3f} | "
              f"Ganho={resultado['ganho_pct']:.1f}% | "
              f"({resultado['n_linhas_teste']} linhas de teste)")


if __name__ == "__main__":
    main()