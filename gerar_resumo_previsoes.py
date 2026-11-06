"""Resumo narrativo das previsões — corpus do RAG — LH Nautical.

Gera texto por template (não por LLM) a partir da tabela Gold de previsões
e do histórico real — evita risco de alucinação de número no
corpus que o RAG vai indexar.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.forecast.gerar_resumo_previsoes
"""

import os

import pandas as pd

from src.forecast.data import _conectar

CATALOGO = os.environ.get("DATABRICKS_CATALOG", "dev")
CAMINHO_SAIDA = "docs/rag_corpus/resumo_previsoes.md"

# Nomes de mês em português, fixos — evita depender de locale do sistema
# operacional (strftime("%B") varia por máquina/configuração regional).
MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
    7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Os dois produtos com sazonalidade confirmada (reconfirmados pós-reavaliação)
PRODUTOS_SAZONAIS = [
    {"pipeline": "store", "product_variant_id": 396, "nome": "Bateria Náutica 8635", "local": "Loja"},
    {"pipeline": "warehouse", "product_variant_id": 341, "nome": "Bateria Náutica 834", "local": "Centro de Distribuição"},
]

# Piso acima do qual um percentual de crescimento recebe nota de cautela — a base
# de dados é sintética e o período previsto cai numa janela de ramp-up sazonal
# (primavera, antes da alta temporada náutica); percentuais muito altos podem
# refletir uma base de comparação sazonalmente atípica, não necessariamente uma
# tendência de negócio real dessa magnitude. Investigação (duplicação de linha,
# cesta de produtos diferente) descartou essas duas causas como explicação
# completa — decisão do time: documentar como limitação conhecida, não bloquear
# a entrega perseguindo a causa exata.
LIMIAR_CRESCIMENTO_CAUTELA = 100.0


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


def formatar_mes(data: pd.Timestamp) -> str:
    """Formata uma data como 'mês/ano' em português, sem depender de locale."""
    return f"{MESES_PT[data.month]}/{data.year}"


def nota_cautela_crescimento(crescimento_pct: float) -> str:
    """Retorna uma nota de cautela quando o crescimento percentual é extremo.

    Ver LIMIAR_CRESCIMENTO_CAUTELA para o raciocínio completo. Evita apresentar
    percentuais muito altos como fato definitivo, sem escondê-los.
    """
    if abs(crescimento_pct) >= LIMIAR_CRESCIMENTO_CAUTELA:
        return (" Este percentual é elevado e deve ser interpretado com cautela — "
                "pode refletir uma base de comparação sazonalmente atípica, não "
                "necessariamente uma tendência de negócio dessa magnitude.")
    return ""


def resumo_por_local() -> pd.DataFrame:
    """Agrega a previsão total e a comparação YoY por local.

    Returns:
        DataFrame com location_id, location_name, location_type,
        previsto_trimestre, real_ano_anterior (pode ser nulo) e crescimento_pct.
    """
    previsao = run_query(f"""
        SELECT location_id, location_name, location_type,
               SUM(previsao_pontual) AS previsto_trimestre
        FROM {CATALOGO}.gold.fct_previsao_demanda
        GROUP BY location_id, location_name, location_type
    """)

    meses_previsao = run_query(f"""
        SELECT DISTINCT mes_ref FROM {CATALOGO}.gold.fct_previsao_demanda ORDER BY mes_ref
    """)
    meses_previsao["mes_ref"] = pd.to_datetime(meses_previsao["mes_ref"])
    meses_ano_anterior = (meses_previsao["mes_ref"] - pd.DateOffset(years=1)).dt.strftime("%Y-%m-%d").tolist()
    meses_sql = ", ".join(f"'{m}'" for m in meses_ano_anterior)

    real_ano_anterior = run_query(f"""
        SELECT location_id, SUM(quantidade_mes) AS real_ano_anterior
        FROM {CATALOGO}.gold.fct_demanda_mensal_produto_local
        WHERE mes_ref IN ({meses_sql})
        GROUP BY location_id
    """)

    resultado = previsao.merge(real_ano_anterior, on="location_id", how="left")
    resultado["crescimento_pct"] = (
        (resultado["previsto_trimestre"] - resultado["real_ano_anterior"]) / resultado["real_ano_anterior"] * 100
    )
    return resultado


def texto_local(linha: pd.Series) -> str:
    """Gera o parágrafo narrativo de um local, a partir da linha agregada."""
    if linha["location_type"] == "store":
        sujeito = linha["location_name"]  # já contém "Loja X" — sem prefixo redundante
    else:
        sujeito = f"O centro de distribuição {linha['location_name']}"

    if pd.isna(linha["real_ano_anterior"]) or linha["real_ano_anterior"] == 0:
        comparacao = "Não há histórico do mesmo trimestre no ano anterior disponível para comparação."
    else:
        tendencia = "aumento" if linha["crescimento_pct"] >= 0 else "redução"
        comparacao = (
            f"Isso representa um {tendencia} de {abs(linha['crescimento_pct']):.1f}% em relação "
            f"ao mesmo trimestre do ano anterior ({linha['real_ano_anterior']:.0f} unidades)."
            f"{nota_cautela_crescimento(linha['crescimento_pct'])}"
        )

    return (
        f"{sujeito} tem previsão de demanda total de {linha['previsto_trimestre']:.0f} unidades "
        f"para o próximo trimestre. {comparacao}"
    )


def texto_produto_sazonal(pipeline: str, product_variant_id: int, nome_produto: str, local: str) -> str:
    """Gera o parágrafo narrativo de um produto com sazonalidade confirmada."""
    previsao = run_query(f"""
        SELECT mes_ref,
               SUM(previsao_pontual) AS previsao_pontual,
               SUM(previsao_p10) AS previsao_p10,
               SUM(previsao_p90) AS previsao_p90
        FROM {CATALOGO}.gold.fct_previsao_demanda
        WHERE product_variant_id = {product_variant_id}
        GROUP BY mes_ref
        ORDER BY mes_ref
    """)
    previsao["mes_ref"] = pd.to_datetime(previsao["mes_ref"])

    if previsao.empty:
        return f"{nome_produto} ({local}): sem previsão disponível na tabela Gold no momento da geração deste resumo."

    meses_texto = ", ".join(formatar_mes(m) for m in previsao["mes_ref"])
    total_previsto = previsao["previsao_pontual"].sum()
    total_p10 = previsao["previsao_p10"].sum()
    total_p90 = previsao["previsao_p90"].sum()

    return (
        f"{nome_produto} ({local}) é um produto com sazonalidade estatisticamente confirmada, "
        f"identificada por meio de testes estatísticos de sazonalidade (autocorrelação anual, "
        f"decomposição de série temporal e teste de significância). A previsão para {meses_texto} "
        f"totaliza {total_previsto:.0f} unidades, com intervalo de confiança de 80% entre "
        f"{total_p10:.0f} e {total_p90:.0f} unidades. Esse volume é superior à maior parte do "
        f"histórico do produto, consistente com o período de preparação de embarcações que "
        f"antecede a alta temporada náutica de verão (dezembro a março)."
    )


def resumo_por_categoria() -> pd.DataFrame:
    """Agrega a previsão total e a comparação YoY por categoria de produto.

    Returns:
        DataFrame com category_name, previsto_trimestre, real_ano_anterior
        (pode ser nulo) e crescimento_pct.
    """
    previsao = run_query(f"""
        SELECT category_name, SUM(previsao_pontual) AS previsto_trimestre
        FROM {CATALOGO}.gold.fct_previsao_demanda
        GROUP BY category_name
    """)

    meses_previsao = run_query(f"""
        SELECT DISTINCT mes_ref FROM {CATALOGO}.gold.fct_previsao_demanda ORDER BY mes_ref
    """)
    meses_previsao["mes_ref"] = pd.to_datetime(meses_previsao["mes_ref"])
    meses_ano_anterior = (meses_previsao["mes_ref"] - pd.DateOffset(years=1)).dt.strftime("%Y-%m-%d").tolist()
    meses_sql = ", ".join(f"'{m}'" for m in meses_ano_anterior)

    real_ano_anterior = run_query(f"""
        SELECT category_name, SUM(quantidade_mes) AS real_ano_anterior
        FROM {CATALOGO}.gold.fct_demanda_mensal_produto_local
        WHERE mes_ref IN ({meses_sql})
        GROUP BY category_name
    """)

    resultado = previsao.merge(real_ano_anterior, on="category_name", how="left")
    resultado["crescimento_pct"] = (
        (resultado["previsto_trimestre"] - resultado["real_ano_anterior"]) / resultado["real_ano_anterior"] * 100
    )
    return resultado


def texto_categoria(linha: pd.Series) -> str:
    """Gera o parágrafo narrativo de uma categoria de produto."""
    if pd.isna(linha["real_ano_anterior"]) or linha["real_ano_anterior"] == 0:
        comparacao = "Não há histórico do mesmo trimestre no ano anterior disponível para comparação."
    else:
        tendencia = "aumento" if linha["crescimento_pct"] >= 0 else "redução"
        comparacao = (
            f"Isso representa um {tendencia} de {abs(linha['crescimento_pct']):.1f}% em relação "
            f"ao mesmo trimestre do ano anterior ({linha['real_ano_anterior']:.0f} unidades)."
            f"{nota_cautela_crescimento(linha['crescimento_pct'])}"
        )

    return (
        f"A categoria {linha['category_name']} tem previsão de demanda total de "
        f"{linha['previsto_trimestre']:.0f} unidades para o próximo trimestre. {comparacao}"
    )


def destaques_previsao() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Identifica as 5 combinações produto×loja com maior alta e maior queda prevista.

    Returns:
        Tupla (top_altas, top_quedas), cada uma com product_name, location_name,
        previsto_trimestre, real_ano_anterior e crescimento_pct.
    """
    previsao = run_query(f"""
        SELECT product_variant_id, product_name, location_id, location_name,
               SUM(previsao_pontual) AS previsto_trimestre
        FROM {CATALOGO}.gold.fct_previsao_demanda
        GROUP BY product_variant_id, product_name, location_id, location_name
    """)

    meses_previsao = run_query(f"""
        SELECT DISTINCT mes_ref FROM {CATALOGO}.gold.fct_previsao_demanda ORDER BY mes_ref
    """)
    meses_previsao["mes_ref"] = pd.to_datetime(meses_previsao["mes_ref"])
    meses_ano_anterior = (meses_previsao["mes_ref"] - pd.DateOffset(years=1)).dt.strftime("%Y-%m-%d").tolist()
    meses_sql = ", ".join(f"'{m}'" for m in meses_ano_anterior)

    real_ano_anterior = run_query(f"""
        SELECT product_variant_id, location_id, SUM(quantidade_mes) AS real_ano_anterior
        FROM {CATALOGO}.gold.fct_demanda_mensal_produto_local
        WHERE mes_ref IN ({meses_sql})
        GROUP BY product_variant_id, location_id
    """)

    combinado = previsao.merge(real_ano_anterior, on=["product_variant_id", "location_id"], how="inner")
    combinado = combinado[combinado["real_ano_anterior"] > 0]  # evita divisão por zero
    combinado["crescimento_pct"] = (
        (combinado["previsto_trimestre"] - combinado["real_ano_anterior"]) / combinado["real_ano_anterior"] * 100
    )

    top_altas = combinado.sort_values("crescimento_pct", ascending=False).head(5)
    top_quedas = combinado.sort_values("crescimento_pct", ascending=True).head(5)
    return top_altas, top_quedas


def texto_destaques(top_altas: pd.DataFrame, top_quedas: pd.DataFrame) -> str:
    """Gera o parágrafo narrativo dos destaques de alta e queda prevista."""
    linhas_altas = "; ".join(
        f"{r['product_name']} na {r['location_name']} (+{r['crescimento_pct']:.1f}%)"
        for _, r in top_altas.iterrows()
    )
    linhas_quedas = "; ".join(
        f"{r['product_name']} na {r['location_name']} ({r['crescimento_pct']:.1f}%)"
        for _, r in top_quedas.iterrows()
    )
    return (
        f"As combinações de produto e local com maior alta prevista, em relação ao mesmo "
        f"trimestre do ano anterior, são: {linhas_altas}. As combinações com maior queda "
        f"prevista são: {linhas_quedas}. Os percentuais de alta mais extremos devem ser "
        f"interpretados com cautela — a base de dados é sintética, e comparações contra "
        f"uma base pequena ou sazonalmente atípica podem gerar percentuais desproporcionais."
    )


def main():
    """Gera o resumo narrativo completo e escreve em docs/rag_corpus/resumo_previsoes.md."""
    os.makedirs(os.path.dirname(CAMINHO_SAIDA), exist_ok=True)

    locais = resumo_por_local()
    categorias = resumo_por_categoria()
    top_altas, top_quedas = destaques_previsao()

    linhas_markdown = [
        "# Resumo de Previsões de Demanda — LH Nautical",
        "",
        "Documento gerado automaticamente a partir da tabela de previsões de produção. "
        "Reflete a execução mais recente do processo de geração de previsões.",
        "",
        "## Visão Geral por Local",
        "",
    ]

    for _, linha in locais.sort_values("location_name").iterrows():
        linhas_markdown.append(f"### {linha['location_name']}")
        linhas_markdown.append("")
        linhas_markdown.append(texto_local(linha))
        linhas_markdown.append("")

    linhas_markdown.append("## Visão Geral por Categoria de Produto")
    linhas_markdown.append("")

    for _, linha in categorias.sort_values("category_name").iterrows():
        linhas_markdown.append(f"### {linha['category_name']}")
        linhas_markdown.append("")
        linhas_markdown.append(texto_categoria(linha))
        linhas_markdown.append("")

    linhas_markdown.append("## Destaques da Previsão: Maiores Altas e Quedas")
    linhas_markdown.append("")
    linhas_markdown.append(texto_destaques(top_altas, top_quedas))
    linhas_markdown.append("")

    linhas_markdown.append("## Produtos com Sazonalidade Confirmada")
    linhas_markdown.append("")

    for produto in PRODUTOS_SAZONAIS:
        linhas_markdown.append(f"### {produto['nome']} ({produto['local']})")
        linhas_markdown.append("")
        linhas_markdown.append(
            texto_produto_sazonal(produto["pipeline"], produto["product_variant_id"], produto["nome"], produto["local"])
        )
        linhas_markdown.append("")

    with open(CAMINHO_SAIDA, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas_markdown))

    print(f"Resumo narrativo gerado: {CAMINHO_SAIDA} ({len(locais)} locais, {len(categorias)} categorias, "
          f"5+5 destaques, {len(PRODUTOS_SAZONAIS)} produtos sazonais)")


if __name__ == "__main__":
    main()