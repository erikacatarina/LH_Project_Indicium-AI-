"""Features derivadas de janela temporal — LH Nautical.

Implementa lags, médias/desvios móveis, encoding cíclico de mês e o
split temporal cronológico. Toda lógica que depende de ordenação no
tempo vive aqui, nunca na dbt.
"""
import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 12]
ROLLING_WINDOWS = [3, 6]
CHAVE_COMBINACAO = ["product_variant_id", "location_id"]


def criar_features_temporais(df: pd.DataFrame) -> pd.DataFrame:
    """Cria colunas de lag e média/desvio móvel por combinação produto-local.

    Todo cálculo usa shift(1) antes de qualquer rolling, para garantir que
    a feature do mês M nunca inclua a própria demanda do mês M.

    Args:
        df: DataFrame contendo, no mínimo, as colunas product_variant_id,
            location_id, mes_ref e quantidade_mes.

    Returns:
        O mesmo DataFrame, ordenado cronologicamente por combinação, com as
        colunas lag_1, lag_2, lag_3, lag_12, rolling_mean_3, rolling_std_3,
        rolling_mean_6 e rolling_std_6 adicionadas.
    """
    df = df.sort_values(CHAVE_COMBINACAO + ["mes_ref"]).reset_index(drop=True)

    for lag in LAGS:
        df[f"lag_{lag}"] = df.groupby(CHAVE_COMBINACAO)["quantidade_mes"].shift(lag)

    for janela in ROLLING_WINDOWS:
        # O parâmetro w=janela (em vez de usar `janela` direto dentro da lambda) evita um
        # erro clássico de closure em loop: sem isso, todas as colunas de rolling acabariam
        # usando o valor de `janela` da ÚLTIMA iteração do loop, não o valor de cada rodada.
        df[f"rolling_mean_{janela}"] = df.groupby(CHAVE_COMBINACAO)["quantidade_mes"].transform(
            lambda s, w=janela: s.shift(1).rolling(w).mean()
        )
        df[f"rolling_std_{janela}"] = df.groupby(CHAVE_COMBINACAO)["quantidade_mes"].transform(
            lambda s, w=janela: s.shift(1).rolling(w).std()
        )

    return df

def adicionar_encoding_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona o encoding cíclico (seno/cosseno) do mês do ano.

    Representa o mês como uma posição num círculo, para que dezembro e
    janeiro fiquem matematicamente próximos, relevante para os modelos
    lineares (Ridge/Lasso), que não capturam essa proximidade sozinhos.

    Args:
        df: DataFrame contendo a coluna mes (inteiro de 1 a 12).

    Returns:
        O mesmo DataFrame, com as colunas mes_sin e mes_cos adicionadas.
    """
    df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)
    return df

def split_temporal(df: pd.DataFrame, meses_teste: int = 3, meses_validacao: int = 3):
    """Divide o DataFrame em treino, validação e teste, por data, sem embaralhar.

    Args:
        df: DataFrame contendo a coluna mes_ref.
        meses_teste: Quantidade de meses mais recentes reservados para teste.
            Padrão: 3, o mesmo horizonte do forecast oficial.
        meses_validacao: Quantidade de meses imediatamente anteriores ao teste,
            reservados para validação/tuning de hiperparâmetros.

    Returns:
        Tupla (treino, validacao, teste), três DataFrames que juntos
        reconstituem o original, sem nenhuma linha repetida ou perdida.
    """
    meses_ordenados = sorted(df["mes_ref"].unique())

    corte_teste = meses_ordenados[-meses_teste]
    corte_validacao = meses_ordenados[-(meses_teste + meses_validacao)]

    treino = df[df["mes_ref"] < corte_validacao]
    validacao = df[(df["mes_ref"] >= corte_validacao) & (df["mes_ref"] < corte_teste)]
    teste = df[df["mes_ref"] >= corte_teste]

    return treino, validacao, teste