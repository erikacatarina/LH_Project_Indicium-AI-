# Parâmetros Oficiais do Forecast para "store" - 03/10/2026

Gerado a partir de `notebooks/eda/a4_calibracao_parametros.ipynb`, execução local (VS Code) de [03/09/2026].

## Limiar de histórico suficiente (série madura vs. esparsa)

- `MIN_MESES_HISTORICO` = 16
- `MIN_PCT_COBERTURA` = 20%
- Resultado da calibração: 90.1% das combinações product_variant_id × location_id classificadas como maduras (2726 de 3027 combinações).
- Justificativa:
  - Testamos quatro limiares (16/0.20, 21/0.26, 23/0.30, 26/0.33) e cruzamos cada um com o quanto de demanda real (quantidade vendida) ele preservava, não só quantas combinações produto-loja passavam no corte.
  - O resultado mostrou que, nesta base, cortar combinações corta demanda quase na mesma proporção — não existe uma "gordura" óbvia para tirar.
  - O limiar mais rígido testado (21/0.26) já derrubava a cobertura de volume para 54%, ou seja, jogaria quase metade de toda a demanda real para o fallback simples.
  - O objetivo é prever demanda por produto e por loja (não só para uma fatia dela), escolhemos o limiar mais frouxo da grade — 16 meses de histórico e 20% de cobertura — por ser o único que preserva a grande maioria tanto das combinações (90%) quanto do volume vendido (93%). Combinações que não atingem nem esse piso mínimo vão para o fallback de média por categoria, já previsto no escopo.
  - Limitação sabida: esse limiar aceita séries com venda intermitente (até 1 mês vendido a cada 5). Isso pode aparecer como erro maior em algumas combinações específicas durante os testes dos modelos.

## Candidatas finais à análise de sazonalidade

1. product_variant_id=[396] — índice de sazonalidade [2.590028], padrão confirmado visualmente
2. product_variant_id=[649] — índice de sazonalidade [2.226389], padrão confirmado visualmente
3. product_variant_id=[22] — índice de sazonalidade [2.181373], padrão confirmado visualmente

## Consumo previsto destes parâmetros

- `MIN_MESES_HISTORICO` / `MIN_PCT_COBERTURA` → módulo Python de features, para gerar a flag de histórico suficiente por product_variant_id × location_id.
- Candidatas finais → Análise formal de sazonalidade com rigor estatístico.

# Parâmetros Oficiais do Forecast para "warehouse" - 03/10/2026

Gerado a partir de `notebooks/eda/a4_calibracao_parametros.ipynb`, execução local (VS Code) de [03/09/2026].

## Limiar de histórico suficiente (série madura vs. esparsa)

- `MIN_MESES_HISTORICO` = 16
- `MIN_PCT_COBERTURA` = 20%
- Resultado da calibração: 90.0 % das combinações product_variant_id × location_id classificadas como maduras (2725 de 3027 combinações).
- Justificativa:
  - Testamos quatro limiares (16/0.20, 21/0.26, 23/0.30, 26/0.33) e cruzamos cada um com o quanto de demanda real (quantidade vendida) ele preservava, não só quantas combinações produto-loja passavam no corte.
  - O resultado mostrou que, nesta base, cortar combinações corta demanda quase na mesma proporção — não existe uma "gordura" óbvia para tirar.
  - O limiar mais rígido testado (21/0.26) já derrubava a cobertura de volume para 54%, ou seja, jogaria quase metade de toda a demanda real para o fallback simples.
  - O objetivo é prever demanda por produto e por loja (não só para uma fatia dela), escolhemos o limiar mais frouxo da grade — 16 meses de histórico e 20% de cobertura — por ser o único que preserva a grande maioria tanto das combinações (90%) quanto do volume vendido (93%). Combinações que não atingem nem esse piso mínimo vão para o fallback de média por categoria, já previsto no escopo.
  - Limitação sabida: esse limiar aceita séries com venda intermitente (até 1 mês vendido a cada 5). Isso pode aparecer como erro maior em algumas combinações específicas durante os testes dos modelos.

## Candidatas finais à análise de sazonalidade

1. product_variant_id=[3] — índice de sazonalidade [2.236411], padrão confirmado visualmente
2. product_variant_id=[541] — índice de sazonalidade [2.196078], padrão confirmado visualmente
3. product_variant_id=[763] — índice de sazonalidade [2.089669], padrão confirmado visualmente

## Consumo previsto destes parâmetros

- `MIN_MESES_HISTORICO` / `MIN_PCT_COBERTURA` → módulo Python de features, para gerar a flag de histórico suficiente por product_variant_id × location_id.
- Candidatas finais → Análise formal de sazonalidade com rigor estatístico.

## Baseline de médias móveis

Avaliada sobre o conjunto de teste (últimos 3 meses), só nas combinações com histórico suficiente.

| Pipeline                 | MAE  | RMSE | MAPE    |
| ------------------------ | ---- | ---- | ------- |
| Loja                     | 4,11 | 5,47 | 106,03% |
| Centro de Distribuição | 3,97 | 5,17 | 99,64%  |

Registrado no MLflow: experimento `/Shared/forecast_lh_nautical/baseline_medias_moveis`,
runs `baseline_store` e `baseline_warehouse`.

**Leitura:** MAPE próximo de 100% nos dois pipelines confirma que a baseline simples erra,
em média, quase o tamanho do próprio valor real.

# Parâmetros Oficiais do Forecast para "store" - 10/10/2026

Gerado a partir de `notebooks/eda/a4_calibracao_parametrosv2.ipynb`, execução local (VS Code) de [10/09/2026].

## Limiar de histórico suficiente (série madura vs. esparsa)

- `MIN_MESES_HISTORICO` = 14
- `MIN_PCT_COBERTURA` = 20%
- Resultado da calibração: 90.1 das combinações product_variant_id × location_id classificadas como maduras (2728 de 3027 combinações).
- Justificativa:
  - Testamos quatro limiares (14/0.20, 16/0.20, 19/0.26, 22/0.30, 24/0.33) e cruzamos cada um com o quanto de demanda real (quantidade vendida) ele preservava, não só quantas combinações produto-loja passavam no corte.
  - O resultado mostrou que, nesta base, cortar combinações corta demanda quase na mesma proporção — não existe uma "gordura" óbvia para tirar.
  - O limiar mais rígido testado (24/0.3) já derrubava a cobertura de volume para 9.6%, ou seja, jogaria quase toda a demanda real para o fallback simples.
  - O objetivo é prever demanda por produto e por loja (não só para uma fatia dela), escolhemos o limiar mais frouxo da grade — 14 meses de histórico e 20% de cobertura — por ser o único que preserva a grande maioria tanto das combinações (90%) quanto do volume vendido (93%). Combinações que não atingem nem esse piso mínimo vão para o fallback de média por categoria, já previsto no escopo.
  - Limitação sabida: esse limiar aceita séries com venda intermitente (até 1 mês vendido a cada 5). Isso pode aparecer como erro maior em algumas combinações específicas durante os testes dos modelos.

## Candidatas finais à análise de sazonalidade

1. product_variant_id=[649] — índice de sazonalidade [2.425759], padrão confirmado visualmente
2. product_variant_id=[15] — índice de sazonalidade [2.409524], padrão confirmado visualmente
3. product_variant_id=[354] — índice de sazonalidade [2.322917], padrão confirmado visualmente

## Consumo previsto destes parâmetros

- `MIN_MESES_HISTORICO` / `MIN_PCT_COBERTURA` → módulo Python de features, para gerar a flag de histórico suficiente por product_variant_id × location_id.
- Candidatas finais → Análise formal de sazonalidade com rigor estatístico.

# Parâmetros Oficiais do Forecast para "warehouse" - 10/10/2026

Gerado a partir de `notebooks/eda/a4_calibracao_parametrosv2.ipynb`, execução local (VS Code) de [10/09/2026].

## Limiar de histórico suficiente (série madura vs. esparsa)

- `MIN_MESES_HISTORICO` = 15
- `MIN_PCT_COBERTURA` = 20%
- Resultado da calibração: 88.8 % das combinações product_variant_id × location_id classificadas como maduras (2689 de 3027 combinações).
- Justificativa:
  - Testamos quatro limiares (14/0.20, 19/0.26, 22/0.30, 24/0.33) e cruzamos cada um com o quanto de demanda real (quantidade vendida) ele preservava, não só quantas combinações produto-loja passavam no corte.
  - O resultado mostrou que, nesta base, cortar combinações corta demanda quase na mesma proporção — não existe uma "gordura" óbvia para tirar.
  - O limiar mais rígido testado (24/0.33) já derrubava a cobertura de volume para 7%, ou seja, jogaria quase toda a demanda real para o fallback simples.
  - O objetivo é prever demanda por produto e por loja (não só para uma fatia dela), escolhemos o limiar mais frouxo da grade — 15 meses de histórico e 20% de cobertura — por ser o único que preserva a grande maioria tanto das combinações (88.8%) quanto do volume vendido (92,3%). Combinações que não atingem nem esse piso mínimo vão para o fallback de média por categoria, já previsto no escopo.
  - Limitação sabida: esse limiar aceita séries com venda intermitente (até 1 mês vendido a cada 5). Isso pode aparecer como erro maior em algumas combinações específicas durante os testes dos modelos.

## Candidatas finais à análise de sazonalidade

1. product_variant_id=[763] — índice de sazonalidade [2.281022], padrão confirmado visualmente
2. product_variant_id=[123] — índice de sazonalidade [2.209910], padrão confirmado visualmente
3. product_variant_id=[3] — índice de sazonalidade [2.196078], padrão confirmado visualmente

## Consumo previsto destes parâmetros

- `MIN_MESES_HISTORICO` / `MIN_PCT_COBERTURA` → módulo Python de features, para gerar a flag de histórico suficiente por product_variant_id × location_id.
- Candidatas finais → Análise formal de sazonalidade com rigor estatístico.
