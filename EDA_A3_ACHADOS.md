# EDA A3 — Achados - STORE - 02/09/2026

Gerado a partir de `notebooks/eda/a3_eda_forecast.ipynb`, execução local (VS Code) de 02/09/2026.

## Grão adotado
`product_variant_id` × `location_id` × mês — decidido pelo time (grão de item/SKU).

## Métrica de demanda
Principal: `quantity`. Secundária (ROI/faturamento, não usada para dimensionar estoque): `valor_liquido_item`.

## Cobertura de histórico (variante × loja)
| Faixa de cobertura | % de combinações |
|---|---|
| 0-25% | 0.391477 |
| 25-50% | 0.608523 |
| 50-75% | 0.000000 |
| 75-90% | 0.000000 |
| 90-100% | 0.000000 |

> Consumido para calibrar o limiar "série madura vs. esparsa".

## Variantes candidatas à análise de sazonalidade
1. product_variant_id=[22] — [índice de sazonalidade: 2.181373]
2. product_variant_id=[49] — [índice de sazonalidade: 2.165657]
3. product_variant_id=[617] — [índice de sazonalidade: 2.102149]

## Outliers/distorções identificados
Olhar célula 6 do notebook a3_eda_forecast.ipynb

## Observações sobre calendário/feriados
| Feriado | fim_de_semana | ticket_medio_dia |
|---|---|---|
| False | True | 9554.273680 |
| True | True | 9580.455973 |
| True | False | 9764.007258 |
| False | False | 9535.203800 |

-------------------------------------------------------------------------------------------------------------

# EDA A3 — Achados - STORE - 10/09/2026

Gerado a partir de `notebooks/eda/a3_eda_forecastv2.ipynb`, execução local (VS Code) de 10/09/2026.

## Grão adotado
`product_variant_id` × `location_id` × mês — decidido pelo time (grão de item/SKU).

## Métrica de demanda
Principal: `quantity`. Secundária (ROI/faturamento, não usada para dimensionar estoque): `valor_liquido_item`.

## Cobertura de histórico (variante × loja)
| Faixa de cobertura | % de combinações |
|---|---|
| 0-25% | 0.414602 |
| 25-50% | 0.585398 |
| 50-75% | 0.000000 |
| 75-90% | 0.000000 |
| 90-100% | 0.000000 |

> Consumido para calibrar o limiar "série madura vs. esparsa".

## Variantes candidatas à análise de sazonalidade
1. product_variant_id=[62] — [índice de sazonalidade: 2.293907]
2. product_variant_id=[49] — [índice de sazonalidade: 2.224265]
3. product_variant_id=[561] — [índice de sazonalidade: 2.201619]

## Outliers/distorções identificados
Olhar célula 6 do notebook a3_eda_forecast.ipynb

## Observações sobre calendário/feriados
| Feriado | fim_de_semana | ticket_medio_dia |
|---|---|---|
| False | True | 9540.186418 |
| True | True | 9554.226251 |
| True | False | 9773.540294 |
| False | False | 9537.665211 |

------------------------------------------------------------------------------------------------------------

# EDA A3 — Achados - WAREHOUSE - 02/09/2026

Gerado a partir de `notebooks/eda/a3_eda_forecastv.ipynb`, execução local (VS Code) de 02/09/2026.

## Grão adotado
`product_variant_id` × `location_id` × mês — decidido pelo time (grão de item/SKU).

## Métrica de demanda
Principal: `quantity`. Secundária (ROI/faturamento, não usada para dimensionar estoque): `valor_liquido_item`.

## Cobertura de histórico (variante × loja)
| Faixa de cobertura | % de combinações |
|---|---|
| 0-25% | 0.395771 |
| 25-50% | 0.604229 |
| 50-75% | 0.000000 |
| 75-90% | 0.000000 |
| 90-100% | 0.000000 |

> Consumido para calibrar o limiar "série madura vs. esparsa".

## Variantes candidatas à análise de sazonalidade
1. product_variant_id=[3] — [índice de sazonalidade: 2.236411]
2. product_variant_id=[763] — [índice de sazonalidade: 2.089669]
3. product_variant_id=[965] — [índice de sazonalidade: 2.042735]

## Outliers/distorções identificados
Olhar célula 6 do notebook a3_eda_forecast.ipynb

## Observações sobre calendário/feriados
| Feriado | fim_de_semana | ticket_medio_dia |
|---|---|---|
| False | True | 9554.273680 |
| True | True | 9580.455973 |
| True | False | 9764.007258 |
| False | False | 9535.203800 |

-----------------------------------------------------------------------------------------------------------------

# EDA A3 — Achados - WAREHOUSE - 10/09/2026

Gerado a partir de `notebooks/eda/a3_eda_forecastv2.ipynb`, execução local (VS Code) de 10/09/2026.

## Grão adotado
`product_variant_id` × `location_id` × mês — decidido pelo time (grão de item/SKU).

## Métrica de demanda
Principal: `quantity`. Secundária (ROI/faturamento, não usada para dimensionar estoque): `valor_liquido_item`.

## Cobertura de histórico (variante × loja)
| Faixa de cobertura | % de combinações |
|---|---|
| 0-25% | 0.411959 |
| 25-50% | 0.588041 |
| 50-75% | 0.000000 |
| 75-90% | 0.000000 |
| 90-100% | 0.000000 |

> Consumido para calibrar o limiar "série madura vs. esparsa".

## Variantes candidatas à análise de sazonalidade
1. product_variant_id=[763] — [índice de sazonalidade: 2.281022]
2. product_variant_id=[3] — [índice de sazonalidade: 2.196078]
3. product_variant_id=[965] — [índice de sazonalidade: 2.172862]

## Outliers/distorções identificados
Olhar célula 6 do notebook a3_eda_forecast.ipynb

## Observações sobre calendário/feriados
| Feriado | fim_de_semana | ticket_medio_dia |
|---|---|---|
| False | True | 9540.186418 |
| True | True | 9554.226251 |
| True | False | 9773.540294 |
| False | False | 9537.665211 |