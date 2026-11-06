"""Completa as métricas dos 4 modelos treinados e registra a decisão
do modelo escolhido por pipeline — tudo direto no MLflow, sem arquivo local.

Uso:
    # Fase 1 — só ver os números completos (roda quantas vezes precisar):
    python -m src.forecast.comparar_modelos

    # Fase 2 — depois de decidir, registrar a escolha com justificativa:
    python -m src.forecast.comparar_modelos \\
        --escolha-store lightgbm --motivo-store "Motivo da escolha em texto livre" \\
        --escolha-warehouse catboost --motivo-warehouse "Motivo da escolha em texto livre"
"""

import argparse

import mlflow
from mlflow.tracking import MlflowClient

EXPERIMENTO = "/Shared/forecast_lh_nautical/treino_modelos"
MODELOS = ["ridge", "random_forest", "lightgbm", "catboost"]
PIPELINES = ["store", "warehouse"]


def buscar_run_do_estudo(client: MlflowClient, experimento_id: str, nome_estudo: str):
    """Busca a run "pai" de um estudo pelo nome.

    Args:
        client: Cliente do MLflow.
        experimento_id: ID do experimento onde os estudos foram registrados.
        nome_estudo: Nome da run pai (ex.: "estudo_store_ridge").

    Returns:
        A run correspondente.

    Raises:
        RuntimeError: se nenhuma run com esse nome for encontrada.
    """
    runs = client.search_runs(
        experiment_ids=[experimento_id],
        filter_string=f"tags.mlflow.runName = '{nome_estudo}'",
    )
    if not runs:
        raise RuntimeError(f"Estudo não encontrado: {nome_estudo}")
    return runs[0]


def buscar_trial_vencedor(client: MlflowClient, experimento_id: str, run_id_pai: str):
    """Busca, entre as runs filhas de um estudo, a de menor MAE (o trial vencedor).

    Args:
        client: Cliente do MLflow.
        experimento_id: ID do experimento.
        run_id_pai: ID da run pai do estudo.

    Returns:
        A run filha vencedora.

    Raises:
        RuntimeError: se nenhum trial for encontrado.
    """
    filhas = client.search_runs(
        experiment_ids=[experimento_id],
        filter_string=f"tags.mlflow.parentRunId = '{run_id_pai}'",
        order_by=["metrics.mae ASC"],
        max_results=1,
    )
    if not filhas:
        raise RuntimeError(f"Nenhum trial encontrado para a run pai {run_id_pai}")
    return filhas[0]


def gerar_texto_decisao(pipeline: str, modelo_escolhido: str, resultados: dict, motivo: str) -> str:
    """Monta o texto (Markdown) com a tabela comparativa e a justificativa da escolha.

    Args:
        pipeline: "store" ou "warehouse".
        modelo_escolhido: nome do modelo escolhido.
        resultados: dicionário {modelo: {mae, rmse, mape}} dos 4 modelos do pipeline.
        motivo: justificativa em texto livre, fornecida pelo time via linha de comando.

    Returns:
        Texto em Markdown, pronto para ser anexado como artefato da run.
    """
    linhas = [
        f"# Decisão do modelo — pipeline {pipeline}",
        "",
        f"**Modelo escolhido:** {modelo_escolhido}",
        "",
        "## Comparação completa (trial vencedor de cada modelo)",
        "",
        "| Modelo | MAE | RMSE | MAPE |",
        "|---|---|---|---|",
    ]
    for nome_modelo, metricas in resultados.items():
        linhas.append(
            f"| {nome_modelo} | {metricas['mae']:.3f} | {metricas['rmse']:.3f} | {metricas['mape']:.2f}% |"
        )
    linhas += ["", "## Justificativa", "", motivo]
    return "\n".join(linhas)


def main():
    """Backfill as métricas faltantes e, se solicitado, registra a decisão do modelo."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--escolha-store", choices=MODELOS, default=None)
    parser.add_argument("--motivo-store", default="")
    parser.add_argument("--escolha-warehouse", choices=MODELOS, default=None)
    parser.add_argument("--motivo-warehouse", default="")
    args = parser.parse_args()

    mlflow.set_tracking_uri("databricks")
    client = MlflowClient()
    experimento = client.get_experiment_by_name(EXPERIMENTO)

    resultados_por_pipeline = {pipeline: {} for pipeline in PIPELINES}

    # Fase 1 — sempre roda: recupera o vencedor de cada estudo e completa as métricas.
    for pipeline in PIPELINES:
        for modelo in MODELOS:
            nome_estudo = f"estudo_{pipeline}_{modelo}"
            run_pai = buscar_run_do_estudo(client, experimento.experiment_id, nome_estudo)
            trial = buscar_trial_vencedor(client, experimento.experiment_id, run_pai.info.run_id)

            client.log_metric(run_pai.info.run_id, "melhor_rmse", trial.data.metrics["rmse"])
            client.log_metric(run_pai.info.run_id, "melhor_mape", trial.data.metrics["mape"])

            resultados_por_pipeline[pipeline][modelo] = {
                "mae": trial.data.metrics["mae"],
                "rmse": trial.data.metrics["rmse"],
                "mape": trial.data.metrics["mape"],
                "run_id": run_pai.info.run_id,
            }
            print(
                f"[{pipeline}] {modelo}: "
                f"MAE={trial.data.metrics['mae']:.3f} "
                f"RMSE={trial.data.metrics['rmse']:.3f} "
                f"MAPE={trial.data.metrics['mape']:.2f}%"
            )

    # Fase 2 — só roda para os pipelines em que uma escolha foi passada por linha de comando.
    escolhas = {"store": args.escolha_store, "warehouse": args.escolha_warehouse}
    motivos = {"store": args.motivo_store, "warehouse": args.motivo_warehouse}

    for pipeline, modelo_escolhido in escolhas.items():
        if not modelo_escolhido:
            print(f"\n[{pipeline}] Nenhuma escolha informada ainda — rode de novo com --escolha-{pipeline}.")
            continue

        run_id_escolhido = resultados_por_pipeline[pipeline][modelo_escolhido]["run_id"]
        client.set_tag(run_id_escolhido, "selecionado_b3", "true")

        texto = gerar_texto_decisao(pipeline, modelo_escolhido, resultados_por_pipeline[pipeline], motivos[pipeline])
        client.log_text(run_id_escolhido, texto, "decisao_modelo.md")
        print(f"\n[{pipeline}] Decisão registrada: {modelo_escolhido} (tag + artefato decisao_modelo.md na run {run_id_escolhido})")


if __name__ == "__main__":
    main()