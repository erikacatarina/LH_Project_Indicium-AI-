# Documentação Power BI| LH Nautical

**Arquivo fonte:** `Relatório Executivo de Vendas.pbip`

**Documento gerado a partir da leitura direta do modelo semântico (TMDL) e da definição do relatório (PBIR) em 21/08/2026.**

Este documento contém o modelo de dados completo, o dicionário de 60 medidas, as páginas do relatório e uma seção de observações técnicas.

---

## 1. Visão Geral

O `Relatório Executivo de Vendas` é um dashboard interativo + relatório gerencial da LH Nautical, construído em Power BI Desktop, consumindo o Data Warehouse via Databricks SQL Warehouse.

- **Conector:** `Databricks.Query`, direto ao SQL Warehouse (parâmetros `Servidor` e `HTTP_Path`).
- **Catálogo/schema de origem:** `prd.gold.*` (todas as 12 Marts).
- **Modo de armazenamento:** Import.
- **11 páginas de relatório**, tema customizado (paleta LH Nautical), 2 bookmarks, 1 página de drillthrough, 1 página de tooltip.

---

## 2. Arquitetura de Conectividade

### Parâmetros do modelo (`Parâmetros`)

| Parâmetro | Valor / Tipo | Uso |
|---|---|---|
| `Servidor` | `dbc-47e8ae46-086a.cloud.databricks.com` (texto) | Host do Databricks SQL Warehouse |
| `HTTP_Path` | `/sql/1.0/warehouses/a9d011bce8dcd209` (texto) | Caminho HTTP do warehouse específico |
| `RangeStart` | `2026-05-01 00:00:00` (datetime) | Início da janela de Incremental Refresh (valor de design-time) |
| `RangeEnd` | `2026-05-02 00:00:00` (datetime) | Fim da janela de Incremental Refresh (valor de design-time) |

> `RangeStart`/`RangeEnd` são parâmetros exigidos pelo Power BI para reconhecer a política de Incremental Refresh, os valores acima são só o intervalo usado durante o desenvolvimento no Desktop.

### Como trocar de ambiente (dev → prd, ou outro workspace)
Editem os parâmetros `Servidor`/`HTTP_Path` em **Transform Data → Manage Parameters**, sem precisar alterar nenhuma query individualmente, todas as 9 dimensões e 3 fatos referenciam esses dois parâmetros.

---

## 3. Modelo de Dados (Star Schema)

12 tabelas Gold + 2 tabelas utilitárias do Power BI (não vêm do Databricks):

### Tabelas Fato (3)

| Tabela | Grão | Descrição (do modelo) |
|---|---|---|
| `fct_orders` | Item de pedido (`order_item_id`) | Fato de vendas. Sem atributos desnormalizados de produto: nome/marca/categoria vêm via relacionamento com `dim_produtos`. |
| `fct_returns` | Item devolvido (`return_item_id`) | Fato de devoluções. Sem rastreamento de produto da troca (`exchange_variant_id` removido, decisão de escopo) e sem relação com `dim_employee` (devoluções não têm vendedor). |
| `fct_desempenho_mensal_produto_vendedor` | Mês + produto + vendedor | Fato de snapshot mensal. Consolida receita líquida (bruta − descontos − impostos − devoluções), quantidade vendida e devolvida. |

### Dimensões (9)

| Tabela | Chave | Descrição (do modelo) |
|---|---|---|
| `dim_calendar` | `date_key` (isenta de SK) | Date spine diária 2020-01-01 a 2031-01-01, com feriados fixos/móveis e flag de alta temporada náutica. |
| `dim_clientes` | `customer_sk` | Enriquecida com métricas e segmentação RFM calculada a partir do histórico de pedidos. |
| `dim_produtos` | `produto_sk` | Grão `product_variant_id` (SKU). Base para rentabilidade por produto/categoria. Não inclui `sku`/`barcode_ean`/`ncm_code` (decisão de escopo). |
| `dim_employee` | `funcionario_sk` | Versão enxuta — não inclui CPF, e-mail ou datas de contratação/desligamento (decisão de segurança/escopo). Membro default `'E-commerce'` para pedidos sem vendedor. |
| `dim_locations` | `local_sk` | Locais físicos, compartilhada por `fct_orders`, `dim_employee` e `fct_returns`. Versão enxuta (sem timestamps). |
| `dim_canal` | `channel_sk` | Canal de venda (pos/ecommerce), construída dinamicamente a partir de `int_orders`. |
| `dim_order_status` | `order_status_id` (natural) | Status de negócio do pedido, construída dinamicamente. `0` = "sem status registrado". |
| `dim_metodo_pagamento` | `metodo_pagamento_id` (natural) | Método de pagamento, construída dinamicamente. `0` = "não informado". Inclui `'múltiplos_métodos'` quando um pedido teve mais de um método distinto. |
| `dim_status_pagamento` | `status_pagamento_id` (natural) | Status de pagamento derivado, construída dinamicamente. `0` = "sem pagamento registrado". `'payment refunded'` ainda cai no fallback `initcap()`, sem descrição curada manualmente. |

### Tabelas Utilitárias (não vêm do Databricks)

| Tabela | Origem | Uso |
|---|---|---|
| `Medidas` | Tabela desconectada (Power Query estático) | Abriga as 60 medidas DAX do modelo, organizadas em pastas de exibição. |
| `Data_Atualizacao` | `DateTime.LocalNow()` capturado no Power Query | Fornece a data do último refresh para a medida `Data de Atualização do Relatório`. Só atualiza quando alguém roda um refresh manual. |

### Relacionamentos

| De | Para | Tipo de chave |
|---|---|---|
| `fct_orders.placed_at_key` | `dim_calendar.date_key` | Data (surrogate `_key`) |
| `fct_returns.data_pedido_original_key` | `dim_calendar.date_key` | Data (surrogate `_key`) |
| `fct_desempenho_mensal_produto_vendedor.mes_referencia_key` | `dim_calendar.date_key` | Data (surrogate `_key`) |
| `fct_orders.customer_id` | `dim_clientes.customer_id` | Surrogate Key (hash) |
| `fct_returns.customer_id` | `dim_clientes.customer_id` | Surrogate Key (hash) |
| `fct_orders.produto_sk` | `dim_produtos.produto_sk` | Surrogate Key (hash) |
| `fct_returns.produto_sk` | `dim_produtos.produto_sk` | Surrogate Key (hash) |
| `fct_desempenho_mensal_produto_vendedor.produto_sk` | `dim_produtos.produto_sk` | Surrogate Key (hash) |
| `fct_orders.funcionario_sk` | `dim_employee.funcionario_sk` | Surrogate Key (hash) |
| `fct_desempenho_mensal_produto_vendedor.funcionario_sk` | `dim_employee.funcionario_sk` | Surrogate Key (hash) |
| `fct_orders.local_sk` | `dim_locations.local_sk` | Surrogate Key (hash) |
| `fct_returns.local_sk` | `dim_locations.local_sk` | Surrogate Key (hash) |
| `fct_orders.canal_sk` | `dim_canal.channel_sk` | Surrogate Key (hash) |
| `fct_orders.order_status_id` | `dim_order_status.order_status_id` | Chave natural (dimensão codificada) |
| `fct_orders.metodo_pagamento_id` | `dim_metodo_pagamento.metodo_pagamento_id` | Chave natural (dimensão codificada) |
| `fct_orders.status_pagamento_id` | `dim_status_pagamento.status_pagamento_id` | Chave natural (dimensão codificada) |

**Estratégia de SK/FK observada:** as SKs são geradas via `dbt_utils.generate_surrogate_key()` no dbt. A chave natural é mantida ao lado da SK em quase todas as tabelas para rastreabilidade.

---

## 4. Estratégia de Atualização (Import + Incremental Refresh)

Política declarada nas 3 tabelas fato (`fct_orders`, `fct_returns`, `fct_desempenho_mensal_produto_vendedor`):

- **Histórico armazenado (rolling window):** 2 anos.
- **Granularidade incremental:** mês.
- **Períodos incrementais:** 3 (equivalente à janela de 3 meses documentada no Planejamento).

**Justificativa registrada no projeto:** o SQL Warehouse do Databricks Free Edition é serverless e pausa por inatividade. O import evita risco de lentidão numa demonstração ao vivo; Incremental Refresh atende à exigência de estratégia para volume sem abrir mão dessa estabilidade.

> ⚠️ A atualização incremental está pré-configurada porém como a volumetria de dados ainda é baixa ela não está ativa. Em cenários futuros, caso seja necessário ativa a atualização incremental, basta descomentar o filtro aplicado com cláusula Where nas tabelas fatos do modelo semântico.

---

## 5. Dicionário de Medidas

Total: **60 medidas**, organizadas nas pastas de exibição (`displayFolder`) já definidas no modelo. Fórmula reproduzida exatamente como está no `.tmdl` (comentário original do autor incluído, quando presente).


### Dor 1: Faturamento Líquido Inconsistente (9 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `Receita Bruta` | -- Medida que calcula receita bruta dos pedidos da tabela fct_orders SUM ( fct_orders[line_total] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Desconto Total` | -- Medida que calcula o desconto total do item de pedido da tabela fct_orders SUM ( fct_orders[desconto_rateado_item] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Receita Líquida` | -- Medida que calcula receita líquida (antes dos impostos) dos pedidos da tabela fct_orders SUM ( fct_orders[valor_liquido_item] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Valor de Impostos` | -- Medida que calcula o valor dos impostos dos pedidos SUM(fct_orders[valor_imposto]) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Receita Líquida Após Impostos` | --Medida que calcula receita líquida (após os impostos) de pedidos da tabela fct_orders [Receita Líquida] - [Valor de Impostos] | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Valor Devolvido` | -- Medida que calcula o valor devolvido de pedidos devolvidos SUM ( fct_returns[valor_reembolsado_item] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Taxa de Devolução %` | -- Medida que calcula o percentual de pedidos devolvidos DIVIDE ( [Valor Devolvido], [Receita Bruta] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Pedidos Cancelados` | -- Medida que calcula pedidos distintos que foram cancelados CALCULATE ( [Quantidade de Pedidos], dim_order_status[order_status] = "cancelled" ) | `#,0` |
| `Taxa de Cancelamento %` | -- Medida que calcula o percentual de pedidos cancelados DIVIDE ( [Pedidos Cancelados], [Quantidade de Pedidos] ) | `#,0.00%;-#,0.00%;#,0.00%` |

### Dor 2: Omnichannel (10 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `Quantidade de Pedidos` | -- Medida que calcula a quantidade distinta de pedidos na tabela fct_orders DISTINCTCOUNT ( fct_orders[order_id] ) | `#,0` |
| `Ticket Médio` | -- Medida que calcula o ticket médio para os pedidos (antes dos impostos) DIVIDE ( [Receita Líquida], [Quantidade de Pedidos] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Ticket Médio Após Impostos` | -- Medida que calcula o ticket médio para os pedidos (após impostos) DIVIDE ( [Receita Líquida Após Impostos], [Quantidade de Pedidos] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Média de Itens por Pedido (un)` | -- Medida que calcula a quantidade média de itens efetuados em um único pedido ROUNDDOWN( DIVIDE ( SUM ( fct_orders[quantity] ), [Quantidade de Pedidos] ), 0 ) | `#,0` |
| `% Participação de Receita por Canal` | -- Medida que calcula a participação dos canais no total da receita (antes dos impostos) DIVIDE ( [Receita Líquida], CALCULATE ( [Receita Líquida], ALL ( dim_canal ) ) ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `% Participação de Receita Líquida Após Impostos por Canal` | -- Medida que calcula a participação dos canais no total da receita (após os impostos) DIVIDE ( [Receita Líquida Após Impostos], CALCULATE ( [Receita Líquida Após Impostos], ALL ( dim_canal ) ) ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Receita E-commerce Após Impostos` | -- Medida que calcula a receita líquida para o canal e-commerce, isoladamente (após impostos) CALCULATE ( [Receita Líquida Após Impostos], dim_canal[descricao_canal] = "E-commerce" ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Receita Loja Física Após Impostos` | -- Medida que calcula a receita líquida para o canal da loja física, isoladamente (após impostos) CALCULATE ( [Receita Líquida Após Impostos], dim_canal[descricao_canal] = "Loja Física" ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Ticket Médio E-commerce Após Impostos` | -- Medida que calcula o ticket médio para o canal do e-commerce, isoladamente (após impostos) VAR _receita_e_commerce = [Receita E-commerce Após Impostos] VAR _pedidos_e_commerce = CALCULATE([Quantidade de Pedidos], dim_canal[descricao_canal] = "E-Commerce") VAR _resultado = DIVIDE(_receita_e_commerce,_pedidos_e_commerce) RETURN _resultado | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Ticket Médio Loja Fisica Após Impostos` | -- Medida que calcula o ticket médio para o canal da loja física, isoladamente (após impostos) VAR _receita_loja_fisica = [Receita Loja Física Após Impostos] VAR _pedidos_loja_fisica = CALCULATE([Quantidade de Pedidos], dim_canal[descricao_canal] = "Loja Física") VAR _resultado = DIVIDE(_receita_loja_fisica,_pedidos_loja_fisica) RETURN _resultado | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |

### Dor 5: Sazonalidade / Time Intelligence (12 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `Receita Líquida Ano Anterior` | -- Medida que calcula a receita líquida do ano anterior CALCULATE ( [Receita Líquida], SAMEPERIODLASTYEAR ( dim_calendar[data] ) ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Variação da Receita Após Impostos YoY %` | -- -- Medida que calcula a variação da receita YoY (percentual) DIVIDE ( [Receita Líquida Após Impostos] - [Receita Líquida Após Impostos Ano Anterior], [Receita Líquida Após Impostos Ano Anterior] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Receita Líquida Após Impostos YTD` | -- Medida que calcula a receita líquida acumulada no ano YTD (após impostos) TOTALYTD ( [Receita Líquida Após Impostos], dim_calendar[data] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Receita Líquida Após Impostos Alta Temporada` | -- Medida que calcula a receita líquida na alta temporada náutica (após impostos) CALCULATE ( [Receita Líquida Após Impostos], dim_calendar[alta_temporada_nautica] = TRUE () ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `% Receita Após Impostos em Alta Temporada` | -- Medida que calcula o percentual de receita em alta temporada (após impostos) DIVIDE ( [Receita Líquida Após Impostos Alta Temporada], [Receita Líquida] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Pedidos Ano Anterior` | -- Medida que calcula a quantidade de pedidos do ano anterior CALCULATE ( [Quantidade de Pedidos], SAMEPERIODLASTYEAR ( dim_calendar[data] ) ) | `#,0` |
| `Variação da Quantidade de Pedidos YoY %` | -- -- Medida que calcula a variação da quantidade YoY (percentual) DIVIDE ( [Quantidade de Pedidos] - [Pedidos Ano Anterior], [Pedidos Ano Anterior] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Ticket Médio Após Impostos Ano Anterior` | -- -- Medida que calcula o valor do ticket médio em relação ao ano anterior CALCULATE ( [Ticket Médio Após Impostos], SAMEPERIODLASTYEAR ( dim_calendar[data] ) ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Variação do Ticket Médio Após Impostos YoY %` | -- Medida que calcula a variação do ticket médio YoY (percentual) DIVIDE ( [Ticket Médio Após Impostos] - [Ticket Médio Após Impostos Ano Anterior], [Ticket Médio Após Impostos Ano Anterior] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Receita Líquida Após Impostos Ano Anterior` | -- Medida que calcula a receita líquida do ano anterior (após impostos) CALCULATE ( [Receita Líquida Após Impostos], SAMEPERIODLASTYEAR ( dim_calendar[data] ) ) | `\$#,0.000;-\$#,0.000;\$#,0.000` |
| `Taxa de Devolução Ano anterior` | -- Medida que calcula a taxa de devolução do ano anterior CALCULATE( [Taxa de Devolução %], SAMEPERIODLASTYEAR(dim_calendar[data]) ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Variação Taxa de Devolução YoY %` | -- Medida que calcula a variação do ticket médio YoY (percentual) DIVIDE ( [Taxa de Devolução %] - [Taxa de Devolução Ano anterior], [Taxa de Devolução Ano anterior] ) | `#,0.00%;-#,0.00%;#,0.00%` |

### Dor 6: Margens e Custo (6 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `Custo Total Vendido` | -- Medida que calcula o custo total vendido SUMX ( fct_orders, fct_orders[quantity] * RELATED ( dim_produtos[cost_price] ) ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Margem Bruta Realizada Após Impostos` | -- Medida que calcula a margem bruta realizada (após os impostos) [Receita Líquida Após Impostos] - [Custo Total Vendido] | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Margem Bruta Realizada %` | -- Medida que calcula a margem bruta realizada (antes dos impostos) DIVIDE ( [Margem Bruta Realizada Após Impostos], [Receita Líquida] ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Margem Catálogo (Referência)` | -- Medida que calcula a margem por produto de acordo com o previsto em catálogo SUMX ( fct_orders, RELATED ( dim_produtos[unit_gross_margin] ) * fct_orders[quantity] ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Gap Margem Catálogo x Realizada` | -- Medida que calcula o gap entre a margem prevista e a margem realizada nas vendas de produtos [Margem Bruta Realizada Após Impostos]-[Margem Catálogo (Referência)] | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `Rank Produto por Margem` | -- Medida que calcula o rank dos produtos baseado na margem bruta RANKX ( ALL ( dim_produtos[product_name] ), [Margem Bruta Realizada Após Impostos], , DESC ) | `#,0` |

### Rankings e Acumulados (7 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `Rank Produto por Receita Após Impostos` | -- Medida que calcula o ranking dinâmico de produtos por receita (após impostos) RANKX ( ALLSELECTED ( dim_produtos[product_name] ), [Receita Líquida Após Impostos], , DESC ) | `#,0` |
| `Rank Vendedor por Receita Após Impostos` | -- Medida que calcula o ranking de vendedores por receita (após impostos) RANKX ( ALL ( dim_employee[full_name] ), [Receita Líquida Após Impostos], , DESC ) | `#,0` |
| `Rank Região por Receita Após Impostos` | -- Medida que calcula o ranking de regiões por participação (após impostos) RANKX ( ALL ( dim_locations[state] ), [Receita Líquida Após Impostos] , , DESC ) | `#,0` |
| `Receita Após Impostos Acumulada` | -- Medida que calcula a receita acumulada (running total) por data (após impostos) CALCULATE ( [Receita Líquida Após Impostos], FILTER ( ALLSELECTED ( dim_calendar[data] ), dim_calendar[data] <= MAX ( dim_calendar[data] ) ) ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |
| `% Acumulado Receita Após Impostos Produto` | -- Medida que calcula a curva ABC de produtos VAR RankAtual = [Rank Produto por Receita Após Impostos] RETURN DIVIDE ( CALCULATE ( [Receita Líquida Após Impostos], FILTER ( ALL ( dim_produtos[product_name] ), [Rank Produto por Receita Após Impostos] <= RankAtual ) ), CALCULATE ( [Receita Líquida Após Impostos], ALL ( dim_produtos[product_name] ) ) ) | `#,0.00%;-#,0.00%;#,0.00%` |
| `Classificação ABC` | -- Medida que classifica o produto nas faixas de curva ABC SWITCH ( TRUE (), [% Acumulado Receita Após Impostos Produto] <= 0.8, "A", [% Acumulado Receita Após Impostos Produto] <= 0.95, "B", "C" ) | `—` |
| `Margem Acumulada` | -- Medida que calcula o acumulado de margem ao longo do tempo CALCULATE ( [Margem Bruta Realizada Após Impostos], FILTER ( ALLSELECTED ( dim_calendar[data] ), dim_calendar[data] <= MAX ( dim_calendar[data] ) ) ) | `"R$"\ #,0.00;-"R$"\ #,0.00;"R$"\ #,0.00` |

### Cards (8 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `CARD Variação Receita Líquida Após Impostos` | VAR _VARIACAO = [Variação da Receita Após Impostos YoY %] VAR _FORMAT = SWITCH( TRUE(), _VARIACAO > 0, UNICHAR(129033) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), _VARIACAO < 0, UNICHAR(129035) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), FORMAT(_VARIACAO, "0.0%;0.0%") ) RETURN _FORMAT | `—` |
| `CARD Variação Pedidos % YoY` | VAR _VARIACAO = [Variação da Quantidade de Pedidos YoY %] VAR _FORMAT = SWITCH( TRUE(), _VARIACAO > 0, UNICHAR(129033) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), _VARIACAO < 0, UNICHAR(129035) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), FORMAT(_VARIACAO, "0.0%;0.0%") ) RETURN _FORMAT | `—` |
| `CARD Variação Ticket Medio % YoY` | VAR _VARIACAO = [Variação do Ticket Médio Após Impostos YoY %] VAR _FORMAT = SWITCH( TRUE(), _VARIACAO > 0, UNICHAR(129033) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), _VARIACAO < 0, UNICHAR(129035) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), FORMAT(_VARIACAO, "0.0%;0.0%") ) RETURN _FORMAT | `—` |
| `CARD Taxa de Devolução % YoY` | VAR _VARIACAO = [Variação Taxa de Devolução YoY %] VAR _FORMAT = SWITCH( TRUE(), _VARIACAO > 0, UNICHAR(129033) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), _VARIACAO < 0, UNICHAR(129035) & " " & FORMAT(_VARIACAO, "0.0%;0.0%"), FORMAT(_VARIACAO, "0.0%;0.0%") ) RETURN _FORMAT | `—` |
| `Clientes Alto Valor` | CALCULATE ( DISTINCTCOUNT ( dim_clientes[customer_id] ), dim_clientes[segmento_rfm] = "Alto Valor" ) | `#,0` |
| `Clientes Inativos` | CALCULATE ( DISTINCTCOUNT ( dim_clientes[customer_id] ), dim_clientes[segmento_rfm] = "Inativo" ) | `#,0` |
| `%Clientes Alto Valor` | DIVIDE ( [Clientes Alto Valor], DISTINCTCOUNT ( dim_clientes[customer_id] ) ) | `—` |
| `Contagem de Clientes` | DISTINCTCOUNT(dim_clientes[customer_id]) | `#,0` |

### Geral (8 medidas)

| Medida | Fórmula DAX | Formato |
|---|---|---|
| `qtd_linhas_fct_orders` | -- Medida que calcula a quantidade de registros presentes na tabela fct_orders COUNTROWS(fct_orders) | `#,0` |
| `qtd_linhas_fct_returns` | -- Medida que calcula a quantidade de registros presentes na tabela fct_returns COUNTROWS(fct_returns) | `#,0` |
| `qtd_linhas_fct_desempenho` | -- Medida que calcula a quantidade de registros presentes na tabela fct_desempenho_mensal COUNTROWS(fct_desempenho_mensal_produto_vendedor) | `#,0` |
| `Intervalo Médio entre Vendas (dias)` | -- Calcula o tempo médio necessário para que aconteça uma venda de um produto. VAR DatasVenda = VALUES ( fct_orders[placed_at] ) VAR QtdDatas = COUNTROWS ( DatasVenda ) VAR PrimeiraData = MINX ( DatasVenda, fct_orders[placed_at] ) VAR UltimaData = MAXX ( DatasVenda, fct_orders[placed_at] ) RETURN IF ( QtdDatas > 1, DIVIDE ( DATEDIFF ( PrimeiraData, UltimaData, DAY ), QtdDatas - 1 ) ) | `#,0` |
| `Blank` | BLANK() | `#,0` |
| `Período de Referência` | VAR _DATAMIN = FORMAT(MIN(dim_calendar[data]), "DD/MM/YYYY") VAR _DATAMAX = FORMAT(MAX(dim_calendar[data]), "DD/MM/YYYY") VAR _PERIODO = "De" & " " & _DATAMIN & " À " & _DATAMAX RETURN _PERIODO | `—` |
| `Data de Atualização do Relatório` | FORMAT ( MAX ( Data_Atualizacao[DataAtualizacao] ), "dd/mm/yyyy" ) | `—` |
| `Data Emissão` | FORMAT(TODAY(), "dd/mm/yyyy") | `—` |
---

## 6. Páginas do Relatório

Ordem de navegação (`pageOrder`), com dimensão e visibilidade real observada no arquivo:

| # | Página | Dimensão | Visibilidade | Tipo/Observação |
|---|---|---|---|---|
| 1 | Capa | 1280×720 | Oculta da navegação padrão | Landing page do relatório (`landingPageName`) |
| 2 | Geral | 1280×720 | Oculta da navegação padrão | Visão executiva (macro) — 30 visuais |
| 3 | Pedidos | 1280×720 | Oculta da navegação padrão | 32 visuais; contém os 2 bookmarks ("Ver Mapa"/"Ver Matriz") |
| 4 | Regiões | 1280×720 | Oculta da navegação padrão | 27 visuais |
| 5 | Clientes | 1280×720 | Oculta da navegação padrão | 20 visuais (RFM) |
| 6 | Produtos | 1280×720 | Oculta da navegação padrão | 19 visuais — página adicional além do escopo original de 3 eixos, cobrindo a Dor 6 (margem/Curva ABC) |
| 7 | Capa A4 | 2480×3508 (A4) | Visível | Capa do relatório gerencial exportável em PDF |
| 8 | Relatório Gerencial | 2480×3508 (A4) | Visível | 15 visuais; filtro de página fixo em `dim_calendar[ano]` |
| 9 | Apêndice | 1920×1080 | Oculta da navegação padrão | **Tipo: Tooltip** — página de glossário/contexto desenhada no Figma, acessada via hover |
| 10 | Detalhamento de Vendas | 1280×720 | Oculta da navegação padrão | **Tipo: Drillthrough** — 17 campos de drill configurados (ano, mês, canal, cliente, vendedor, local, produto, categoria, marca, método/status de pagamento, status do pedido) |
| 11 | Page 1 | 1280×720 | Oculta da navegação padrão | Sem visuais — parece ser página residual/não utilizada |

**Padrão de navegação inferido:** quase todas as páginas estão marcadas como ocultas da faixa de abas padrão do Power BI (`HiddenInViewMode`) — consistente com uma navegação 100% por botões/bookmarks customizados, não pela barra de abas nativa. Só "Capa A4" e "Relatório Gerencial" (as páginas de exportação em PDF) ficam visíveis somente para intuito de exportação do relatório de forma manual ou automatizada no serviço do PowerBI.

### Bookmarks
| Nome | Página ativa | Efeito |
|---|---|---|
| Ver Mapa | Pedidos | Alterna a visualização para exibir o mapa |
| Ver Matriz | Pedidos | Alterna a visualização para exibir a matriz |

### Recursos visuais registrados (Figma → Power BI)
Ícones/imagens customizados encontrados em `StaticResources/RegisteredResources`: Apêndice, Drill(through), Produtos, Relatório Geral, Relatório por Cliente, Relatório por Pedido, Relatório por Região, Capa, Cover, Relatório A4 — confirma que a navegação usa ícones desenhados no Figma em vez dos botões padrão do Power BI.

---

## 7. Tema e Paleta de Cores

Tema customizado `Lh_Nautical_Palette`, com as cores confirmando exatamente a paleta documentada no Planejamento:

| Papel semântico | Cor |
|---|---|
| `good` (tendência positiva) | `#386641` |
| `bad` (tendência negativa) | `#780000` |
| `neutral` | `#8D8F8E` |
| Paleta base (`dataColors`, 5 primeiras) | `#2F6690`, `#3A7CA5`, `#303240`, `#E8E8E8`, `#8D8F8E` |

O tema estende a paleta original com cores adicionais geradas automaticamente (tons complementares) para suportar visuais com mais de 5 categorias — essas cores extras não estão documentadas no Planejamento e não têm significado de negócio atribuído.

---

## 8. Como Atualizar o Relatório

1. Abram `Relatório Executivo de Vendas.pbip` no Power BI Desktop.
2. **Home → Refresh.** O Power BI reconecta ao Databricks usando os parâmetros `Servidor`/`HTTP_Path` e reimporta todas as 12 tabelas Gold, mais recalcula `Data_Atualizacao` (timestamp do refresh).
3. **Atenção ao SQL Warehouse:** como é serverless (Databricks Free Edition), a primeira consulta após um período de inatividade pode demorar mais — é esperado, não é erro.
4. Sem conta/licença Power BI, todo o ciclo de atualização acontece localmente no Desktop — não há refresh agendado automático possível neste ambiente.
5. Para exportar o relatório gerencial em PDF: naveguem até a página "Relatório Gerencial" (ou "Capa A4") e usem **File → Export → Export to PDF** — decisão de arquitetura registrada no Planejamento (ausência de licença Pro/PPU para Report Builder).
6. Uma vez publicado no serviço do PowerBI o relatório pode ser atualizado diariamente com a configuração de atualizações automática nas configurações do modelo semântico.
7. Para a configuração das atualizações automáticas no serviço do PowerBI, será necessário incluir as credenciais de acesso ao workspace do databricks em que as tabelas e schemas residem.

---

## 9. Rastreabilidade às Dores de Negócio

As pastas de exibição das medidas já mapeiam diretamente para as dores que foram mapeadas anteriormente:

| Dor de Negócio | Pasta de Medidas | Páginas relacionadas |
|---|---|---|
| 1 — Faturamento líquido inconsistente | `Dor 1 Faturamento Líquido Inconsistente` | Geral, Relatório Gerencial |
| 2 — Invisibilidade omnichannel | `Dor 2 Omnichannel` | Pedidos, Geral |
| 3 — Morosidade na decisão comercial | Sem medida dedicada | É uma dor resolvida pela materialização do relatório |
| 4 — Falta de segmentação de clientes | (medidas RFM em `Cards`: Clientes Alto Valor/Inativos) | Clientes |
| 5 — Sazonalidade/previsibilidade | `Dor 5 Sazonalidade / Time Intelligence` | Geral, Relatório Gerencial |
| 6 — Ineficiência em campanhas por categoria | `Dor 6`, `Rankings e Acumulados` | Produtos |



---

## 10. Créditos e Convenções

- **Convenção de nomenclatura de medidas:** português, nome de negócio direto (`Receita Líquida`, `Ticket Médio`), sufixo `Após Impostos` quando a variante deduz imposto.
- **Convenção de SK:** sufixo `_sk` (string, hash), sempre oculta (`isHidden`) no modelo, mantida ao lado da chave natural quando presente.
- **Convenção de chave de data:** sufixo `_key` (int, formato `yyyyMMdd`), sempre oculta.
- **Pastas de exibição:** nomeadas pela dor de negócio que resolvem (`Dor 1 ...`, `Dor 2 ...` etc.), com `Cards`, `Rankings e Acumulados` e `Geral` para medidas transversais/utilitárias.
