"""Geração dos gráficos do Relatório de Análise e Previsão — LH Nautical.

Cada função recebe os dados já calculados pelas seções do relatório (não
recalcula nada) e salva um PNG. Módulo separado por responsabilidade única —
gerar_relatorio_previsao.py fica só com a orquestração e o texto.
"""

import matplotlib
matplotlib.use("Agg")  # sem interface gráfica — roda em qualquer terminal/Job
import matplotlib.pyplot as plt
import pandas as pd


def grafico_previsao_por_pipeline(totais: pd.DataFrame, caminho_saida: str):
    """Gráfico de barras: previsão total por tipo de local (Loja x Centro de Distribuição)."""
    rotulos = ["Lojas" if t == "store" else "Centros de Distribuição" for t in totais["location_type"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(rotulos, totais["previsto_trimestre"], color=["#2E7D32", "#1565C0"])
    ax.set_ylabel("Unidades previstas (3 meses)")
    ax.set_title("Previsão de Demanda por Tipo de Local")
    for i, valor in enumerate(totais["previsto_trimestre"]):
        ax.text(i, valor, f"{valor:.0f}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=120)
    plt.close(fig)


def grafico_crescimento_por_local(crescimento: pd.DataFrame, titulo: str, caminho_saida: str):
    """Gráfico de barras horizontais: crescimento YoY por local, ordenado."""
    dados = crescimento.sort_values("crescimento_pct")
    fig, ax = plt.subplots(figsize=(7, max(3, 0.4 * len(dados))))
    cores = ["#C62828" if v < 0 else "#2E7D32" for v in dados["crescimento_pct"]]
    ax.barh(dados["location_name"], dados["crescimento_pct"], color=cores)
    ax.set_xlabel("Crescimento YoY (%)")
    ax.set_title(titulo)
    ax.axvline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=120)
    plt.close(fig)


def grafico_cobertura_novos_cds(cruzamento: pd.DataFrame, caminho_saida: str):
    """Gráfico de barras: crescimento de demanda por estado, colorido por cobertura existente."""
    dados = cruzamento.sort_values("crescimento_pct")
    cores = ["#2E7D32" if s == "COM COBERTURA" else "#C62828" for s in dados["status_cobertura"]]
    fig, ax = plt.subplots(figsize=(7, max(3, 0.4 * len(dados))))
    ax.barh(dados["estado"], dados["crescimento_pct"], color=cores)
    ax.set_xlabel("Crescimento de demanda de cliente (%)")
    ax.set_title("Crescimento por Estado x Cobertura da Rede Atual")
    ax.axvline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=120)
    plt.close(fig)