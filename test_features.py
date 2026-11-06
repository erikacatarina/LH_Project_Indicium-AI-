"""Testes de não-vazamento do módulo de features — LH Nautical.

Prova, com dado sintético e valores conhecidos, que lags e rolling
windows não usam informação do futuro e não misturam combinações
diferentes.
"""
import numpy as np
import pandas as pd

from src.forecast.features import adicionar_encoding_mes, criar_features_temporais, split_temporal


def test_lag_1_pega_mes_anterior_da_mesma_combinacao(df_exemplo):
    """Verifica que lag_1 reflete o mês anterior da própria combinação, não de outra."""
    resultado = criar_features_temporais(df_exemplo)

    linha_marco_combinacao_b = resultado[
        (resultado.product_variant_id == 2) & (resultado.mes_ref == "2025-03-01")
    ]

    assert linha_marco_combinacao_b["lag_1"].iloc[0] == 6  # valor de fevereiro, combinação B


def test_rolling_mean_nao_inclui_o_proprio_mes(df_exemplo):
    """Verifica que a média móvel do mês M nunca inclui a demanda do próprio mês M."""
    resultado = criar_features_temporais(df_exemplo)

    linha_abril_combinacao_a = resultado[
        (resultado.product_variant_id == 1) & (resultado.mes_ref == "2025-04-01")
    ]

    # Se o 999999 do próprio mês vazasse para dentro do cálculo, a média não seria 10.
    assert linha_abril_combinacao_a["rolling_mean_3"].iloc[0] == 10.0


def test_rolling_mean_nao_mistura_combinacoes_diferentes(df_exemplo):
    """Verifica que a média móvel de uma combinação não é afetada por outra combinação."""
    resultado = criar_features_temporais(df_exemplo)

    linha_abril_combinacao_b = resultado[
        (resultado.product_variant_id == 2) & (resultado.mes_ref == "2025-04-01")
    ]

    # Média esperada: (5 + 6 + 7) / 3 = 6.0 — nada relacionado ao 999999 da combinação A.
    assert linha_abril_combinacao_b["rolling_mean_3"].iloc[0] == 6.0


def test_encoding_mes_aproxima_dezembro_e_janeiro():
    """Verifica que o encoding cíclico aproxima meses vizinhos do calendário (dez/jan)."""
    df = pd.DataFrame({"mes": [12, 1, 6]})
    resultado = adicionar_encoding_mes(df)

    dezembro = resultado.iloc[0][["mes_sin", "mes_cos"]].values
    janeiro = resultado.iloc[1][["mes_sin", "mes_cos"]].values
    junho = resultado.iloc[2][["mes_sin", "mes_cos"]].values

    distancia_dez_jan = np.linalg.norm(dezembro - janeiro)
    distancia_jan_jun = np.linalg.norm(janeiro - junho)

    assert distancia_dez_jan < distancia_jan_jun


def test_split_temporal_preserva_ordem_e_nao_perde_linhas(df_exemplo):
    """Verifica que o split temporal não embaralha datas nem perde/duplica linhas."""
    treino, validacao, teste = split_temporal(df_exemplo, meses_teste=1, meses_validacao=1)

    assert treino["mes_ref"].max() < validacao["mes_ref"].min()
    assert validacao["mes_ref"].max() < teste["mes_ref"].min()
    assert len(treino) + len(validacao) + len(teste) == len(df_exemplo)