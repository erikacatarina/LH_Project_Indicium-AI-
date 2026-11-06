"""Backtesting rolling-origin do modelo final (CatBoost) — LH Nautical.

Executado como task Python serverless de um Databricks Job. Reaproveita a
estrutura de conexão/sys.path já validada.
"""

import inspect
import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Descobre a raiz do bundle subindo os frames até achar o caminho deste arquivo."""
    frame = inspect.currentframe()
    while frame:
        caminho = frame.f_locals.get("filename")
        if caminho and Path(caminho).name == "backtesting.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import mlflow
import pandas as pd
from catboost import CatBoostRegressor

from src.forecast.baseline import calcular_metricas
from src.forecast.data_job import carregar_mart_job
from src.forecast.features import adicionar_encoding_mes, criar_features_temporais

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
N_JANELAS = 3
MESES_TESTE_POR_JANELA = 3


def gerar_janelas_rolling_origin(df: pd.DataFrame, n_janelas: int = N_JANELAS, meses_teste: int = MESES_TESTE_POR_JANELA):
    """Gera janelas de treino/teste, cada uma testando um bloco de meses mais recente que a anterior.

    Args:
        df: DataFrame com a coluna mes_ref.
        n_janelas: Quantidade de janelas a gerar.
        meses_teste: Tamanho fixo (em meses) do bloco de teste de cada janela.

    Returns:
        Lista de tuplas (numero_da_janela, treino, teste), da mais antiga para a mais recente.
    """
    meses_ordenados = sorted(df["mes_ref"].unique())
    janelas = []

    for numero_janela in range(1, n_janelas + 1):
        # deslocamento: quantos meses o fim do teste desta janela fica ANTES do fim do dataset.
        # janela 1 (mais antiga) tem o maior deslocamento; a última janela tem deslocamento 0
        # (ou seja, termina no último mês disponível — a mesma janela que a já usaram).
        deslocamento = n_janelas - numero_janela
        indice_fim_teste = len(meses_ordenados) - 1 - deslocamento
        indice_inicio_teste = indice_fim_teste - meses_teste + 1

        meses_teste_janela = meses_ordenados[indice_inicio_teste : indice_fim_teste + 1]
        mes_fim_treino = meses_ordenados[indice_inicio_teste - 1]

        treino = df[df["mes_ref"] <= mes_fim_treino]
        teste = df[df["mes_ref"].isin(meses_teste_janela)]

        janelas.append((numero_janela, treino, teste))

    return janelas

def preparar_dados_catboost(treino: pd.DataFrame, teste: pd.DataFrame):
    """Aplica o pré-processamento do CatBoost a um par treino/teste.

    Args:
        treino: DataFrame de treino da janela.
        teste: DataFrame de teste da janela.

    Returns:
        Tupla (X_treino, y_treino, X_teste, y_teste).
    """
    treino = treino.copy()
    teste = teste.copy()

    treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
    teste[COLUNA_CATEGORICA] = teste[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)

    X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    X_teste = teste[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
    return X_treino, treino["quantidade_mes"], X_teste, teste["quantidade_mes"]


def rodar_janela(numero_janela: int, treino: pd.DataFrame, teste: pd.DataFrame, melhores_hiperparametros: dict) -> dict:
    """Treina o CatBoost numa janela e mede o erro no teste correspondente.

    Args:
        numero_janela: Identificador da janela (1, 2 ou 3).
        treino: DataFrame de treino da janela.
        teste: DataFrame de teste da janela.
        melhores_hiperparametros: Hiperparâmetros já tunados.

    Returns:
        Dicionário com numero_janela, mae, rmse e mape.
    """
    X_treino, y_treino, X_teste, y_teste = preparar_dados_catboost(treino, teste)

    modelo = CatBoostRegressor(
        **melhores_hiperparametros,
        cat_features=[COLUNA_CATEGORICA],
        random_state=42,
        verbose=False,
    )
    modelo.fit(X_treino, y_treino)
    previsao = modelo.predict(X_teste)

    avaliacao = pd.DataFrame({
        "quantidade_mes": y_teste.reset_index(drop=True),
        "previsao_baseline": previsao,
    })
    metricas = calcular_metricas(avaliacao)
    return {"numero_janela": numero_janela, **metricas}

from mlflow.tracking import MlflowClient

EXPERIMENTO = "/Shared/forecast_lh_nautical/treino_modelos"


def buscar_hiperparametros_selecionados(client: MlflowClient, experimento_id: str, pipeline: str) -> dict:
    """Busca os hiperparâmetros do CatBoost marcado como selecionado, para um pipeline.

    Args:
        client: Cliente do MLflow.
        experimento_id: ID do experimento onde a registrou a tag.
        pipeline: "store" ou "warehouse".

    Returns:
        Dicionário de hiperparâmetros prontos para instanciar o CatBoostRegressor.

    Raises:
        RuntimeError: se nenhuma run com a tag selecionado_b3 for encontrada para o pipeline.
    """
    runs = client.search_runs(
        experiment_ids=[experimento_id],
        filter_string=(
            f"tags.mlflow.runName = 'estudo_{pipeline}_catboost' and tags.selecionado_b3 = 'true'"
        ),
    )
    if not runs:
        raise RuntimeError(f"Nenhuma run selecionada encontrada para {pipeline}/catboost.")

    params = runs[0].data.params
    return {
        "iterations": int(params["melhor_iterations"]),
        "depth": int(params["melhor_depth"]),
        "learning_rate": float(params["melhor_learning_rate"]),
    }


def main():
    """Roda o backtesting rolling-origin do CatBoost para um pipeline, registrando cada janela no MLflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO)
    hiperparametros = buscar_hiperparametros_selecionados(client, experimento.experiment_id, args.location_type)

    df = carregar_mart_job(args.location_type, catalog=args.catalog)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]

    janelas = gerar_janelas_rolling_origin(df)

    mlflow.set_experiment("/Shared/forecast_lh_nautical/backtesting_rolling_origin")
    with mlflow.start_run(run_name=f"backtesting_{args.location_type}_catboost"):
        mlflow.log_params(hiperparametros)
        resultados = []
        for numero_janela, treino, teste in janelas:
            resultado = rodar_janela(numero_janela, treino, teste, hiperparametros)
            resultados.append(resultado)
            mlflow.log_metric(f"mae_janela_{numero_janela}", resultado["mae"])
            mlflow.log_metric(f"rmse_janela_{numero_janela}", resultado["rmse"])
            mlflow.log_metric(f"mape_janela_{numero_janela}", resultado["mape"])
            print(f"Janela {numero_janela}: MAE={resultado['mae']:.3f} RMSE={resultado['rmse']:.3f} MAPE={resultado['mape']:.2f}%")

        maes = [r["mae"] for r in resultados]
        media_mae = sum(maes) / len(maes)
        desvio_mae = pd.Series(maes).std()
        mlflow.log_metric("mae_medio_janelas", media_mae)
        mlflow.log_metric("mae_desvio_janelas", desvio_mae)

        print(f"\nMAE médio entre janelas: {media_mae:.3f} (desvio: {desvio_mae:.3f})")


if __name__ == "__main__":
    main()