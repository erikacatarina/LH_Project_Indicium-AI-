"""Diagnósticos de premissas dos algoritmos - LH Nautical.

Verifica, com dado real, as premissas do escopo exige
documentar no Model Card: multicolinearidade (Ridge/Lasso), overfitting e
distribuição de resíduos (Random Forest, LightGBM, CatBoost).

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
        if caminho and Path(caminho).name == "diagnosticos_premissas.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import mlflow
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from statsmodels.stats.outliers_influence import variance_inflation_factor

from src.forecast.baseline import calcular_metricas
from src.forecast.data_job import carregar_mart_job
from src.forecast.features import adicionar_encoding_mes, criar_features_temporais, split_temporal

FEATURES_NUMERICAS = [
    "lag_1", "lag_2", "lag_3", "lag_12",
    "rolling_mean_3", "rolling_std_3", "rolling_mean_6", "rolling_std_6",
    "mes_sin", "mes_cos",
]
COLUNA_CATEGORICA = "category_name"
EXPERIMENTO_MODELOS = "/Shared/forecast_lh_nautical/treino_modelos"
EXPERIMENTO_PREMISSAS = "/Shared/forecast_lh_nautical/premissas_b6"

def calcular_vif(df: pd.DataFrame, features: list) -> pd.DataFrame:
    """Calcula o VIF de cada feature numérica.

    Args:
        df: DataFrame contendo as features (sem nulos — VIF não aceita nulo).
        features: Lista de colunas numéricas a avaliar.

    Returns:
        DataFrame com uma linha por feature e seu VIF.
    """
    dados = df[features].dropna()
    resultado = pd.DataFrame({
        "feature": features,
        "vif": [variance_inflation_factor(dados.values, i) for i in range(len(features))],
    })
    return resultado.sort_values("vif", ascending=False)

def avaliar_overfitting(nome_modelo: str, treino: pd.DataFrame, validacao: pd.DataFrame, hiperparametros: dict) -> dict:
    """Treina um modelo e mede o MAE tanto no treino quanto na validação.

    Args:
        nome_modelo: "random_forest", "lightgbm" ou "catboost".
        treino: DataFrame de treino.
        validacao: DataFrame de validação.
        hiperparametros: Hiperparâmetros já vencedores, sem retunar.

    Returns:
        Dicionário com mae_treino, mae_validacao e gap (validação − treino).
    """
    treino = treino.copy()
    validacao = validacao.copy()

    if nome_modelo == "random_forest":
        treino[FEATURES_NUMERICAS] = treino[FEATURES_NUMERICAS].fillna(0)
        validacao[FEATURES_NUMERICAS] = validacao[FEATURES_NUMERICAS].fillna(0)
        dummies_treino = pd.get_dummies(treino[COLUNA_CATEGORICA], prefix="cat")
        dummies_validacao = pd.get_dummies(validacao[COLUNA_CATEGORICA], prefix="cat").reindex(
            columns=dummies_treino.columns, fill_value=0
        )
        X_treino = pd.concat([treino[FEATURES_NUMERICAS].reset_index(drop=True), dummies_treino.reset_index(drop=True)], axis=1)
        X_validacao = pd.concat([validacao[FEATURES_NUMERICAS].reset_index(drop=True), dummies_validacao.reset_index(drop=True)], axis=1)
        modelo = RandomForestRegressor(**hiperparametros, random_state=42)

    elif nome_modelo == "lightgbm":
        treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].astype("category")
        validacao[COLUNA_CATEGORICA] = pd.Categorical(validacao[COLUNA_CATEGORICA], categories=treino[COLUNA_CATEGORICA].cat.categories)
        X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        X_validacao = validacao[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        modelo = LGBMRegressor(**hiperparametros, random_state=42)

    elif nome_modelo == "catboost":
        treino[COLUNA_CATEGORICA] = treino[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
        validacao[COLUNA_CATEGORICA] = validacao[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
        X_treino = treino[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        X_validacao = validacao[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]]
        modelo = CatBoostRegressor(**hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False)

    else:
        raise ValueError(f"Modelo não reconhecido: {nome_modelo}")

    modelo.fit(X_treino, treino["quantidade_mes"])

    mae_treino = calcular_metricas(pd.DataFrame({
        "quantidade_mes": treino["quantidade_mes"].reset_index(drop=True),
        "previsao_baseline": modelo.predict(X_treino),
    }))["mae"]
    mae_validacao = calcular_metricas(pd.DataFrame({
        "quantidade_mes": validacao["quantidade_mes"].reset_index(drop=True),
        "previsao_baseline": modelo.predict(X_validacao),
    }))["mae"]

    return {"modelo": nome_modelo, "mae_treino": mae_treino, "mae_validacao": mae_validacao, "gap": mae_validacao - mae_treino}

def analisar_residuos(nome_modelo: str, validacao: pd.DataFrame, hiperparametros: dict) -> dict:
    """Treina o modelo final e resume a distribuição dos resíduos na validação.

    Args:
        nome_modelo: Nome do modelo (usado só para rótulo no resultado).
        validacao: DataFrame de validação com a coluna previsao_baseline já calculada.
        hiperparametros: Não usado diretamente aqui — mantido por consistência de assinatura.

    Returns:
        Dicionário com média, desvio-padrão, skewness e % de resíduos positivos.
    """
    residuos = validacao["quantidade_mes"] - validacao["previsao_baseline"]
    return {
        "modelo": nome_modelo,
        "media_residuo": residuos.mean(),
        "desvio_residuo": residuos.std(),
        "skewness": residuos.skew(),
        "pct_residuos_positivos": (residuos > 0).mean(),
    }

def buscar_hiperparametros(client: MlflowClient, experimento_id: str, pipeline: str, nome_modelo: str) -> dict:
    """Busca os hiperparâmetros vencedores de um modelo específico (não só o selecionado_b3)."""
    runs = client.search_runs(
        experiment_ids=[experimento_id],
        filter_string=f"tags.mlflow.runName = 'estudo_{pipeline}_{nome_modelo}'",
    )
    if not runs:
        raise RuntimeError(f"Estudo não encontrado: estudo_{pipeline}_{nome_modelo}")
    params = runs[0].data.params
    prefixo = "melhor_"
    return {k[len(prefixo):]: (int(v) if v.lstrip("-").isdigit() else float(v))
            for k, v in params.items() if k.startswith(prefixo)}


def main():
    """Roda os três diagnósticos de premissas para um pipeline e registra no MLflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    df = carregar_mart_job(args.location_type, catalog=args.catalog)
    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)
    df = df[df["historico_suficiente"]]
    treino, validacao, _ = split_temporal(df)

    mlflow.set_experiment(EXPERIMENTO_PREMISSAS)
    with mlflow.start_run(run_name=f"premissas_{args.location_type}"):
        # Checagem 1 — multicolinearidade (features do Ridge)
        vif = calcular_vif(treino, FEATURES_NUMERICAS)
        print(f"\n[{args.location_type}] VIF por feature:")
        print(vif.to_string(index=False))
        for _, linha in vif.iterrows():
            mlflow.log_metric(f"vif_{linha['feature']}", linha["vif"])

        # Checagem 2 — overfitting (RF, LightGBM, CatBoost)
        print(f"\n[{args.location_type}] Overfitting (treino vs. validação):")
        for nome_modelo in ["random_forest", "lightgbm", "catboost"]:
            hiperparametros = buscar_hiperparametros(client, experimento.experiment_id, args.location_type, nome_modelo)
            resultado = avaliar_overfitting(nome_modelo, treino, validacao, hiperparametros)
            print(f"  {nome_modelo}: MAE treino={resultado['mae_treino']:.3f} | "
                  f"MAE validação={resultado['mae_validacao']:.3f} | gap={resultado['gap']:.3f}")
            mlflow.log_metric(f"mae_treino_{nome_modelo}", resultado["mae_treino"])
            mlflow.log_metric(f"mae_validacao_{nome_modelo}", resultado["mae_validacao"])
            mlflow.log_metric(f"gap_overfitting_{nome_modelo}", resultado["gap"])

            # Checagem 3 — resíduos, só para o modelo final (CatBoost)
            if nome_modelo == "catboost":
                validacao_prevista = validacao.copy()
                # reaproveita o modelo já treinado dentro de avaliar_overfitting exigiria refatorar
                # o retorno da função; para manter a Checagem 2 simples e legível, retreina-se aqui
                # uma vez a mais — custo aceitável dado que CatBoost já é rápido nesta base.
                treino_c = treino.copy()
                treino_c[COLUNA_CATEGORICA] = treino_c[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
                validacao_prevista[COLUNA_CATEGORICA] = validacao_prevista[COLUNA_CATEGORICA].fillna("desconhecida").astype(str)
                modelo_final = CatBoostRegressor(**hiperparametros, cat_features=[COLUNA_CATEGORICA], random_state=42, verbose=False)
                modelo_final.fit(treino_c[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]], treino_c["quantidade_mes"])
                validacao_prevista["previsao_baseline"] = modelo_final.predict(validacao_prevista[FEATURES_NUMERICAS + [COLUNA_CATEGORICA]])

                residuos = analisar_residuos(nome_modelo, validacao_prevista, hiperparametros)
                print(f"\n[{args.location_type}] Resíduos do CatBoost: {residuos}")
                mlflow.log_metric("residuo_media", residuos["media_residuo"])
                mlflow.log_metric("residuo_desvio", residuos["desvio_residuo"])
                mlflow.log_metric("residuo_skewness", residuos["skewness"])
                mlflow.log_metric("residuo_pct_positivos", residuos["pct_residuos_positivos"])


if __name__ == "__main__":
    main()