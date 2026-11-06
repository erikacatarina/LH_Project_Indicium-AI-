"""Script de setup de infraestrutura — LH Nautical.

Cria os catálogos e schemas do Unity Catalog necessários antes
de qualquer execução do pipeline de ingestão. Executar uma única
vez por workspace (ou sempre que um novo ambiente for provisionado).
"""

# Catálogo de desenvolvimento
spark.sql("CREATE CATALOG IF NOT EXISTS dev")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS dev.bronze")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS dev.silver")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS dev.gold")  # noqa: F821

# Catálogo de produção
spark.sql("CREATE CATALOG IF NOT EXISTS prd")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS prd.bronze")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS prd.silver")  # noqa: F821
spark.sql("CREATE SCHEMA IF NOT EXISTS prd.gold")  # noqa: F821

print("Catalogos e schemas criados/validados com sucesso.")
