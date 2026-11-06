# Validação de Escrita — Camada Bronze

## 1. Tabelas Criadas

Confirmadas 13 tabelas na camada dev.bronze, todas no formato Delta, conforme escopo definido em ANALISE_FONTE_DADOS.md.

## 2. Validação de Schema

Schema de cada tabela conferido manualmente contra SCHEMA_MAPPING.md.
Destaque: payments.installments confirmado como smallint, conforme especificado. Não houve regressão para IntegerType por inferência
automática, validando a eficácia do schema explícito.

## 3. Validação de Contagem de Linhas

| Tabela               | Linhas Esperadas | Linhas Reais | Status |
| -------------------- | ---------------- | ------------ | ------ |
| sql_orders           | 50.000           | 50.000       | OK     |
| sql_order_items      | 150.321          | 150.321      | OK     |
| sql_payments         | 54.635           | 54.635       | OK     |
| sql_returns          | 1.000            | 1.000        | OK     |
| sql_return_items     | 1.409            | 1.409        | OK     |
| sql_fiscal_invoices  | 35.079           | 35.079       | OK     |
| sql_customers        | 2000             | 2000         | OK     |
| sql_products         | 500              | 500          | OK     |
| sql_product_variants | 1.009            | 1.009        | OK     |
| sql_categories       | 14               | 14           | OK     |
| sql_brands           | 12               | 12           | OK     |
| sql_locations        | 6                | 6            | OK     |
| sql_employees        | 15               | 15           | OK     |

## 4. Validação de Formato e Otimização

Confirmado via DESCRIBE DETAIL: todas as tabelas em formato delta, sem particionamento físico (partitionColumns vazio), sem clustering
ativo (clusterByAuto: false), conforme decisão documentada em OTIMIZACAO.md. Auto-otimização nativa do Databricks suficiente para
o volume atual do projeto.
