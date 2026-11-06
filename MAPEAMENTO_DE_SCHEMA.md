# Mapeamento de Schema — LH Nautical

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
> O conteúdo técnico abaixo (classificação de tabelas, schemas, joins) continua válido — apenas os nomes de destino mudaram; PKs/FKs/tipos de coluna documentados abaixo continuam corretos.


## 1. Visão Geral

Este documento consolida o resultado das 4 ações de revalidação executadas via DBeaver:

- **Ação 1** — Revalidação de schema das tabelas `categories`, `brands`, `addresses`, `attributes` (corrigiu erro de copy-paste do mapeamento inicial)
- **Ação 2** — Identificação de Chaves Primárias (PK) das 13 tabelas em escopo
- **Ação 3** — Identificação de Chaves Estrangeiras (FK) das 13 tabelas em escopo
- **Ação 4** — Schema completo com tipos SQL Server e equivalente Spark/Delta

## 2. Achados da Revalidação (Ação 1)

O mapeamento inicial apresentava `categories` com o mesmo schema de `brands`, e `addresses` com o mesmo schema de `attributes` — erro de copy-paste durante a extração. A revalidação confirmou:

- `attributes` (`id`, `name`, `data_type`) estava correto no mapeamento original.

## 3. Schema Detalhado por Tabela

### `orders`

Tabela fato central — origem de `fct_vendas`. Granularidade: pedido.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `location_id` → `locations.id`
- `customer_id` → `customers.id`
- `salesperson_id` → `employees.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `order_number` | nvarchar | 20 | — | — | Não | `StringType` |
| `channel` | nvarchar | 10 | — | — | Não | `StringType` |
| `customer_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `salesperson_id` | int | — | 10 | 0 | Sim | `IntegerType` |
| `location_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `status` | nvarchar | 10 | — | — | Não | `StringType` |
| `subtotal` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `discount_amount` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `total` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `placed_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `order_items`

Granularidade da `fct_vendas` (item de pedido). **Não possui coluna de data** — extração dependente do `order_id`.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `order_id` → `orders.id`
- `product_variant_id` → `product_variants.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `order_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `product_variant_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `quantity` | decimal | — | 14 | 3 | Não | `DecimalType(14,3)` |
| `unit_price` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `icms_rate` | decimal | — | 5 | 2 | Não | `DecimalType(5,2)` |
| `ipi_rate` | decimal | — | 5 | 2 | Não | `DecimalType(5,2)` |
| `line_total` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |

### `payments`

Origem de `metodo_pagamento`, `status_pagamento`, `flag_pago` na `fct_vendas`. Agregação por `order_id` necessária (produto cartesiano).

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `order_id` → `orders.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `order_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `method` | nvarchar | 20 | — | — | Não | `StringType` |
| `installments` | smallint | — | 5 | 0 | Não | `ShortType` |
| `amount` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `status` | nvarchar | 10 | — | — | Não | `StringType` |
| `paid_at` | datetime2 | — | — | — | Sim | `TimestampType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `returns`

Origem de `flag_devolvido`, `valor_devolvido`, `motivo_devolucao` na `fct_vendas`.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `customer_id` → `customers.id`
- `received_at_location_id` → `locations.id`
- `order_id` → `orders.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `return_number` | nvarchar | 20 | — | — | Não | `StringType` |
| `order_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `customer_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `received_at_location_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `status` | nvarchar | 10 | — | — | Não | `StringType` |
| `reason` | nvarchar | 200 | — | — | Sim | `StringType` |
| `total_refund_amount` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `return_items`

Granularidade de devolução por item. **Não possui coluna de data** — vincula com `order_items` via `order_item_id`.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `exchange_variant_id` → `product_variants.id`
- `return_id` → `returns.id`
- `order_item_id` → `order_items.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `return_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `order_item_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `quantity` | decimal | — | 14 | 3 | Não | `DecimalType(14,3)` |
| `action` | nvarchar | 10 | — | — | Não | `StringType` |
| `exchange_variant_id` | int | — | 10 | 0 | Sim | `IntegerType` |
| `unit_refund_amount` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |

### `fiscal_invoices`

Origem de `flag_nfe_autorizada` na `fct_vendas`. `nfe_access_key` é `nchar(44)` — padrão de chave de acesso NF-e.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `order_id` → `orders.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `order_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `nfe_number` | nvarchar | 20 | — | — | Não | `StringType` |
| `nfe_access_key` | nchar | 44 | — | — | Não | `StringType` |
| `series` | nvarchar | 5 | — | — | Não | `StringType` |
| `issued_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `status` | nvarchar | 12 | — | — | Não | `StringType` |
| `total_amount` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `xml_storage_uri` | nvarchar | 500 | — | — | Sim | `StringType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `customers`

Origem de `dim_cliente`. `person_type` distingue PJ/PF.

**Chave Primária:** `id`

**Chaves Estrangeiras:** nenhuma

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `person_type` | nvarchar | 2 | — | — | Não | `StringType` |
| `legal_name` | nvarchar | 200 | — | — | Não | `StringType` |
| `trade_name` | nvarchar | 200 | — | — | Sim | `StringType` |
| `tax_id` | nvarchar | 20 | — | — | Não | `StringType` |
| `state_registration` | nvarchar | 20 | — | — | Sim | `StringType` |
| `email` | nvarchar | 150 | — | — | Sim | `StringType` |
| `phone` | nvarchar | 20 | — | — | Sim | `StringType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `products`

Origem de `dim_produto`. Relaciona com `brands` e `categories`.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `category_id` → `categories.id`
- `brand_id` → `brands.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `name` | nvarchar | 200 | — | — | Não | `StringType` |
| `description` | nvarchar | -1 | — | — | Sim | `StringType` |
| `brand_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `category_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `ncm_code` | nvarchar | 10 | — | — | Não | `StringType` |
| `unit_of_measure` | nvarchar | 2 | — | — | Não | `StringType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `product_variants`

Origem de `dim_produto` (sku, preço, custo, impostos). Relaciona com `products`.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `product_id` → `products.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `product_id` | int | — | 10 | 0 | Não | `IntegerType` |
| `sku` | nvarchar | 40 | — | — | Não | `StringType` |
| `barcode_ean` | nvarchar | 20 | — | — | Sim | `StringType` |
| `sale_price` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `cost_price` | decimal | — | 14 | 2 | Não | `DecimalType(14,2)` |
| `weight_kg` | decimal | — | 10 | 3 | Sim | `DecimalType(10,3)` |
| `icms_rate` | decimal | — | 5 | 2 | Não | `DecimalType(5,2)` |
| `ipi_rate` | decimal | — | 5 | 2 | Não | `DecimalType(5,2)` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `parent_category_id` → `categories.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `name` | nvarchar | 120 | — | — | Não | `StringType` |
| `slug` | nvarchar | 140 | — | — | Não | `StringType` |
| `parent_category_id` | int | — | 10 | 0 | Sim | `IntegerType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `brands`

Atributo `marca` em `dim_produto`.

**Chave Primária:** `id`

**Chaves Estrangeiras:** nenhuma

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `name` | nvarchar | 120 | — | — | Não | `StringType` |
| `country` | nchar | 2 | — | — | Sim | `StringType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `locations`

Origem de `dim_localizacao`.

**Chave Primária:** `id`

**Chaves Estrangeiras:** nenhuma

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `name` | nvarchar | 120 | — | — | Não | `StringType` |
| `location_type` | nvarchar | 10 | — | — | Não | `StringType` |
| `postal_code` | nvarchar | 9 | — | — | Não | `StringType` |
| `street` | nvarchar | 200 | — | — | Não | `StringType` |
| `number` | nvarchar | 20 | — | — | Não | `StringType` |
| `complement` | nvarchar | 100 | — | — | Sim | `StringType` |
| `district` | nvarchar | 100 | — | — | Não | `StringType` |
| `city` | nvarchar | 100 | — | — | Não | `StringType` |
| `state` | nchar | 2 | — | — | Não | `StringType` |
| `country` | nchar | 2 | — | — | Não | `StringType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

### `employees`

Origem de `dim_funcionario`. Vínculo com `orders` via `salesperson_id`. **Contém CPF (PII)** — considerar mascaramento na Silver.

**Chave Primária:** `id`

**Chaves Estrangeiras:**
- `primary_location_id` → `locations.id`

| Coluna | Tipo SQL Server | Length | Prec | Scale | Nullable | Tipo Spark |
|---|---|---|---|---|---|---|
| `id` | int | — | 10 | 0 | Não | `IntegerType` |
| `full_name` | nvarchar | 200 | — | — | Não | `StringType` |
| `cpf` | nvarchar | 11 | — | — | Não | `StringType` |
| `email` | nvarchar | 150 | — | — | Sim | `StringType` |
| `role` | nvarchar | 20 | — | — | Não | `StringType` |
| `primary_location_id` | int | — | 10 | 0 | Sim | `IntegerType` |
| `hire_date` | date | — | — | — | Não | `DateType` |
| `termination_date` | date | — | — | — | Sim | `DateType` |
| `is_active` | bit | — | — | — | Não | `BooleanType` |
| `created_at` | datetime2 | — | — | — | Não | `TimestampType` |
| `updated_at` | datetime2 | — | — | — | Não | `TimestampType` |

## 4. Pontos de Atenção para a Ingestão

- **`order_items` e `return_items` não possuem coluna de data** — full load é a estratégia mais simples para essas tabelas; extração incremental exigiria join com `orders`/`returns`
- **`payments.installments`** é `smallint` → `ShortType` no Spark — atenção ao declarar o schema explícito para não usar `IntegerType` por padrão
- **`payments`** tem 54.635 registros para 50.000 pedidos — confirma múltiplos pagamentos por pedido (produto cartesiano), tratado via agregação por `order_id`
- **`employees.cpf`** é dado sensível (PII)
- **`locations.state` e `locations.country`** são `nchar(2)` — campos de tamanho fixo, validar se há padding de espaços na Silver
- **`categories.parent_category_id`** é FK auto-referenciada nullable — categorias raiz têm `parent_category_id = NULL`

## 5. Referências

- [`ANALISE_FONTE_DADOS.md`](./ANALISE_FONTE_DADOS.md) — classificação Incluir/Excluir das 23 tabelas
- [`CONVENTIONS.md`](./CONVENTIONS.md) — convenções de nomenclatura e ambientes