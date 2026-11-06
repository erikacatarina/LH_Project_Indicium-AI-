"""Baseline de médias móveis — LH Nautical.

Implementa a baseline obrigatória do forecast: prever a
demanda do mês como a média móvel dos últimos 3 meses. É o piso de
comparação que os 4 modelos de regressão precisam superar
para serem justificados.
"""

import numpy as np
import pandas as pd


def prever_baseline(df: pd.DataFrame, coluna_baseline: str = "rolling_mean_3") -> pd.DataFrame:
    """Usa a média móvel já calculada como previsão da baseline.

    Args:
        df: DataFrame de saída de criar_features_temporais, contendo a
            coluna de rolling mean a ser usada como previsão.
        coluna_baseline: Nome da coluna de rolling mean a usar como previsão.
            Padrão: rolling_mean_3, a média dos últimos 3 meses.

    Returns:
        O mesmo DataFrame de entrada, com a coluna previsao_baseline adicionada.
    """
    df = df.copy()
    df["previsao_baseline"] = df[coluna_baseline]
    return df


def calcular_metricas(
    df: pd.DataFrame,
    coluna_real: str = "quantidade_mes",
    coluna_prevista: str = "previsao_baseline",
) -> dict:
    """Calcula MAE, RMSE e MAPE entre valores reais e previstos.

    MAPE é calculado apenas sobre linhas em que o valor real é maior que
    zero, para evitar divisão por zero — o número de linhas excluídas é
    retornado junto, para transparência.

    Args:
        df: DataFrame contendo as colunas de valor real e valor previsto.
        coluna_real: Nome da coluna com o valor real observado.
        coluna_prevista: Nome da coluna com o valor previsto.

    Returns:
        Dicionário com as chaves mae, rmse, mape e linhas_excluidas_mape.
    """
    valido = df.dropna(subset=[coluna_real, coluna_prevista])
    erro = valido[coluna_real] - valido[coluna_prevista]

    mae = erro.abs().mean()
    rmse = np.sqrt((erro**2).mean())

    nao_zero = valido[valido[coluna_real] > 0]
    mape = (
        (nao_zero[coluna_real] - nao_zero[coluna_prevista]).abs() / nao_zero[coluna_real]
    ).mean() * 100
    linhas_excluidas_mape = len(valido) - len(nao_zero)

    return {
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "linhas_excluidas_mape": linhas_excluidas_mape,
    }