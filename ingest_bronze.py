"""Script de ingestao Bronze — LH Nautical.

Extrai as 13 tabelas em escopo do banco SQL Server via JDBC
e grava na camada Bronze do Delta Lake, com idempotencia
garantida via overwrite controlado (full load).

Estrategia de extracao: full load para todas as tabelas.
Decisao tomada considerando o volume total do projeto (~293k linhas)
e a ausencia de coluna de data em order_items e return_items,
que inviabilizaria extracao incremental simples nessas tabelas.
"""

# Adiciona a raiz do bundle ao sys.path para permitir imports entre modulos
# quando executado via spark_python_task no Databricks Workflows (DAB/Serverless).
# os.getcwd() aponta para o diretorio do script; dois niveis acima chega na raiz.
import os
import sys

bundle_root = os.path.abspath(os.path.join(os.getcwd(), "..", ".."))
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

import argparse

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    IntegerType,
    ShortType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.utils.logging_utils import (
    configurar_logger,
    tratar_erro_conexao,
    tratar_erro_schema,
)

parser = argparse.ArgumentParser()
parser.add_argument("--catalog", default="dev", help="Catalogo de destino (dev ou prd)")
args = parser.parse_args()

CATALOGO = args.catalog
SCHEMA = "bronze"
ORIGEM = "sql"

logger = configurar_logger()

# 13 tabelas em escopo conforme ANALISE_FONTE_DADOS.md (classificação "Incluir")
TABELAS_INCLUIR = [
    "orders",
    "order_items",        
    "payments",
    "returns",
    "return_items",       
    "fiscal_invoices",
    "customers",
    "products",
    "product_variants",
    "categories",
    "brands",
    "locations",
    "employees",
]

# Schema explícito por tabela conforme MAPEAMENTO_DE_SCHEMA.md.
# Evita inferência automática do Spark, que pode errar quando colunas vêm nulas.
SCHEMAS = {
    "customers": StructType([
        StructField("id", IntegerType(), False),
        StructField("person_type", StringType(), False),
        StructField("legal_name", StringType(), False),
        StructField("trade_name", StringType(), True),
        StructField("tax_id", StringType(), False),
        StructField("state_registration", StringType(), True),
        StructField("email", StringType(), True),
        StructField("phone", StringType(), True),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "brands": StructType([
        StructField("id", IntegerType(), False),
        StructField("name", StringType(), False),
        StructField("country", StringType(), True),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "categories": StructType([
        StructField("id", IntegerType(), False),
        StructField("name", StringType(), False),
        StructField("slug", StringType(), False),
        StructField("parent_category_id", IntegerType(), True),   # FK auto-referenciada — nulo em categorias raiz
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "locations": StructType([
        StructField("id", IntegerType(), False),
        StructField("name", StringType(), False),
        StructField("location_type", StringType(), False),
        StructField("postal_code", StringType(), False),
        StructField("street", StringType(), False),
        StructField("number", StringType(), False),
        StructField("complement", StringType(), True),
        StructField("district", StringType(), False),
        StructField("city", StringType(), False),
        StructField("state", StringType(), False),
        StructField("country", StringType(), False),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "employees": StructType([
        StructField("id", IntegerType(), False),
        StructField("full_name", StringType(), False),
        StructField("cpf", StringType(), False),                   # dado sensível (PII)
        StructField("email", StringType(), True),
        StructField("role", StringType(), False),
        StructField("primary_location_id", IntegerType(), True),  # FK para locations, opcional
        StructField("hire_date", DateType(), False),
        StructField("termination_date", DateType(), True),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "products": StructType([
        StructField("id", IntegerType(), False),
        StructField("name", StringType(), False),
        StructField("description", StringType(), True),
        StructField("brand_id", IntegerType(), False),
        StructField("category_id", IntegerType(), False),
        StructField("ncm_code", StringType(), False),
        StructField("unit_of_measure", StringType(), False),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "product_variants": StructType([
        StructField("id", IntegerType(), False),
        StructField("product_id", IntegerType(), False),
        StructField("sku", StringType(), False),
        StructField("barcode_ean", StringType(), True),
        StructField("sale_price", DecimalType(14, 2), False),
        StructField("cost_price", DecimalType(14, 2), False),
        StructField("weight_kg", DecimalType(10, 3), True),
        StructField("icms_rate", DecimalType(5, 2), False),
        StructField("ipi_rate", DecimalType(5, 2), False),
        StructField("is_active", BooleanType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "orders": StructType([
        StructField("id", IntegerType(), False),
        StructField("order_number", StringType(), False),
        StructField("channel", StringType(), False),
        StructField("customer_id", IntegerType(), False),
        StructField("salesperson_id", IntegerType(), True),
        StructField("location_id", IntegerType(), False),
        StructField("status", StringType(), False),
        StructField("subtotal", DecimalType(14, 2), False),
        StructField("discount_amount", DecimalType(14, 2), False),
        StructField("total", DecimalType(14, 2), False),
        StructField("placed_at", TimestampType(), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "order_items": StructType([
        StructField("id", IntegerType(), False),
        StructField("order_id", IntegerType(), False),            
        StructField("product_variant_id", IntegerType(), False),
        StructField("quantity", DecimalType(14, 3), False),
        StructField("unit_price", DecimalType(14, 2), False),
        StructField("icms_rate", DecimalType(5, 2), False),
        StructField("ipi_rate", DecimalType(5, 2), False),
        StructField("line_total", DecimalType(14, 2), False),
    ]),

    "payments": StructType([
        StructField("id", IntegerType(), False),
        StructField("order_id", IntegerType(), False),
        StructField("method", StringType(), False),
        StructField("installments", ShortType(), False),
        StructField("amount", DecimalType(14, 2), False),
        StructField("status", StringType(), False),
        StructField("paid_at", TimestampType(), True),           
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "returns": StructType([
        StructField("id", IntegerType(), False),
        StructField("return_number", StringType(), False),
        StructField("order_id", IntegerType(), False),
        StructField("customer_id", IntegerType(), False),
        StructField("received_at_location_id", IntegerType(), False),
        StructField("status", StringType(), False),
        StructField("reason", StringType(), True),
        StructField("total_refund_amount", DecimalType(14, 2), False),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),

    "return_items": StructType([
        StructField("id", IntegerType(), False),
        StructField("return_id", IntegerType(), False),           # FK para returns — usada para join incremental futuro
        StructField("order_item_id", IntegerType(), False),
        StructField("quantity", DecimalType(14, 3), False),
        StructField("action", StringType(), False),
        StructField("exchange_variant_id", IntegerType(), True),  # preenchido apenas em trocas
        StructField("unit_refund_amount", DecimalType(14, 2), False),
    ]),

    "fiscal_invoices": StructType([
        StructField("id", IntegerType(), False),
        StructField("order_id", IntegerType(), False),
        StructField("nfe_number", StringType(), False),
        StructField("nfe_access_key", StringType(), False),
        StructField("series", StringType(), False),
        StructField("issued_at", TimestampType(), False),
        StructField("status", StringType(), False),
        StructField("total_amount", DecimalType(14, 2), False),
        StructField("xml_storage_uri", StringType(), True),
        StructField("created_at", TimestampType(), False),
        StructField("updated_at", TimestampType(), False),
    ]),
}


def conectar_jdbc() -> tuple[str, dict]:
    """Monta a URL e as propriedades de conexao JDBC com o banco SQL Server.

    Recupera as credenciais do Databricks Secrets e monta a string de conexao com os
    parametros de criptografia TLS necessarios neste ambiente.

    Returns:
        Tupla contendo a URL JDBC e o dicionario de propriedades de conexao.

    Raises:
        ConnectionError: Se as credenciais nao puderem ser recuperadas do Secrets.
    """
    try:
        host = dbutils.secrets.get(scope="lh-nautical", key="jdbc-host")          # noqa: F821
        port = dbutils.secrets.get(scope="lh-nautical", key="jdbc-port")          # noqa: F821
        database = dbutils.secrets.get(scope="lh-nautical", key="jdbc-database")  # noqa: F821
        user = dbutils.secrets.get(scope="lh-nautical", key="jdbc-user")          # noqa: F821
        password = dbutils.secrets.get(scope="lh-nautical", key="jdbc-password")  # noqa: F821
    except Exception as erro:
        tratar_erro_conexao(logger, "secrets", erro)

    jdbc_url = (
        f"jdbc:sqlserver://{host}:{port};"
        f"databaseName={database};"
        f"encrypt=true;trustServerCertificate=true"
    )

    connection_properties = {
        "user": user,
        "password": password,
        "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    }

    logger.info("Conexao JDBC configurada com sucesso.")
    return jdbc_url, connection_properties


def aplicar_schema(df, schema_esperado: StructType):
    """Aplica o schema explicito a um DataFrame, com cast por coluna.

    Args:
        df: DataFrame Spark com schema inferido pela leitura JDBC.
        schema_esperado: Schema explicito definido em SCHEMAS, com
            o tipo correto de cada coluna.

    Returns:
        DataFrame com as colunas tipadas conforme o schema esperado.
    """
    return df.select(
        [df[campo.name].cast(campo.dataType).alias(campo.name) for campo in schema_esperado.fields]
    )


def extrair_tabela(spark: SparkSession, nome_tabela: str, jdbc_url: str, connection_properties: dict):
    """Extrai uma tabela do banco SQL Server via JDBC (full load), com schema explicito.

    Args:
        spark: Sessao Spark ativa.
        nome_tabela: Nome da tabela a ser extraida, conforme schema de origem.
        jdbc_url: URL de conexao JDBC.
        connection_properties: Propriedades de autenticacao da conexao.

    Returns:
        DataFrame Spark contendo todos os registros da tabela, com schema validado.

    Raises:
        ConnectionError: Se a extracao falhar por problema de conexao.
        ValueError: Se a tabela nao tiver schema definido no dicionario SCHEMAS.
    """
    if nome_tabela not in SCHEMAS:
        raise ValueError(
            f"Schema nao definido para a tabela '{nome_tabela}'. "
            f"Adicione ao dicionario SCHEMAS antes de prosseguir."
        )

    schema_esperado = SCHEMAS[nome_tabela]

    try:
        logger.info(f"Iniciando extracao da tabela '{nome_tabela}' com schema explicito...")

        df = spark.read.jdbc(
            url=jdbc_url,
            table=nome_tabela,
            properties=connection_properties,
        )

        df = aplicar_schema(df, schema_esperado)

        total_linhas = df.count()
        logger.info(f"Tabela '{nome_tabela}' extraida com sucesso: {total_linhas} linhas.")
        return df
    except Exception as erro:
        tratar_erro_conexao(logger, nome_tabela, erro)


def montar_nome_tabela_bronze(nome_tabela: str) -> str:
    """Monta o nome completo da tabela na camada Bronze, conforme CONVENCAO_DE_NOMENCLATURA.md.

    Formato: <catalog>.<schema>.<origem>_<nome_original_tabela>

    Args:
        nome_tabela: Nome original da tabela na origem.

    Returns:
        Nome completo qualificado para uso no Unity Catalog.
    """
    return f"{CATALOGO}.{SCHEMA}.{ORIGEM}_{nome_tabela}"


def escrever_bronze(df, nome_tabela: str) -> None:
    """Grava o DataFrame na camada Bronze do Delta Lake, com idempotencia.

    Utiliza modo overwrite para garantir que reprocessamentos do
    pipeline nao gerem duplicatas, cada execucao substitui
    completamente o conteudo da tabela Bronze pelo dado mais
    recente extraido da origem (estrategia full load).

    Decisao de otimizacao: nao aplicamos PARTITIONED BY fisico,
    dado o volume do projeto (~293k linhas) estar muito abaixo do
    limiar de 1TB documentado no CONVENCAO_DE_NOMENCLATURA.md. A coluna
    ingestion_date e gravada desde ja para viabilizar migracao
    futura para Liquid Clustering (CLUSTER BY) sem reprocessamento
    historico, caso o volume cresca (ver docs/ESCALABILIDADE.md).

    Args:
        df: DataFrame Spark a ser gravado.
        nome_tabela: Nome original da tabela na origem.

    Raises:
        ValueError: Se a escrita falhar por incompatibilidade de schema.
    """
    from pyspark.sql.functions import current_date

    df_com_data = df.withColumn("ingestion_date", current_date())
    nome_completo = montar_nome_tabela_bronze(nome_tabela)

    try:
        logger.info(f"Gravando tabela '{nome_completo}' na camada Bronze...")

        df_com_data.write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(nome_completo)

        logger.info(f"Tabela '{nome_completo}' gravada com sucesso.")
    except Exception as erro:
        tratar_erro_schema(logger, nome_tabela, erro)


def main():
    """Orquestra a ingestao das 13 tabelas em escopo para a camada Bronze."""
    spark = SparkSession.builder.getOrCreate()
    jdbc_url, connection_properties = conectar_jdbc()

    logger.info(f"Iniciando ingestao de {len(TABELAS_INCLUIR)} tabelas...")

    for nome_tabela in TABELAS_INCLUIR:
        df = extrair_tabela(spark, nome_tabela, jdbc_url, connection_properties)
        escrever_bronze(df, nome_tabela)

    logger.info("Ingestao Bronze concluida com sucesso para todas as tabelas.")


if __name__ == "__main__":
    main()