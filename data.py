"""Acesso a dados da mart oficial do forecast — LH Nautical.

Fornece carregar_mart, o ponto único de leitura de
fct_demanda_mensal_produto_local, já filtrado por pipeline
(store ou warehouse).
"""
import pandas as pd
from databricks import sql

from src.forecast import config


def _conectar():
    """Abre uma conexão com o SQL Warehouse configurado em config.py."""
    return sql.connect(
        server_hostname=config.DATABRICKS_HOST,
        http_path=config.DATABRICKS_HTTP_PATH,
        access_token=config.DATABRICKS_TOKEN,
        catalog=config.DATABRICKS_CATALOG,
        schema=config.DATABRICKS_SCHEMA,
    )


def carregar_mart(location_type: str) -> pd.DataFrame:
    """Carrega a mart oficial do forecast, filtrada por pipeline.

    Args:
        location_type: Tipo de local a filtrar — "store" ou "warehouse".
            Nunca os dois juntos, para não misturar as duas populações de
            demanda.

    Returns:
        DataFrame com uma linha por product_variant_id, location_id e mês,
        ordenado cronologicamente dentro de cada combinação.

    Raises:
        KeyError: Se alguma variável de ambiente de conexão não estiver
            definida no .env (ver src.forecast.config).
    """
    query = f"""
        SELECT *
        FROM fct_demanda_mensal_produto_local
        WHERE location_type = '{location_type}'
        ORDER BY product_variant_id, location_id, mes_ref
    """
    with _conectar() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(rows, columns=columns)