"""Ponto de entrada do pacote de forecast — LH Nautical.

Uso:
    python -m src.forecast --location-type store 
    python -m src.forecast --location-type warehouse

Monta a tabela de features para um pipeline e imprime um resumo de 
conferência: linhas carregadas da mart, nulos por feature derivada e o 
tamanho de cada corte do split temporal (treino, validação, teste).
"""
import argparse

from src.forecast import adicionar_encoding_mes, carregar_mart, criar_features_temporais, split_temporal


def main():
    """Monta a tabela de features para um pipeline e imprime um resumo de conferência."""
    parser = argparse.ArgumentParser(description="Monta a tabela de features do forecast para um pipeline.")
    parser.add_argument("--location-type", choices=["store", "warehouse"], required=True)
    args = parser.parse_args()

    df = carregar_mart(args.location_type)
    print(f"Linhas carregadas da mart ({args.location_type}): {len(df)}")

    df = criar_features_temporais(df)
    df = adicionar_encoding_mes(df)

    colunas_feature = [c for c in df.columns if c.startswith(("lag_", "rolling_", "mes_"))]
    print("Nulos por feature derivada (esperado: mais nulos em lags/janelas maiores):")
    print(df[colunas_feature].isna().sum())

    treino, validacao, teste = split_temporal(df)
    print(f"Treino: {len(treino)} linhas, até {treino['mes_ref'].max()}")
    print(f"Validação: {len(validacao)} linhas, {validacao['mes_ref'].min()} a {validacao['mes_ref'].max()}")
    print(f"Teste: {len(teste)} linhas, a partir de {teste['mes_ref'].min()}")


if __name__ == "__main__":
    main()