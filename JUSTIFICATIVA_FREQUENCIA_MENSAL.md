# Justificativa da Frequência Mensal do Forecast

Gerado a partir de `notebooks/EDA/a9_justificativa_frequencia_mensal.ipynb`, execução de 07/09/2026.

## Decisão 
O forecast é gerado e consultado em frequência **mensal** — casa com o horizonte de 3 meses
previstos, com o ciclo de compra de ticket alto/baixa frequência do varejo náutico, e com a
sazonalidade dez-mar já em análise.

## Evidência quantitativa
| Grão | % de células com demanda zero |
|---|---|
| Mensal | 73.4% |
| Semanal | 92.9% |

## Conclusão
O grão semanal apresenta 19.5% pontos percentuais a mais de células zeradas
que o mensal, o que agravaria a distorção do MAPE por divisão por zero/exclusão de linhas. 
Isso reforça, com dado real.