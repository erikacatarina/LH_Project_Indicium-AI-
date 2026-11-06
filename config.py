"""Configuração de conexão do pacote de forecast — LH Nautical.

Centraliza a leitura de credenciais do SQL Warehouse a partir do .env,
para uso por qualquer módulo de src/forecast/ ou por testes.
"""
import os

from dotenv import load_dotenv

load_dotenv(override=True)

DATABRICKS_HOST = os.environ["DATABRICKS_HOST"]
DATABRICKS_HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
DATABRICKS_CATALOG = os.environ.get("DATABRICKS_CATALOG", "dev")
DATABRICKS_SCHEMA = "gold"