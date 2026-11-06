"""Job de treino do forecast — estrutura com Optuna e MLflow — LH Nautical.

Executado como task Python serverless de um Databricks Job (não localmente).
Cada trial do Optuna é uma run aninhada do MLflow, sob uma run "pai" que
representa o estudo completo. Provado aqui com Ridge (o mais simples dos 4
modelos).
"""

import inspect
import sys
from pathlib import Path

# spark_python_task executa este arquivo via exec(), sem definir __file__.
# O executor guarda o caminho real numa variável local chamada "filename",
# no frame que chama o exec() — subimos a pilha até achá-la.
def _bundle_root() -> Path:
    """Descobre a raiz do bundle subindo os frames até achar o caminho deste arquivo."""
    frame = inspect.currentframe()
    while frame:
        caminho = frame.f_locals.get("filename")
        if caminho and Path(caminho).name == "treino.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")

sys.path.append(str(_bundle_root()))

import argparse

import mlflow
import optuna
from sklearn.linear_model import Ridge
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor

from src.forecast.baseline import calcular_metricas
from src.forecast.data_job import carregar_mart_job
from src.forecast.features import adicionar_encoding_mes, criar_features_temporais, split_temporal

import pandas as pd

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"


def preparar_dados_modelo(treino: pd.DataFrame, validacao: pd.DataFrame, nome_modelo: str):
    """Aplica a imputação/encoding específicos de cada modelo.

    Args:
        treino: DataFrame de treino, ainda com nulos e category_name como texto.
        validacao: DataFrame de validação, no mesmo estado.
        nome_modelo: Um de "ridge", "random_forest", "lightgbm", "catboost".

    Returns:
        Tupla (X_treino, y_treino, X_validacao, y_validacao), já prontos para o modelo.
    """
    treino = treino.copy()
    validacao = validacao.copy()

    if nome_modelo in ("ridge", "random_forest"):
        # Não aceitam nulo nem string: imputa 0 nos numéricos (ausência de lag/rolling
        # vira "sem demanda observada naquela janela") e faz one-hot da categoria,
        # alinhando as colunas da validação às do treino.
        treino[FEATURES_NUMERICAS] = treino[FEATURES_NUMERICAS].fillna(0)
        validacao[FEATURES_NUMERICAS] = validacao[FEATURES_NUMERICAS].fillna(0)

        dummies_treino = pd.get_dummies(treino[COLUNA_CATEGORICA], prefix="cat")
        dummies_validacao = pd.get_dummies(validacao[COLUNA_CATEGORICA], prefix="cat").reindex(
            columns=dummies_treino.columns, fill_value=0
        )

        X_treino = pd.concat(
            [treino[FEATURES_NUMERICAS].reset_index(drop=True), dummies_treino.reset_index(drop=True)], axis=1
        )
        X_validacao = pd.concat(
            [validacao[FEATURES_NUMERICAS].reset_index(drop=True), dummies_validacao.reset_index(drop=True)], axis=1
        )

    elif nome_modelo == "lightgbm":
        # Aceita nulo e categórica nativamente — só precisa do dtype "category",
        # com as mesmas categorias vistas no treino.
        treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].astype("category")
        validacao[COLUNA_CATEGORICA] = pd.Categorical(
            validacao[COLUNA_CATEGORICA], categories=treino[COLUNA_CATEGORICA].cat.categories
        )
        X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        X_validacao = validacao[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]

    elif nome_modelo == "catboost":
        # Aceita nulo nativamente; categórica precisa ser string, não numérica.
        treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
        validacao[COLUNA_CATEGORICA] = validacao[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
        X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        X_validacao = validacao[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]

    else:
        raise ValueError(f"Modelo não reconhecido: {nome_modelo}")

    return X_treino, treino["quantidade_mes"], X_validacao, validacao["quantidade_mes"]

def construir_modelo(nome_modelo: str, trial):
    """Instancia o modelo pedido, com hiperparâmetros sugeridos pelo trial do Optuna.

    Args:
        nome_modelo: Um de "ridge", "random_forest", "lightgbm", "catboost".
        trial: Objeto de trial fornecido pelo Optuna.

    Returns:
        Instância do modelo, ainda não treinada.
    """
    if nome_modelo == "ridge":
        alpha = trial.suggest_float("alpha", 1e-3, 10.0, log=True)
        return Ridge(alpha=alpha)

    if nome_modelo == "random_forest":
        return RandomForestRegressor(
            n_estimators=trial.suggest_int("n_estimators", 100, 400),
            max_depth=trial.suggest_int("max_depth", 3, 15),
            min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 10),
            random_state=42,
        )

    if nome_modelo == "lightgbm":
        return LGBMRegressor(
            n_estimators=trial.suggest_int("n_estimators", 100, 500),
            num_leaves=trial.suggest_int("num_leaves", 15, 127),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            random_state=42,
        )

    if nome_modelo == "catboost":
        return CatBoostRegressor(
            iterations=trial.suggest_int("iterations", 100, 500),
            depth=trial.suggest_int("depth", 4, 10),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            cat_features=[COLUNA_CATEGORICA],
            random_state=42,
            verbose=False,
        )

    raise ValueError(f"Modelo não reconhecido: {nome_modelo}")


def preparar_dados(location_type: str, catalog: str):
    """Carrega a mart e gera as features, sem tratar nulo/categórica — isso é por modelo.

    Args:
        location_type: Tipo de local a filtrar — "store" ou "warehouse".
        catalog: Catálogo Unity Catalog do ambiente atual do bundle ("dev"/"prd").

    Returns:
        Tupla (treino, validacao), DataFrames pandas das combinações maduras,
        ainda com nulos nas colunas de lag/rolling mais longas.
    """
    df = carregar_mart_job(location_type, catalog=catalog)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]

    treino, validacao, _ = split_temporal(df)
    return treino, validacao


def objetivo(trial, nome_modelo: str, treino: pd.DataFrame, validacao: pd.DataFrame):
    """Executa um trial do Optuna: treina o modelo pedido e mede o erro na validação.

    Args:
        trial: Objeto de trial fornecido pelo Optuna.
        nome_modelo: Um de "ridge", "random_forest", "lightgbm", "catboost".
        treino: DataFrame de treino, ainda cru (nulo/categórica tratados aqui dentro).
        validacao: DataFrame de validação, no mesmo estado.

    Returns:
        O MAE do modelo no conjunto de validação (métrica que o Optuna minimiza).
    """
    modelo = construir_modelo(nome_modelo, trial)
    X_treino, y_treino, X_validacao, y_validacao = preparar_dados_modelo(treino, validacao, nome_modelo)

    with mlflow.start_run(nested=True, run_name=f"{nome_modelo}_trial_{trial.number}"):
        modelo.fit(X_treino, y_treino)
        previsao = modelo.predict(X_validacao)

        avaliacao = pd.DataFrame({
            "quantidade_mes": y_validacao.reset_index(drop=True),
            "previsao_baseline": previsao,
        })
        metricas = calcular_metricas(avaliacao)

        mlflow.log_param("modelo", nome_modelo)
        for nome_param, valor in trial.params.items():
            mlflow.log_param(nome_param, valor)
        mlflow.log_metric("mae", metricas["mae"])
        mlflow.log_metric("rmse", metricas["rmse"])
        mlflow.log_metric("mape", metricas["mape"])

    return metricas["mae"]


def main():
    """Roda um estudo Optuna por modelo, para um pipeline, registrando tudo no MLflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    treino, validacao = preparar_dados(args.location_type, catalog=args.catalog)

    mlflow.set_experiment("/Shared/forecast_lh_nautical/treino_modelos")

    for nome_modelo in ["ridge", "random_forest", "lightgbm", "catboost"]:
        with mlflow.start_run(run_name=f"estudo_{args.location_type}_{nome_modelo}"):
            mlflow.log_param("location_type", args.location_type)
            mlflow.log_param("modelo", nome_modelo)
            mlflow.log_param("n_trials", args.n_trials)

            study = optuna.create_study(direction="minimize")
            study.optimize(
                lambda trial: objetivo(trial, nome_modelo, treino, validacao),
                n_trials=args.n_trials,
            )

            mlflow.log_metric("melhor_mae", study.best_value)
            for nome_param, valor in study.best_params.items():
                mlflow.log_param(f"melhor_{nome_param}", valor)

            print(f"[{args.location_type}] {nome_modelo}: melhor MAE = {study.best_value:.4f}")


if __name__ == "__main__":
    main()