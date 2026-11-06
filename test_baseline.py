"""Testes da baseline de médias móveis — LH Nautical.

Confirma que MAE, RMSE e MAPE batem com cálculo manual, e que o MAPE
trata corretamente linhas com demanda real igual a zero.
"""
import pandas as pd

from src.forecast.baseline import calcular_metricas


def test_metricas_batem_com_calculo_manual():
    """Verifica que MAE, RMSE e MAPE batem com um exemplo pequeno calculado à mão."""
    # real: [10, 20, 30] | previsto: [12, 18, 33]
    # erros: [-2, 2, -3] -> MAE = (2+2+3)/3 = 2.333...
    # RMSE = sqrt((4+4+9)/3) = sqrt(17/3) = 2.380...
    # MAPE = média(|erro|/real) * 100 = média(0.2, 0.1, 0.1) * 100 = 13.33...
    df = pd.DataFrame({"quantidade_mes": [10, 20, 30], "previsao_baseline": [12, 18, 33]})

    metricas = calcular_metricas(df)

    assert round(metricas["mae"], 2) == 2.33
    assert round(metricas["rmse"], 2) == 2.38
    assert round(metricas["mape"], 2) == 13.33
    assert metricas["linhas_excluidas_mape"] == 0


def test_metricas_excluem_linhas_com_real_zero_do_mape():
    """Verifica que linhas com demanda real zero são excluídas do MAPE e contabilizadas."""
    df = pd.DataFrame({"quantidade_mes": [0, 10], "previsao_baseline": [5, 10]})

    metricas = calcular_metricas(df)

    assert metricas["linhas_excluidas_mape"] == 1
    assert metricas["mape"] == 0.0  # a única linha restante (10 vs 10) tem erro zero