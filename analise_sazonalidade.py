"""Análise formal de sazonalidade no produto escolhido — LH Nautical.

Recalcula as candidatas a sazonalidade e aplica testes
estatísticos formais — força de sazonalidade via STL, teste de Mann-Whitney
(alta temporada vs. resto do ano) e autocorrelação no lag 12 — para
justificar, com rigor, a escolha do produto usado na pergunta de negócio 1.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.analise_sazonalidade
"""

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import acf

from src.forecast import carregar_mart

MESES_ALTA_TEMPORADA = [12, 1, 2, 3]


def candidatas_sazonalidade(pipeline: str, top_n: int = 5) -> pd.DataFrame:
    """Recalcula o índice de sazonalidade por variante, entre as combinações maduras.

    Args:
        pipeline: "store" ou "warehouse".
        top_n: Quantas candidatas retornar, ordenadas do maior índice para o menor.

    Returns:
        DataFrame indexado por product_variant_id, com as médias por período
        e o índice de sazonalidade (alta_temporada / resto_do_ano).
    """
    df = carregar_mart(pipeline)
    df = df[df["historico_suficiente"]]

    agregado = df.groupby(["product_variant_id", "mes"])["quantidade_mes"].sum().reset_index()
    agregado["periodo"] = agregado["mes"].apply(
        lambda m: "alta_temporada" if m in MESES_ALTA_TEMPORADA else "resto_do_ano"
    )

    medias = (
        agregado.groupby(["product_variant_id", "periodo"])["quantidade_mes"]
        .mean()
        .unstack("periodo")
        .dropna()
    )
    medias = medias[medias["resto_do_ano"] > 0]
    medias["indice_sazonalidade"] = medias["alta_temporada"] / medias["resto_do_ano"]

    return medias.sort_values("indice_sazonalidade", ascending=False).head(top_n)

def testar_sazonalidade(pipeline: str, product_variant_id) -> dict:
    """Aplica os três testes estatísticos de sazonalidade a uma variante específica.

    Args:
        pipeline: "store" ou "warehouse".
        product_variant_id: A variante a testar.

    Returns:
        Dicionário com os resultados de cada teste, incluindo avisos quando
        um teste não pôde ser aplicado por falta de histórico suficiente.
    """
    df = carregar_mart(pipeline)
    df = df[(df["historico_suficiente"]) & (df["product_variant_id"] == product_variant_id)]

    serie_mensal = df.groupby("mes_ref")["quantidade_mes"].sum().sort_index()
    resultado = {"product_variant_id": product_variant_id, "n_meses": len(serie_mensal)}

    # Teste 1 — Autocorrelação no lag 12 (o mesmo mês, um ano antes)
    if len(serie_mensal) >= 13:
        valores_acf = acf(serie_mensal, nlags=12, fft=True)
        resultado["acf_lag_12"] = valores_acf[12]
    else:
        resultado["acf_lag_12"] = None
        resultado["aviso_acf"] = f"Histórico de {len(serie_mensal)} meses insuficiente (mínimo 13)"

    # Teste 2 — Força de sazonalidade via STL (precisa de pelo menos 24 meses)
    if len(serie_mensal) >= 24:
        stl = STL(serie_mensal, period=12, robust=True).fit()
        variancia_residuo = np.var(stl.resid)
        variancia_sazonal_mais_residuo = np.var(stl.seasonal + stl.resid)
        resultado["forca_sazonalidade_stl"] = (
            max(0, 1 - variancia_residuo / variancia_sazonal_mais_residuo)
            if variancia_sazonal_mais_residuo > 0 else None
        )
    else:
        resultado["forca_sazonalidade_stl"] = None
        resultado["aviso_stl"] = f"Histórico de {len(serie_mensal)} meses insuficiente para STL (mínimo recomendado: 24)"

    # Teste 3 — Mann-Whitney: a demanda em alta temporada é maior que no resto do ano?
    df["periodo"] = df["mes"].apply(lambda m: "alta" if m in MESES_ALTA_TEMPORADA else "resto")
    grupo_alta = df[df["periodo"] == "alta"]["quantidade_mes"]
    grupo_resto = df[df["periodo"] == "resto"]["quantidade_mes"]

    if len(grupo_alta) >= 3 and len(grupo_resto) >= 3:
        _, p_valor = mannwhitneyu(grupo_alta, grupo_resto, alternative="greater")
        resultado["mannwhitney_p_valor"] = p_valor
    else:
        resultado["mannwhitney_p_valor"] = None
        resultado["aviso_mannwhitney"] = "Menos de 3 observações em algum dos dois grupos"

    return resultado

def main():
    """Roda a análise de sazonalidade nas top candidatas de cada pipeline."""
    for pipeline in ["store", "warehouse"]:
        print(f"\n=========== {pipeline} ===========")
        candidatas = candidatas_sazonalidade(pipeline, top_n=5)
        print("\nCandidatas (índice de sazonalidade recalculado):")
        print(candidatas.to_string())

        print("\nTestes formais nas top 3:")
        for product_variant_id in candidatas.head(3).index:
            resultado = testar_sazonalidade(pipeline, product_variant_id)
            print(f"\n  Variante {product_variant_id} ({resultado['n_meses']} meses de histórico):")
            print(f"    ACF lag 12: {resultado.get('acf_lag_12')}")
            print(f"    Força de sazonalidade (STL): {resultado.get('forca_sazonalidade_stl')}")
            print(f"    Mann-Whitney (p-valor, alta > resto): {resultado.get('mannwhitney_p_valor')}")
            for chave in ("aviso_acf", "aviso_stl", "aviso_mannwhitney"):
                if chave in resultado:
                    print(f"    ⚠️ {resultado[chave]}")


if __name__ == "__main__":
    main()