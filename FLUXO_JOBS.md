# Fluxo de Jobs - Orquestração Databricks Workflows

## 1. Visão Geral

O pipeline de ingestão Bronze é orquestrado via Databricks Workflows,
configurado como código no databricks.yml (Databricks Asset Bundles).
O deploy é automatizado via Bitbucket Pipelines em cada merge para
dev ou main.

## 2. Estrutura do Job

**Nome do job:** `lh_nautical_bronze_ingestion`
**Renderização por ambiente:**

- Desenvolvimento: `dev_lh_nautical_bronze_ingestion`
- Produção: `prd_lh_nautical_bronze_ingestion`

## 3. Diagrama de Execução

```
┌──────────────────────────────────────────────────────────┐
│                    TRIGGER                               │
│          Schedule diário ou execução manual              │
└─────────────────────┬────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│                  run_ingestion                           │
│                                                          │
│   Script : src/ingestion/ingest_bronze.py                │
│   Compute: Serverless (Free Edition)                     │
│                                                          │
│   1. conectar_jdbc()          → monta URL + credenciais  │
│   2. extrair_tabela()   × 13  → lê cada tabela via JDBC  │
│   3. aplicar_schema()   × 13  → força tipos corretos     │
│   4. escrever_bronze()  × 13  → grava em dev/prd.bronze  │
└───────────┬──────────────────────────┬───────────────────┘
            │                          │
            ▼                          ▼
     ┌─────────────┐           ┌──────────────┐
     │   SUCESSO   │           │    FALHA     │
     │             │           │              │
     │  Log OK     │           │  Retry × 1   │
     │  Encerra    │           │  (5 min)     │
     └─────────────┘           └──────┬───────┘
                                      │
                          ┌───────────┴───────────┐
                          │                       │
                          ▼                       ▼
                   ┌─────────────┐       ┌──────────────────┐
                   │   SUCESSO   │       │   FALHA FINAL    │
                   │             │       │                  │
                   │  Log OK     │       │  Alerta e-mail   │
                   │  Encerra    │       │  Intervenção     │
                   └─────────────┘       │  manual          │
                                         └──────────────────┘
```

## 4. Estratégia de Retry

- **Máximo de tentativas:** 2 (1 execução original + 1 retry automático)
- **Intervalo entre tentativas:** 5 minutos
- **Justificativa:** falhas transitórias de conexão com o banco SQL
  Server (ex: timeout de rede) são resolvidas em uma nova tentativa;
  falhas persistentes (ex: schema incompatível) precisam de
  intervenção manual e não devem ser re-tentadas indefinidamente

## 5. Fluxo de Deploy (CI/CD)

```
Desenvolvedor faz push para feature/*
            │
            ▼
    Pull Request → dev
            │
            ▼  (merge aprovado)
  Bitbucket Pipelines
            │
            ▼
  databricks bundle deploy --target dev
            │
            ▼
  Job disponível no workspace DEV
            │
            (validação e testes)
            │
            ▼
    Pull Request dev → main
            │
            ▼  (merge com 2 aprovações)
  Bitbucket Pipelines
            │
            ▼
  databricks bundle deploy --target prd
            │
            ▼
  Job disponível no workspace PRD
```

---

## 6. Compute

**Tipo:** Serverless compute — único suportado no Databricks Free Edition.  
**Configuração:** gerenciada automaticamente pelo Databricks, sem configuração manual de `spark_version` ou `num_workers`.

```yaml
# Configuração no databricks.yml
tasks:
  - task_key: run_ingestion
    environment_key: default
    spark_python_task:
      python_file: ./src/ingestion/ingest_bronze.py

environments:
  - environment_key: default
    spec:
      environment_version: "2"
```

---

## 7. Evolução Futura - Opção B (Paralelização)

Caso o volume de dados cresça significativamente (ver `ESCALABILIDADE.md`),
a estrutura do job pode ser expandida para execução paralela por tabela:

```
Job: lh_nautical_bronze_ingestion
│
├── Task: ingest_customers          ──────┐
├── Task: ingest_products           ──────┤  sem dependência
├── Task: ingest_categories         ──────┤  entre si →
├── Task: ingest_brands             ──────┤  rodam em
├── Task: ingest_locations          ──────┤  paralelo
├── Task: ingest_employees          ──────┤
├── Task: ingest_orders             ──────┤
├── Task: ingest_payments           ──────┘
│
├── Task: ingest_order_items        → depende de ingest_orders
├── Task: ingest_return_items       → depende de ingest_returns
└── Task: ingest_fiscal_invoices    → depende de ingest_orders
```

Cada task sem dependência entre si rodaria em paralelo, reduzindo
o tempo total de execução proporcionalmente ao número de workers
disponíveis no cluster.