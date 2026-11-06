"""Checagem manual rápida do módulo de features.
 
Uso:
    python -m src.forecast.validar_manual --location-type store
    python -m src.forecast.validar_manual --location-type warehouse
 
Isto NÃO substitui os testes automatizados — é só uma conferência visual
rápida para rodar antes de commitar, e evitar commitar algo obviamente quebrado.
"""
import argparse
 
from src.forecast import carregar_mart, criar_features_temporais, split_temporal
 
 
def checagem_1_lag_bate_com_mes_anterior(df):
    """Imprime um exemplo de combinação para conferência visual do alinhamento do lag_1."""
    print("\n--- Checagem 1: lag_1 bate com o mês anterior da mesma combinação? ---")
    primeira_combinacao = df[["product_variant_id", "location_id"]].iloc[0]
    exemplo = df[
        (df.product_variant_id == primeira_combinacao.product_variant_id)
        & (df.location_id == primeira_combinacao.location_id)
    ].head(6)
    print(exemplo[["mes_ref", "quantidade_mes", "lag_1", "rolling_mean_3"]].to_string(index=False))
    print(
        "O que observar: lag_1 da linha N deve ser igual a quantidade_mes da linha N-1. "
        "rolling_mean_3 só deve aparecer a partir da 4ª linha (3 meses de histórico + o shift)."
    )
 
 
def checagem_2_split_nao_embaralhou(df):
    """Confere e imprime se o split temporal preserva a ordem cronológica."""
    print("\n--- Checagem 2: o split temporal não embaralhou nada? ---")
    treino, validacao, teste = split_temporal(df)
    ok = treino["mes_ref"].max() < validacao["mes_ref"].min() < teste["mes_ref"].min()
    print(
        f"Treino termina em {treino['mes_ref'].max()} | "
        f"Validação: {validacao['mes_ref'].min()} a {validacao['mes_ref'].max()} | "
        f"Teste começa em {teste['mes_ref'].min()}"
    )
    print("PASSOU" if ok else "FALHOU — investigar antes de commitar")
 
 
def main():
    """Executa as checagens 1 e 2 sobre a mart de um pipeline, via linha de comando."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    args = parser.parse_args()
 
    df = carregar_mart(args.location_type)
    df = criar_features_temporais(df)
 
    checagem_1_lag_bate_com_mes_anterior(df)
    checagem_2_split_nao_embaralhou(df)
 
 
if __name__ == "__main__":
    main()