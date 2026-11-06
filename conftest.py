"""Fixtures compartilhadas dos testes de forecast — LH Nautical.

Fornece dados sintéticos com valores conhecidos, usados pelos testes de
não-vazamento (test_features.py) e de métricas (test_baseline.py) —
nunca dado real da mart, para manter os testes rápidos e determinísticos.
"""
import pandas as pd
import pytest


@pytest.fixture
def df_exemplo():
    """Duas combinações (variante x local), 4 meses cada, valores conhecidos.

    Combinação A (variant=1, location=10): 10, 10, 10, 999999
        - os 3 primeiros meses são iguais de propósito (fácil calcular média a mão)
        - o 4º mês é um valor absurdo, plantado para provar que NADA depende dele
          quando calculamos a feature do próprio 4º mês (não pode vazar)

    Combinação B (variant=2, location=20): 5, 6, 7, 8
        - crescente, serve para provar que lag_1 realmente pega "o mês anterior"
          e não um valor qualquer

    As duas combinações são intercaladas no DataFrame de propósito (não vêm uma
    bloco inteiro depois da outra) — se o código não agrupar corretamente por
    combinação antes de calcular lag/rolling, os valores de uma vazam para a outra.
    """
    dados = [
        {"product_variant_id": 1, "location_id": 10, "mes_ref": "2025-01-01", "quantidade_mes": 10},
        {"product_variant_id": 2, "location_id": 20, "mes_ref": "2025-01-01", "quantidade_mes": 5},
        {"product_variant_id": 1, "location_id": 10, "mes_ref": "2025-02-01", "quantidade_mes": 10},
        {"product_variant_id": 2, "location_id": 20, "mes_ref": "2025-02-01", "quantidade_mes": 6},
        {"product_variant_id": 1, "location_id": 10, "mes_ref": "2025-03-01", "quantidade_mes": 10},
        {"product_variant_id": 2, "location_id": 20, "mes_ref": "2025-03-01", "quantidade_mes": 7},
        {"product_variant_id": 1, "location_id": 10, "mes_ref": "2025-04-01", "quantidade_mes": 999999},
        {"product_variant_id": 2, "location_id": 20, "mes_ref": "2025-04-01", "quantidade_mes": 8},
    ]
    df = pd.DataFrame(dados)
    df["mes_ref"] = pd.to_datetime(df["mes_ref"])
    df["mes"] = df["mes_ref"].dt.month
    return df