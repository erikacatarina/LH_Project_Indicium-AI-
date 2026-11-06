"""Relatório de Análise e Previsão — consolidação automatizada mensal — LH Nautical.

Responde as 4 perguntas de negócio oficiais, reaproveitando
as funções já construídas em cada tarefa anterior — este script não
recalcula nada por conta própria, só orquestra e formata.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.relatorio.gerar_relatorio_previsao
"""

from src.relatorio.graficos import (
    grafico_cobertura_novos_cds,
    grafico_crescimento_por_local,
    grafico_previsao_por_pipeline,
)

import os
import mlflow
from datetime import datetime

import pandas as pd
from mlflow.tracking import MlflowClient

from src.forecast.data import _conectar
from src.forecast.gerar_resumo_previsoes import PRODUTOS_SAZONAIS, texto_produto_sazonal
from src.forecast.crescimento_por_local import (
    EXPERIMENTO_MODELOS,
    calcular_crescimento_yoy,
    gerar_previsao_janela_3,
)
from src.forecast.analise_novos_cds import (
    crescimento_geografico_clientes,
    cruzar_cobertura,
    presenca_existente,
)

CATALOGO = os.environ.get("DATABRICKS_CATALOG", "dev")
PASTA_RELATORIOS = "docs/relatorios"
CAMINHO_LATEST = "docs/Relatorio_Analise_Previsao.md"


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

def secao_previsao_e_sazonalidade(pasta_graficos: str) -> str:
    """Monta a Seção 1: totais previstos por pipeline + os 2 produtos sazonais confirmados."""
    totais = run_query(f"""
        SELECT location_type, SUM(previsao_pontual) AS previsto_trimestre
        FROM {CATALOGO}.gold.fct_previsao_demanda
        GROUP BY location_type
    """)

    caminho_grafico = f"{pasta_graficos}/previsao_por_pipeline.png"
    grafico_previsao_por_pipeline(totais, caminho_grafico)

    linhas = ["## 1. Previsão de Demanda (3 meses) e Sazonalidade", ""]
    linhas.append(f"![Previsão por tipo de local]({caminho_grafico.split('docs/')[-1]})")
    linhas.append("")
    for _, linha in totais.iterrows():
        rotulo = "Lojas" if linha["location_type"] == "store" else "Centros de Distribuição"
        linhas.append(f"- **{rotulo}:** {linha['previsto_trimestre']:.0f} unidades previstas para o próximo trimestre.")
    linhas.append("")
    linhas.append(
        "**Leitura de negócio:** esses volumes orientam diretamente o planejamento de compras e "
        "reposição de estoque para o trimestre — números abaixo do previsto sinalizam risco de ruptura, "
        "acima do previsto sinalizam capital parado em estoque excedente."
    )
    linhas.append("")
    linhas.append("### Produtos com sazonalidade estatisticamente confirmada")
    linhas.append("")

    for produto in PRODUTOS_SAZONAIS:
        texto = texto_produto_sazonal(
            produto["pipeline"], produto["product_variant_id"], produto["nome"], produto["local"]
        )
        linhas.append(f"**{produto['nome']} ({produto['local']}):** {texto}")
        linhas.append("")

    return "\n".join(linhas)

def buscar_texto_decisao_modelo(client: MlflowClient, experimento_id: str, pipeline: str) -> str:
    """Busca o artefato decisao_modelo.md da run marcada como campeã —
    reaproveita a justificativa já escrita, sem recalcular a comparação de novo."""
    runs = client.search_runs(experiment_ids=[experimento_id], filter_string="tags.selecionado_b3 = 'true'")
    runs_pipeline = [r for r in runs if r.data.tags.get("mlflow.runName", "").startswith(f"estudo_{pipeline}_")]

    if not runs_pipeline:
        return f"[Modelo campeão ainda não confirmado para o pipeline {pipeline} neste catálogo.]"

    caminho_local = client.download_artifacts(runs_pipeline[0].info.run_id, "decisao_modelo.md", dst_path="/tmp")
    with open(caminho_local, encoding="utf-8") as arquivo:
        return arquivo.read()

def secao_viabilidade_modelos(client: MlflowClient, experimento_id: str) -> str:
    """Monta a Seção 2, a partir dos artefatos de decisão já escritos."""
    linhas = ["## 2. Viabilidade e Desempenho dos Modelos de Regressão", ""]
    for pipeline, rotulo in [("store", "Loja"), ("warehouse", "Centro de Distribuição")]:
        linhas.append(f"### {rotulo}")
        linhas.append("")
        linhas.append(buscar_texto_decisao_modelo(client, experimento_id, pipeline))
        linhas.append("")
    return "\n".join(linhas)

def secao_crescimento_por_local(client: MlflowClient, experimento_id: str, pasta_graficos: str) -> str:
    """Monta a Seção 3, reaproveitando gerar_previsao_janela_3/calcular_crescimento_yoy."""
    linhas = ["## 3. Crescimento da Demanda por Centro de Distribuição e Ponto de Venda", ""]

    for pipeline, rotulo in [("store", "Lojas"), ("warehouse", "Centros de Distribuição")]:
        previsao = gerar_previsao_janela_3(pipeline, client, experimento_id)
        crescimento = calcular_crescimento_yoy(previsao, pipeline).sort_values("crescimento_pct", ascending=False)

        caminho_grafico = f"{pasta_graficos}/crescimento_{pipeline}.png"
        grafico_crescimento_por_local(crescimento, f"Crescimento YoY — {rotulo}", caminho_grafico)

        linhas.append(f"### {rotulo}")
        linhas.append("")
        linhas.append(f"![Crescimento YoY {rotulo}]({caminho_grafico.split('docs/')[-1]})")
        linhas.append("")
        for _, linha in crescimento.iterrows():
            linhas.append(f"- **{linha['location_name']}:** {linha['crescimento_pct']:.1f}% de crescimento YoY.")
        vencedor = crescimento.iloc[0]
        linhas.append(f"\n**Maior crescimento:** {vencedor['location_name']} ({vencedor['crescimento_pct']:.1f}%).")
        linhas.append(
            "\n**Leitura de negócio:** o local de maior crescimento é candidato prioritário para reforço de "
            "capacidade (estoque de segurança maior, possível ampliação de espaço) antes do início do trimestre."
        )
        linhas.append("")

    return "\n".join(linhas)

def secao_novos_cds(pasta_graficos: str) -> str:
    """Monta a Seção 4, reaproveitando as funções de análise geográfica."""
    meses_previsao = run_query(f"SELECT DISTINCT mes_ref FROM {CATALOGO}.gold.fct_previsao_demanda ORDER BY mes_ref")
    meses_previsao["mes_ref"] = pd.to_datetime(meses_previsao["mes_ref"])
    meses_alvo = sorted(meses_previsao["mes_ref"].dt.strftime("%Y-%m-%d").tolist())
    meses_ano_anterior = sorted((pd.to_datetime(meses_alvo) - pd.DateOffset(years=1)).strftime("%Y-%m-%d").tolist())

    crescimento_geo = crescimento_geografico_clientes(meses_alvo, meses_ano_anterior, nivel="estado")
    locais = presenca_existente()
    cruzamento = cruzar_cobertura(crescimento_geo, locais, top_n=10)

    caminho_grafico = f"{pasta_graficos}/cobertura_novos_cds.png"
    grafico_cobertura_novos_cds(cruzamento, caminho_grafico)

    linhas = ["## 4. Necessidade e Localização de Novos Centros de Distribuição", ""]
    linhas.append(f"![Cobertura por estado]({caminho_grafico.split('docs/')[-1]})")
    linhas.append("")
    linhas.append("### Estados avaliados (maior crescimento de demanda de cliente, com volume relevante)")
    linhas.append("")
    for _, linha in cruzamento.iterrows():
        linhas.append(
            f"- **{linha['estado']}:** {linha['crescimento_pct']:.1f}% — {linha['status_cobertura']}"
        )

    algum_sem_cobertura = (cruzamento["status_cobertura"] == "SEM COBERTURA").any()
    algum_crescimento_positivo = (cruzamento["crescimento_pct"] > 0).any()

    linhas.append("")
    if algum_sem_cobertura and algum_crescimento_positivo:
        linhas.append(
            "**Conclusão:** há estados com crescimento de demanda e sem cobertura da rede atual — "
            "avaliar como candidatos a novo Centro de Distribuição (ver detalhamento acima)."
        )
    else:
        linhas.append(
            "**Conclusão:** não há evidência, nesta análise, que justifique a abertura de um novo "
            "Centro de Distribuição — os estados de maior volume já têm cobertura da rede atual, "
            "ou não apresentam crescimento real de demanda."
        )

    return "\n".join(linhas)

def main():
    """Gera o Relatório de Análise e Previsão completo e escreve em docs/."""
    mlflow.set_tracking_uri("databricks")
    os.makedirs(PASTA_RELATORIOS, exist_ok=True)

    mes_referencia = datetime.now().strftime("%Y-%m")
    pasta_graficos = f"{PASTA_RELATORIOS}/graficos_{mes_referencia}"
    os.makedirs(pasta_graficos, exist_ok=True)

    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO_MODELOS)

    conteudo = [
        "# Relatório de Análise e Previsão — LH Nautical",
        "",
        f"Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M')}. "
        f"Catálogo de origem: `{CATALOGO}`.",
        "",
        secao_previsao_e_sazonalidade(pasta_graficos),
        "",
        secao_viabilidade_modelos(client, experimento.experiment_id),
        "",
        secao_crescimento_por_local(client, experimento.experiment_id, pasta_graficos),
        "",
        secao_novos_cds(pasta_graficos),
    ]

    texto_final = "\n".join(conteudo)

    with open(CAMINHO_LATEST, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto_final)

    print(f"Relatório gerado: {CAMINHO_LATEST}")


if __name__ == "__main__":
    main()
