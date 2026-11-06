# Relatório de Análise e Previsão — LH Nautical

Gerado automaticamente em 18/09/2026 14:18. Catálogo de origem: `dev`.

## 1. Previsão de Demanda (3 meses) e Sazonalidade

![Previsão por tipo de local](relatorios/graficos_2026-09/previsao_por_pipeline.png)

- **Centros de Distribuição:** 53018 unidades previstas para o próximo trimestre.
- **Lojas:** 53270 unidades previstas para o próximo trimestre.

**Leitura de negócio:** esses volumes orientam diretamente o planejamento de compras e reposição de estoque para o trimestre — números abaixo do previsto sinalizam risco de ruptura, acima do previsto sinalizam capital parado em estoque excedente.

### Produtos com sazonalidade estatisticamente confirmada

**Bateria Náutica 8635 (Loja):** Bateria Náutica 8635 (Loja) é um produto com sazonalidade estatisticamente confirmada, identificada por meio de testes estatísticos de sazonalidade (autocorrelação anual, decomposição de série temporal e teste de significância). A previsão para setembro/2026, outubro/2026, novembro/2026 totaliza 98 unidades, com intervalo de confiança de 80% entre 30 e 165 unidades. Esse volume é superior à maior parte do histórico do produto, consistente com o período de preparação de embarcações que antecede a alta temporada náutica de verão (dezembro a março).

**Bateria Náutica 834 (Centro de Distribuição):** Bateria Náutica 834 (Centro de Distribuição) é um produto com sazonalidade estatisticamente confirmada, identificada por meio de testes estatísticos de sazonalidade (autocorrelação anual, decomposição de série temporal e teste de significância). A previsão para setembro/2026, outubro/2026, novembro/2026 totaliza 117 unidades, com intervalo de confiança de 80% entre 36 e 198 unidades. Esse volume é superior à maior parte do histórico do produto, consistente com o período de preparação de embarcações que antecede a alta temporada náutica de verão (dezembro a março).


## 2. Viabilidade e Desempenho dos Modelos de Regressão

### Loja

# Decisão do modelo — pipeline store

**Modelo escolhido:** catboost

## Comparação completa (trial vencedor de cada modelo)

| Modelo | MAE | RMSE | MAPE |
|---|---|---|---|
| ridge | 3.378 | 4.401 | 97.48% |
| random_forest | 3.369 | 4.401 | 96.71% |
| lightgbm | 3.374 | 4.404 | 96.55% |
| catboost | 3.374 | 4.399 | 96.78% |

## Justificativa

Reconfirmado em prd, mesma justificativa de dev: vantagem estrutural, diferencas de metrica pequenas.

### Centro de Distribuição

# Decisão do modelo — pipeline warehouse

**Modelo escolhido:** catboost

## Comparação completa (trial vencedor de cada modelo)

| Modelo | MAE | RMSE | MAPE |
|---|---|---|---|
| ridge | 3.387 | 4.483 | 96.44% |
| random_forest | 3.383 | 4.483 | 95.50% |
| lightgbm | 3.382 | 4.483 | 95.73% |
| catboost | 3.384 | 4.481 | 96.01% |

## Justificativa

Reconfirmado em prd, mesma justificativa de dev.


## 3. Crescimento da Demanda por Centro de Distribuição e Ponto de Venda

### Lojas

![Crescimento YoY Lojas](relatorios/graficos_2026-09/crescimento_store.png)

- **Loja Leão:** 6.6% de crescimento YoY.
- **Loja Oliveira:** 3.5% de crescimento YoY.
- **Loja Mendonça:** -11.5% de crescimento YoY.

**Maior crescimento:** Loja Leão (6.6%).

**Leitura de negócio:** o local de maior crescimento é candidato prioritário para reforço de capacidade (estoque de segurança maior, possível ampliação de espaço) antes do início do trimestre.

### Centros de Distribuição

![Crescimento YoY Centros de Distribuição](relatorios/graficos_2026-09/crescimento_warehouse.png)

- **Armazém Novaes:** 30.2% de crescimento YoY.
- **Armazém Camargo:** 7.9% de crescimento YoY.
- **Armazém Siqueira:** -15.1% de crescimento YoY.

**Maior crescimento:** Armazém Novaes (30.2%).

**Leitura de negócio:** o local de maior crescimento é candidato prioritário para reforço de capacidade (estoque de segurança maior, possível ampliação de espaço) antes do início do trimestre.


## 4. Necessidade e Localização de Novos Centros de Distribuição

![Cobertura por estado](relatorios/graficos_2026-09/cobertura_novos_cds.png)

### Estados avaliados (maior crescimento de demanda de cliente, com volume relevante)

- **DF:** 23.9% — SEM COBERTURA
- **RO:** 18.8% — SEM COBERTURA
- **AM:** 15.9% — SEM COBERTURA
- **AP:** 0.1% — cobertura no estado
- **SE:** 0.1% — SEM COBERTURA
- **MS:** -1.5% — SEM COBERTURA
- **PR:** -7.3% — cobertura no estado

**Conclusão:** há estados com crescimento de demanda e sem cobertura da rede atual — avaliar como candidatos a novo Centro de Distribuição (ver detalhamento acima).