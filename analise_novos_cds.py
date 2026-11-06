"""Necessidade e localização de novos centros de distribuição — LH Nautical.

Cruza o crescimento real de demanda por cidade/estado do cliente com a
presença geográfica já existente da empresa (lojas e CDs), para concluir se
um novo CD é necessário e, se for, sugerir onde — nunca definido a priori.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.analise_novos_cds
"""

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from src.forecast import carregar_mart
from src.forecast.crescimento_por_local import (
    EXPERIMENTO_MODELOS,
    buscar_hiperparametros_selecionados,
    calcular_crescimento_yoy,
    gerar_previsao_janela_3,
)
from src.forecast.data import _conectar  # reaproveita a mesma conexão já usada em carregar_mart


def run_query(query: str) -> pd.DataFrame:
    """Executa uma query no SQL Warehouse e retorna um DataFrame pandas."""
    connection = _conectar()
    with connection.cursor() as cursor:
        cursor.execute(query)
        if cursor.description is None:
            return pd.DataFrame()
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(rows, columns=columns)


def visao_completa_b8(client: MlflowClient, experimento_id: str) -> dict:
    """Recalcula o ranking completo de crescimento por local, para os dois pipelines.

    Returns:
        Dicionário {"store": DataFrame, "warehouse": DataFrame}, cada um com o
        ranking completo (não só o vencedor).
    """
    resultado = {}
    for pipeline in ["store", "warehouse"]:
        previsao = gerar_previsao_janela_3(pipeline, client, experimento_id)
        resultado[pipeline] = calcular_crescimento_yoy(previsao, pipeline)
    return resultado

def crescimento_geografico_clientes(meses_alvo: list, meses_ano_anterior: list, nivel: str = "estado") -> pd.DataFrame:
    """Calcula o crescimento YoY real de demanda, agregado por estado (ou cidade)."""
    colunas_agrupamento = "c.estado" if nivel == "estado" else "c.cidade, c.estado"

    meses_alvo_sql = ", ".join(f"'{m}'" for m in meses_alvo)
    meses_anterior_sql = ", ".join(f"'{m}'" for m in meses_ano_anterior)

    query = f"""
        SELECT
            {colunas_agrupamento},
            SUM(CASE WHEN date_trunc('month', o.placed_at) IN ({meses_alvo_sql}) THEN o.quantity ELSE 0 END) AS demanda_trimestre_alvo,
            SUM(CASE WHEN date_trunc('month', o.placed_at) IN ({meses_anterior_sql}) THEN o.quantity ELSE 0 END) AS demanda_ano_anterior
        FROM fct_orders o
        JOIN dim_clientes c ON o.customer_id = c.customer_id
        WHERE c.cidade != 'Sem Endereço Cadastrado'
        GROUP BY {colunas_agrupamento}
        HAVING demanda_ano_anterior > 0
    """
    df = run_query(query)
    df["crescimento_pct"] = (df["demanda_trimestre_alvo"] - df["demanda_ano_anterior"]) / df["demanda_ano_anterior"] * 100

    # Filtro de materialidade — mesma lógica do MAPE ponderado: não ranquear por
    # percentual antes de garantir volume-base relevante. Limiar: 75º percentil da
    # demanda do ano anterior, entre as regiões que tiveram alguma venda.
    limiar_volume = df["demanda_ano_anterior"].quantile(0.75)
    df_relevante = df[df["demanda_ano_anterior"] >= limiar_volume].copy()

    print(f"Limiar de materialidade (p75 de demanda_ano_anterior): {limiar_volume:.0f} unidades")
    print(f"{len(df_relevante)} de {len(df)} regiões passam no filtro de materialidade")

    return df_relevante.sort_values("crescimento_pct", ascending=False)

def presenca_existente() -> pd.DataFrame:
    """Lista todas as lojas e CDs ativos, com cidade/estado, para checagem de cobertura."""
    return run_query("""
        SELECT location_id, name, location_type, city, state
        FROM dim_locations
        WHERE is_active = true
    """)

def cruzar_cobertura(crescimento_geografico: pd.DataFrame, locais_existentes: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Verifica, para os top-N estados de maior crescimento, se já há presença da empresa."""
    top_estados = crescimento_geografico.head(top_n).copy()

    # dim_clientes.estado vem em maiúsculo (upper() no stg_addresses); dim_locations.state
    # não passa pela mesma normalização (stg_locations não tem upper()) — sem isso, a
    # comparação abaixo poderia falhar silenciosamente para algum estado no futuro,
    # mesmo tendo batido corretamente nesta execução.
    estados_com_local = set(locais_existentes["state"].str.strip().str.upper())

    def status_cobertura(row):
        if row["estado"].strip().upper() in estados_com_local:
            return "cobertura no estado"
        return "SEM COBERTURA"

    top_estados["status_cobertura"] = top_estados.apply(status_cobertura, axis=1)
    return top_estados

def main():
    """Roda a análise completa de necessidade e localização de novos CDs."""
    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    # Parte A — contexto completo
    print("=== Ranking completo de crescimento por local ===")
    rankings_b8 = visao_completa_b8(client, experimento.experiment_id)
    for pipeline, ranking in rankings_b8.items():
        print(f"\n--- {pipeline} ---")
        print(ranking.to_string(index=False))

    # Descobrir o trimestre-alvo real a partir da própria previsão
    previsao_referencia = gerar_previsao_janela_3("store", client, experimento.experiment_id)
    meses_alvo = sorted(previsao_referencia["mes_ref"].dt.strftime("%Y-%m-%d").unique())
    meses_ano_anterior = sorted(
        (pd.to_datetime(meses_alvo) - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    )

    # Parte B — crescimento geográfico real de demanda
    print(f"\n\n=== Crescimento real de demanda por cidade/estado do cliente ({meses_alvo}) ===")
    crescimento_geo = crescimento_geografico_clientes(meses_alvo, meses_ano_anterior, nivel="estado")
    print(crescimento_geo.head(15).to_string(index=False))

    # Parte C — cruzamento com cobertura existente
    print("\n\n=== Cobertura de presença nos top-10 estados de maior crescimento ===")
    locais = presenca_existente()
    cruzamento = cruzar_cobertura(crescimento_geo, locais, top_n=10)
    print(cruzamento[["estado", "crescimento_pct", "demanda_trimestre_alvo", "status_cobertura"]].to_string(index=False))

if __name__ == "__main__":
    main()
