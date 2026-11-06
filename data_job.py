"""Carregamento da mart para uso dentro de um Databricks Job — LH Nautical.

Diferente de src.forecast.data (usado localmente, via SQL Warehouse), este
módulo só funciona executando dentro do Databricks (Job), onde a sessão
spark é obtida via databricks.sdk.runtime — necessário porque, em tasks de
arquivo .py (diferente de notebooks), `spark` não vem pré-definido no
namespace automaticamente.
"""

import pandas as pd
from databricks.sdk.runtime import spark


def carregar_mart_job(location_type: str, catalog: str, schema: str = "gold") -> pd.DataFrame:
    """Carrega a mart oficial do forecast via Spark nativo, filtrada por pipeline.

    Args:
        location_type: Tipo de local a filtrar — "store" ou "warehouse".

    Returns:
        DataFrame pandas, no mesmo formato de src.forecast.data.carregar_mart.
    """
    df_spark = (
        spark.table(f"{catalog}.{schema}.fct_demanda_mensal_produto_local")
        .filter(f"location_type = '{location_type}'")
        .orderBy("product_variant_id", "location_id", "mes_ref")
    )
    return df_spark.toPandas()