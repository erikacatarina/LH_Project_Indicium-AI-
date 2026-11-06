"""Criação/atualização do índice vetorial (Delta Sync Index) do corpus do RAG — LH Nautical.

Cria (na primeira execução) ou reaproveita (nas seguintes) o endpoint e o
índice Delta Sync sobre a tabela de chunks, usando o embedding
Qwen3-Embedding-0.6B via Foundation Model APIs, e dispara a sincronização
full a cada execução (reindexação mensal).

Nomenclatura e API confirmadas contra a documentação oficial em 15/09/2026
(Databricks AI Search, renomeado de "Vector Search" em 01/06/2026).

Executado como task Python serverless de um Databricks Job, encadeada
depois da task de chunking.
"""

import inspect
import sys
import time
from pathlib import Path


def _bundle_root() -> Path:
    """Descobre a raiz do bundle subindo os frames até achar o caminho deste arquivo."""
    frame = inspect.currentframe()
    while frame:
        caminho = frame.f_locals.get("filename")
        if caminho and Path(caminho).name == "indexacao.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

from databricks.ai_search.client import AISearchClient

NOME_ENDPOINT = "lh_nautical_rag_endpoint"
COLUNA_EMBEDDING = "texto"
COLUNA_CHAVE = "chunk_id"
ENDPOINT_MODELO_EMBEDDING = "databricks-qwen3-embedding-0-6b"

def garantir_cdf_habilitado(catalog: str):
    """Habilita Change Data Feed na tabela de chunks — exigido pelo Delta Sync Index
    em endpoints STANDARD.

    Idempotente: seguro rodar em toda execução, mesmo se já estiver habilitado.
    """
    from databricks.sdk.runtime import spark
    spark.sql(f"""
        ALTER TABLE {catalog}.gold.rag_chunks
        SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """)

def garantir_endpoint(client: AISearchClient, nome_endpoint: str):
    """Cria o endpoint STANDARD se ainda não existir, então reaproveitar em vez de recriar a cada execução é essencial."""
    try:
        client.get_endpoint(name=nome_endpoint)
        print(f"Endpoint '{nome_endpoint}' já existe — reaproveitando.")
    except Exception as erro:
        print(f"Endpoint '{nome_endpoint}' não encontrado ({erro}) — criando (tipo STANDARD).")
        client.create_endpoint(name=nome_endpoint, endpoint_type="STANDARD")


def garantir_indice(client: AISearchClient, nome_endpoint: str, nome_indice: str, tabela_origem: str):
    """Cria o índice Delta Sync se ainda não existir; se já existir, só reaproveita."""
    try:
        indice = client.get_index(endpoint_name=nome_endpoint, index_name=nome_indice)
        print(f"Índice '{nome_indice}' já existe — reaproveitando.")
    except Exception as erro:
        print(f"Índice '{nome_indice}' não encontrado ({erro}) — criando.")
        indice = client.create_delta_sync_index(
            endpoint_name=nome_endpoint,
            source_table_name=tabela_origem,
            index_name=nome_indice,
            pipeline_type="TRIGGERED",
            primary_key=COLUNA_CHAVE,
            embedding_source_column=COLUNA_EMBEDDING,
            embedding_model_endpoint_name=ENDPOINT_MODELO_EMBEDDING,
        )
    return indice

def aguardar_indice_pronto(indice, timeout_segundos: int = 1200, intervalo_segundos: int = 15):
    """Espera o índice ficar pronto (status 'ready'), com timeout — evita loop
    infinito se algo travar do lado do Databricks."""
    tempo_decorrido = 0
    while not indice.describe().get("status", {}).get("ready", False):
        if tempo_decorrido >= timeout_segundos:
            raise TimeoutError(f"Índice não ficou pronto em {timeout_segundos}s.")
        print("Aguardando índice ficar pronto...")
        time.sleep(intervalo_segundos)
        tempo_decorrido += intervalo_segundos
    print("Índice pronto.")

def main():
    """Garante endpoint/índice, dispara a sincronização full e roda uma consulta de teste."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    tabela_origem = f"{args.catalog}.gold.rag_chunks"
    nome_indice = f"{args.catalog}.gold.rag_chunks_index"

    garantir_cdf_habilitado(args.catalog)

    client = AISearchClient()
    garantir_endpoint(client, NOME_ENDPOINT)
    indice = garantir_indice(client, NOME_ENDPOINT, nome_indice, tabela_origem)

    print("Disparando sincronização (reindexação full mensal)...")

    aguardar_indice_pronto(indice)

    resultado_teste = indice.similarity_search(
        query_text="previsão de demanda sazonalidade",
        columns=[COLUNA_CHAVE, "documento", "secao"],
        num_results=3,
    )
    print("Consulta de teste (confirma que o índice responde antes de fechar a tarefa):")
    print(resultado_teste)


if __name__ == "__main__":
    main()
