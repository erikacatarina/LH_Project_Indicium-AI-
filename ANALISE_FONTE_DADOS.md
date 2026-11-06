# Análise da Fonte de Dados — LH Nautical

> ⚠️ **Nota de atualização:** os nomes de tabelas fato/dimensão citados
> neste documento (`fct_vendas`, `dim_cliente`, `dim_produto`, `dim_localizacao`,
> `dim_funcionario`) refletem o planejamento inicial da primeira entrega e foram **supersedidos**
> pela modelagem final construída nessa etapa. Tabela de correspondência:
>
> | Citado neste documento | Nome real construído |
> |---|---|
> | `fct_vendas` | `fct_orders` (grão item) + `fct_returns` (devoluções) + `fct_desempenho_mensal_produto_vendedor` (snapshot mensal) |
> | `dim_cliente` | `dim_clientes` |
> | `dim_produto` | `dim_produtos` |
> | `dim_localizacao` | `dim_locations` |
> | `dim_funcionario` | `dim_employee` |
>
> O conteúdo técnico abaixo (classificação de tabelas, schemas, joins) continua válido — apenas os nomes de destino mudaram.

> Documento de referência para a ingestão Bronze

## 1. Visão Geral

Esta análise mapeia as 24 tabelas disponíveis no banco transacional SQL Server da LH Nautical, classificando cada uma quanto à relevância para o escopo do projeto — análises de faturamento, visibilidade de canal, comportamento de cliente, sazonalidade e rentabilidade por produto.

## 2. Método de Acesso e Autenticação

| Item | Definição |
|---|---|
| Tipo de banco | SQL Server |
| Ferramenta de inspeção | DBeaver |
| Autenticação de inspeção | Usuário e senha (uso local/exploratório) |
| Método de ingestão (pipeline) | JDBC |
| Autenticação da ingestão | Databricks Secrets |

> As credenciais usadas para inspeção via DBeaver são exclusivamente para fins exploratórios. O pipeline de ingestão (`ingest_bronze.py`) nunca terá usuário/senha no código, todas as credenciais são lidas via `dbutils.secrets.get()` a partir do secret scope configurado.

## 3. Critério de Classificação

Uma tabela é classificada como **Incluir** se atender a pelo menos um dos critérios:

- É consumida diretamente por uma tabela fato ou dimensão do Star Schema
- Alimenta colunas pré-calculadas da `fct_vendas` (ex: status de pagamento, status fiscal)
- É necessária para resolver alguma das 6 dores de negócio mapeadas

Tabelas relacionadas a compras de fornecedores, estoque interno e atributos de catálogo sem uso nas dores mapeadas foram classificadas como **Excluir**, fora do escopo deste projeto.

## 4. Inventário de Tabelas

| Tabela | Qtd. Linhas | Data Mín. | Data Máx. | Classificação | Justificativa |
|---|---|---|---|---|---|
| orders | 50.000 | 01/01/2020 | 31/12/2026 | **Incluir** | Tabela fato central — origem de `fct_vendas` |
| order_items | 150.321 | — | — | **Incluir** | Granularidade da `fct_vendas` (item de pedido) |
| payments | 54.635 | 01/01/2020 | 31/12/2026 | **Incluir** | Origem de `metodo_pagamento`, `status_pagamento`, `flag_pago` — resolve Dor 1 |
| returns | 1.000 | 18/01/2020 | 27/01/2027 | **Incluir** | Origem de `flag_devolvido`, `valor_devolvido`, `motivo_devolucao` |
| return_items | 1.409 | — | — | **Incluir** | Granularidade de devolução por item — vincula com `order_items` |
| fiscal_invoices | 35.079 | 01/01/2020 | 01/01/2027 | **Incluir** | Origem de `flag_nfe_autorizada` — resolve Dor 1 |
| customers | 2.000 | 30/03/2020 | 31/12/2026 | **Incluir** | Origem de `dim_cliente` |
| products | 500 | 25/04/2020 | 31/12/2026 | **Incluir** | Origem de `dim_produto` |
| product_variants | 1.009 | 26/04/2020 | 31/12/2026 | **Incluir** | Origem de `dim_produto` (sku, preço, custo) |
| categories | 14 | 17/09/2023 | 30/08/2026 | **Incluir** | Hierarquia de categorias em `dim_produto` |
| brands | 12 | 28/08/2022 | 07/12/2026 | **Incluir** | Atributo `marca` em `dim_produto` |
| locations | 6 | 13/06/2021 | 08/12/2026 | **Incluir** | Origem de `dim_localizacao` |
| employees | 15 | 26/09/2020 | 27/12/2026 | **Incluir** | Origem de `dim_funcionario` — vínculo via `salesperson_id` |
| addresses | 3.998 | — | — | Excluir | Fora do escopo das dores mapeadas |
| attributes | 8 | — | — | Excluir | Atributos de catálogo sem uso nas dimensões definidas |
| variant_attribute_values | 2.018 | — | — | Excluir | Depende de `attributes`, fora do escopo |
| suppliers | 25 | 12/10/2023 | 09/12/2023 | Excluir | Cadeia de suprimentos — fora do escopo de vendas |
| product_suppliers | 1.520 | 08/03/2020 | 31/12/2026 | Excluir | Cadeia de suprimentos — fora do escopo |
| purchase_orders | 2.000 | 01/01/2020 | 31/12/2026 | Excluir | Compras a fornecedores — fora do escopo |
| purchase_order_items | 6.059 | — | — | Excluir | Depende de `purchase_orders`, fora do escopo |
| goods_receipts | 1.548 | 15/01/2020 | 22/01/2027 | Excluir | Recebimento de mercadorias — fora do escopo |
| goods_receipt_items | 4.733 | — | — | Excluir | Depende de `goods_receipts`, fora do escopo |
| stock_levels | 6.054 | 27/11/2020 | 27/01/2027 | Excluir | Controle de estoque — fora do escopo de vendas|
| stock_movements | 117.427 | — | — | Excluir | Movimentação de estoque — fora do escopo |

## 5. Resumo

- **13 tabelas** classificadas como **Incluir** — cobrem a tabela fato e as 6 dimensões do Star Schema
- **11 tabelas** classificadas como **Excluir** — relacionadas a cadeia de suprimentos, estoque interno e atributos de catálogo não utilizados nas dores mapeadas
- Volume total das tabelas incluídas: aproximadamente **293.000 linhas**