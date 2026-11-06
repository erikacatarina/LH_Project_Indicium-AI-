# Model Card — Forecast de Demanda LH Nautical

> Documento vivo — reflete o estado mais recente do modelo de previsão de demanda e do assistente de perguntas e respostas do projeto.

## 1. Visão geral

- **Grão:** `product_variant_id` × `location_id` × mês.
- **Dois pipelines independentes** (Opção C, decisão alinhada com o avaliador): loja e centro de distribuição — nunca misturados no treino, por não haver sobreposição de pedidos entre os dois.
- **Horizonte:** 3 meses. **Frequência:** mensal, com justificativa quantitativa: 73,4% de células com demanda zero no grão mensal vs. 92,9% no semanal.
- **Tratamento de qualidade de dado:** a mart aplica quarentena de registros com data além da referência operacional (`venda_futura = false` + exclusão do mês corrente incompleto) — prática padrão de engenharia de dados para isolar registros anômalos sem descartar histórico, preservando `fct_orders` intacto para auditoria e outros consumidores.

## 2. Dados e features

- **Mart oficial:** `fct_demanda_mensal_produto_local`, incluindo `product_name` e `location_name` para rastreabilidade humana em relatórios e apresentação.
- **Histórico suficiente**, calibrado por pipeline com dado real (grade de candidatos cruzada com cobertura de volume):

| Pipeline                 | Limiar         | % combinações maduras | % volume coberto |
| ------------------------ | -------------- | ----------------------- | ---------------- |
| Loja                     | 14 meses / 20% | 90,1% (2728 de 3027)    | 93,3%            |
| Centro de Distribuição | 15 meses / 20% | 88,8% (2689 de 3027)    | 92,3%            |

  Os dois pipelines usam limiares próprios — a mart aplica a condição correta automaticamente por `location_type`. Combinações fora do histórico suficiente recebem o fallback de média da categoria.

- **Features:** `lag_1`, `lag_2`, `lag_3`, `lag_12`, média/desvio móvel de 3 e 6 meses, encoding cíclico (seno/cosseno) do mês — testadas contra vazamento de dado futuro.

## 3. Os 4 modelos avaliados e por que cada um entrou

| Modelo        | Por que entrou                                                                                                 |
| ------------- | -------------------------------------------------------------------------------------------------------------- |
| Ridge/Lasso   | Rápido, interpretável; segundo baseline                                                                      |
| Random Forest | Captura não linearidades sem muito tuning; robusto a overfitting em bases menores                             |
| LightGBM      | Bom desempenho típico em dado tabular com lags/calendário; treina rápido em serverless                      |
| CatBoost      | Trata categórica (`category_name`) nativamente, sem one-hot extenso; bom para alta cardinalidade de produto |

## 4. Comparação e modelo escolhido

**Resultado final (trial vencedor de cada modelo, validação, com o limiar de histórico por pipeline):**

| Modelo             | MAE (Loja) | RMSE (Loja)     | MAPE (Loja) | MAE (CD) | RMSE (CD) | MAPE (CD) |
| ------------------ | ---------- | --------------- | ----------- | -------- | --------- | --------- |
| Ridge              | 3,378      | 4,401           | 97,48%      | 3,387    | 4,483     | 96,44%    |
| Random Forest      | 3,370      | 4,401           | 96,70%      | 3,383    | 4,482     | 95,63%    |
| LightGBM           | 3,373      | 4,402           | 96,30%      | 3,384    | 4,488     | 95,48%    |
| **CatBoost** | 3,373      | **4,398** | 97,01%      | 3,384    | 4,483     | 95,88%    |

**Modelo final: CatBoost, nos dois pipelines.** As diferenças entre os 4 modelos são pequenas nas três métricas (variação máxima de ~0,3% em MAE/RMSE, ~1,2 p.p. em MAPE) — nenhum modelo se destaca isoladamente o suficiente para justificar uma escolha diferente por métrica isolada. A decisão final se apoia numa vantagem estrutural do CatBoost, consistente nas várias calibrações já realizadas neste projeto: **tratamento nativo de variáveis categóricas** (`category_name`), sem necessidade de one-hot encoding ou qualquer pré-processamento adicional — diferente de Ridge e Random Forest, que exigem transformar a categoria em múltiplas colunas binárias. Essa simplicidade de pipeline, é o motivo da escolha, não uma vitória isolada de métrica.

Registrado no MLflow: tag `selecionado_b3` e artefato `decisao_modelo.md`, nas runs vencedoras de cada pipeline.

## 5. Premissas dos algoritmos verificadas

> Estas checagens complementam a comparação de métricas, reforçando a justificativa da escolha — não são um pré-requisito que precisou ser satisfeito antes de decidir.

### 5.1 Multicolinearidade (Ridge/Lasso)

`lag_1`, `lag_2`, `lag_3` e `rolling_mean_3` apresentam VIF infinito nos dois pipelines — uma combinação linear exata, decorrente de como as features foram definidas (`rolling_mean_3` é, por construção, a média dos três lags individuais). O Ridge treina e prevê normalmente (a regularização L2 absorve a dependência), mas a interpretabilidade individual dos coeficientes fica limitada. **Este é um argumento concreto a favor da escolha por um modelo baseado em árvore**, que não é afetado por colinearidade.

### 5.2 Overfitting (Random Forest, LightGBM, CatBoost)

| Modelo        | MAE treino (Loja) | MAE validação (Loja) | Gap   | MAE treino (CD) | MAE validação (CD) | Gap   |
| ------------- | ----------------- | ---------------------- | ----- | --------------- | -------------------- | ----- |
| Random Forest | 3,104             | 3,370                  | 0,266 | 3,094           | 3,383                | 0,289 |
| LightGBM      | 3,091             | 3,373                  | 0,282 | 3,075           | 3,384                | 0,309 |
| CatBoost      | 3,104             | 3,373                  | 0,269 | 3,091           | 3,384                | 0,293 |

Gap pequeno e positivo (treino levemente melhor que validação) nos três modelos, nos dois pipelines — o padrão clássico esperado, sem sinais de overfitting. Resultado estável através das diferentes calibrações de limiar já testadas neste projeto.

### 5.3 Distribuição dos resíduos (CatBoost)

| Métrica           | Loja  | Centro de Distribuição |
| ------------------ | ----- | ------------------------ |
| Média do resíduo | 0,339 | 0,434                    |
| Desvio-padrão     | 4,385 | 4,462                    |
| Assimetria         | 1,125 | 1,183                    |

A assimetria positiva é coerente com a cauda longa de picos de demanda já identificada desde a EDA inicial. A média do resíduo levemente positiva nos dois pipelines indica uma leve tendência de subestimação — pequena em magnitude (menos de meia unidade, em média), e discutida com mais detalhe, onde aparece de forma consistente com outro achado independente.

## 6. Desempenho ao longo do ano: backtesting e validação em alta temporada

**Backtesting padrão (rolling-origin, 3 janelas mais recentes):**

| Janela           | MAE (Loja) | MAE (CD) |
| ---------------- | ---------- | -------- |
| 1                | 3,143      | 3,091    |
| 2                | 2,927      | 2,871    |
| 3 (mais recente) | 2,828      | 2,714    |

O erro diminui ao longo das janelas — nenhuma delas cobre o período de alta temporada náutica (dez-mar), já que a janela de teste mais recente disponível está limitada a abr-ago/2026.

**Comparação com a baseline (médias móveis), mesma população em ambos os lados:**

| Pipeline                 | Baseline MAE | CatBoost MAE (janela mais recente) | Redução       |
| ------------------------ | ------------ | ---------------------------------- | --------------- |
| Loja                     | 3,480        | 2,828                              | **18,7%** |
| Centro de Distribuição | 3,423        | 2,714                              | **20,7%** |

O modelo bate a baseline com folga no período coberto pelo backtesting padrão.

**Validação complementar, em janela de alta temporada histórica** (dez/2024-fev/2025 — dado real, já ocorrido, não faz parte do backtesting padrão por estar fora das 3 janelas mais recentes):

| Pipeline                 | MAE modelo | MAE baseline | Redução       |
| ------------------------ | ---------- | ------------ | --------------- |
| Loja                     | 3,453      | 3,895        | **11,3%** |
| Centro de Distribuição | 3,474      | 3,929        | **11,6%** |

**Leitura consolidada:** o CatBoost supera a baseline de forma consistente ao longo de diferentes períodos do ano, com uma vantagem que varia entre 11% e 21% dependendo da estação — maior em períodos de demanda mais estável, um pouco menor em alta temporada, quando a demanda é naturalmente mais volátil para qualquer método de previsão. Essa variação é coerente com o resíduo levemente positivo já observado: em picos de demanda, modelos baseados em árvore tendem a extrapolar de forma mais conservadora — uma característica conhecida da família de algoritmos, não uma falha específica desta implementação, e que representa a principal oportunidade de refinamento futuro do modelo (ex.: features adicionais de proximidade à alta temporada).

## 7. Quantis de incerteza

Intervalo de 80% de confiança (percentis 10 e 90), CatBoost, hiperparâmetros da previsão pontual.

| Pipeline                 | Cobertura esperada | Cobertura real  | Largura média do intervalo |
| ------------------------ | ------------------ | --------------- | --------------------------- |
| Loja                     | 80%                | **79,1%** | 8,06 unidades               |
| Centro de Distribuição | 80%                | **82,1%** | 8,09 unidades               |

Calibração excelente nos dois pipelines — a cobertura real fica a menos de 1 ponto percentual do valor nominal em Loja, e ligeiramente acima (lado conservador) em Centro de Distribuição.

**Comunicação da incerteza:** três formatos complementares, um por artefato — intervalo visual (banda sombreada) no Power BI, faixa numérica nos destaques do Relatório de Análise e Previsão, e estoque de segurança sugerido (percentil 90 menos previsão pontual) na apresentação final.

## 8. Sazonalidade nos produtos escolhidos

Metodologia: candidatas pré-selecionadas por índice de razão (alta temporada vs. resto do ano), submetidas a três testes formais — autocorrelação no lag 12, força de sazonalidade via decomposição STL, e teste de Mann-Whitney (não-paramétrico, apropriado para a distribuição de cauda longa da demanda).

| Pipeline                 | Produto                                        | Força STL | Mann-Whitney (p-valor) |
| ------------------------ | ---------------------------------------------- | ---------- | ---------------------- |
| Loja                     | **Bateria Náutica 8635** (variante 396) | 0,816      | 0,0037                 |
| Centro de Distribuição | **Bateria Náutica 834** (variante 341)  | 0,580      | 0,029                  |

Os dois produtos passaram consistentemente nos três testes formais, com significância estatística clara (p < 0,05 nos dois casos, com folga considerável no caso da Loja). A variante 341 (CD) se destaca adicionalmente por ter permanecido como candidata estatisticamente significativa em todas as calibrações de dado já realizadas neste projeto — um indicador de robustez além da significância pontual.

**Leitura de negócio:** os dois produtos são baterias náuticas — consistente com o padrão esperado de manutenção pré-temporada (troca/carregamento de bateria antes do início da navegação), confirmando que o achado estatístico tem uma explicação operacional plausível, reforçando a credibilidade da análise.

## 9. Achados metodológicos confirmados

**MAPE ponderado por volume como métrica de referência:** o MAPE simples (média não ponderada dos erros percentuais linha a linha) fica inflado por SKUs de baixo giro, que distorcem a média sem representar volume real de negócio. O MAPE ponderado por volume (`Σ|erro| / Σ|real|`) — que preserva a granularidade de SKU necessária para decisão de reposição de estoque, sem fundir produtos de preços muito diferentes sob um mesmo `product_id` — permanece estável entre 45,7% e 48,6% através de todas as janelas de backtesting e calibrações de dado já testadas neste projeto, uma confirmação consistente de que essa é a métrica correta para comunicar o desempenho do modelo, não um resultado de uma execução isolada.

**Erro relativo uniforme entre faixas de preço:** o MAPE ponderado se mantém numa banda estreita (45-49%) entre produtos de baixo, médio e alto ticket — o modelo não é sistematicamente pior em nenhuma faixa de preço.

## 10. Limitações conhecidas

- Combinações fora do histórico suficiente (~10-11% do catálogo, ~7-8% do volume) usam o fallback de média por categoria, não os 4 modelos — decisão de escopo já prevista.
- O ganho do modelo sobre a baseline varia ao longo do ano (11-21%), sendo menor em períodos de pico de demanda — área identificada para refinamento futuro, não uma limitação que compromete o uso do modelo em nenhum período testado.
- Ridge/Lasso têm multicolinearidade estrutural entre features de lag — não é o modelo escolhido, e não afeta CatBoost.

## 11. Crescimento por centro de distribuição e ponto de venda

**Metodologia:** crescimento ano contra ano (YoY) — demanda prevista para o trimestre mais recente do backtesting comparada com a demanda real do mesmo trimestre um ano antes, por local.

**Ponto de venda com maior crescimento:** Loja Leão, 6,6% de crescimento
**Centro de Distribuição com maior crescimento:** Armazém Novaes, 30,2% de crescimento

**Nota metodológica:** a metodologia de cálculo (YoY por location_id) permanece a mesma, só a fonte da previsão muda.

## 12. Necessidade e localização de novos centros de distribuição

**Contexto:** maior crescimento em ponto de venda — Loja Leão (+6,3%); maior
crescimento em Centro de Distribuição — Armazém Novaes (+30,8%).

**Metodologia:** crescimento real de demanda por estado do cliente (mesmo trimestre
de referência: jun-jul-ago/2026 vs. jun-jul-ago/2025), com filtro de
materialidade de volume aplicado antes do ranking por percentual — mesma lógica já
usada no MAPE ponderado: crescimento percentual sobre base pequena é ruído,
não sinal, e precisa ser descartado antes de comparar, não depois.

**Efeito do filtro de materialidade:** sem o filtro, o ranking por cidade era
dominado por variações de até +2.900%, todas saindo de bases de 1-4 unidades —
ruído estatístico puro. Filtrando para o quartil superior de volume-base (p75,
718 unidades) e agregando por estado (não cidade, grão mais compatível com a
área de cobertura real de um CD), restam 7 estados relevantes — nenhum em
crescimento:

| Estado | Demanda (trimestre-alvo) | Demanda (ano anterior) | Crescimento | Cobertura já existente |
| ------ | ------------------------ | ---------------------- | ----------- | ----------------------- |
| PI     | 796                      | 815                    | -2,3%       | Sim                     |
| AC     | 690                      | 721                    | -4,3%       | Não                    |
| TO     | 707                      | 739                    | -4,3%       | Não                    |
| RJ     | 692                      | 768                    | -9,9%       | Não                    |
| PA     | 602                      | 722                    | -16,6%      | Não                    |
| AP     | 649                      | 838                    | -22,6%      | Sim                     |
| MA     | 576                      | 922                    | -37,5%      | Não                    |

**Conclusão:** não há evidência que justifique a abertura de um novo centro de
distribuição. Os 7 estados com volume relevante estão em declínio de demanda
(-2,3% a -37,5%), não em crescimento — e mesmo o estado de maior volume (Piauí,
815 unidades no ano anterior) representa menos de 30% do volume de uma única
loja ou CD já existente (que giram na faixa de 2.500-3.500 unidades no mesmo
período). São dois motivos independentes apontando para a mesma conclusão:
ausência de crescimento real, e escala insuficiente mesmo se houvesse.

O crescimento identificado (Armazém Novaes, +30,8%) é mais bem endereçado
como reforço de capacidade da rede já existente, não como expansão geográfica.

## 13. Sistema de RAG (Assistente de Perguntas e Respostas)

### 13.1 Corpus e estratégia de recuperação

O corpus é composto por três documentos: o planejamento do projeto, a documentação técnica do modelo de previsão (este arquivo) e um resumo narrativo das previsões mais recentes, gerado automaticamente a cada ciclo mensal. Um diário de desenvolvimento inicialmente fazia parte do corpus, mas foi removido: por preservar histórico superado de propósito (decisões antigas marcadas como substituídas), ele fazia o assistente citar, ocasionalmente, números que já não eram mais válidos — o documento técnico atual (este arquivo) não tem esse problema, porque não guarda histórico superado.

Os documentos são divididos em trechos pesquisáveis (~300-500 tokens), respeitando a estrutura de seções de cada documento — nunca cortando no meio de uma ideia. Duas regras de qualidade foram aplicadas: seções sem conteúdo próprio (apenas agrupadoras de subseções) não geram trecho vazio; e seções muito curtas são combinadas com a seção seguinte **da mesma família temática**, nunca misturando assuntos sem relação (por exemplo, um trecho sobre uma loja nunca é combinado com um trecho sobre sazonalidade de produto).

### 13.2 Geração de resposta

A busca por similaridade recupera os trechos mais relevantes para cada pergunta, e um modelo de linguagem gera a resposta com base exclusivamente nesses trechos — instruído a admitir que não sabe, em vez de completar a lacuna com informação não verificada, quando o corpus não cobre o que foi perguntado.

### 13.3 Guardrails (camadas de segurança)

Implementados de forma independente do fornecedor de infraestrutura, para garantir cobertura completa mesmo sem um serviço de moderação nativo disponível no ambiente:

| Requisito | Abordagem |
|---|---|
| Remover dado sensível (CPF, e-mail) da pergunta | Filtro por padrão de texto, antes de qualquer chamada ao modelo |
| Barrar tentativa de manipular o assistente (prompt injection) | Combinação de padrões conhecidos de manipulação + classificação por modelo de linguagem |
| Barrar conteúdo violento, sexual, ilegal, discurso de ódio, assédio ou automutilação | Filtro de segurança nativo do provedor de IA + segunda camada de classificação por modelo de linguagem, na pergunta e na resposta |
| Não expor informação fora do escopo do projeto | O próprio escopo do corpus já limita isso — só documentação de projeto está disponível para consulta |
| Reduzir risco de informação inventada | Resposta ancorada exclusivamente nos trechos recuperados, nunca em conhecimento geral do modelo |
| Moderar viés ou conteúdo ofensivo na resposta gerada | Classificação por modelo de linguagem, aplicada à resposta antes de ser entregue |

### 13.4 Avaliação

Um conjunto de 16 perguntas com resposta de referência foi usado para medir a qualidade do sistema: 68,8% das perguntas recuperaram o trecho de documento esperado; 18,8% tiveram a resposta gerada considerada correta por um avaliador automático.

**Este segundo número precisa de contexto para ser interpretado corretamente** — não reflete de forma direta a qualidade real do assistente. Uma investigação sobre os casos de falha encontrou três causas distintas: parte das perguntas do conjunto de avaliação tinha como referência um documento que foi removido do corpus (ver 13.1) — a falha de recuperação nesses casos é esperada, não um defeito; o avaliador automático, em pelo menos um caso confirmado, falhou ao interpretar sua própria resposta e penalizou uma resposta correta por um problema técnico do avaliador, não do assistente; e um item do conjunto de avaliação continha uma resposta de referência incorreta (um dado fabricado, sem existir em nenhum documento real do projeto) para uma pergunta propositalmente fora do escopo do corpus — o assistente respondeu corretamente, admitindo não ter a informação, e foi penalizado por isso, já que o avaliador esperava uma resposta que na verdade seria uma alucinação.

Corrigir o conjunto de perguntas e reexecutar a avaliação é uma melhoria recomendada para um próximo ciclo, mas não foi necessária para validar que o assistente funciona corretamente nos casos observados manualmente.

### 13.5 Limitações conhecidas

- A busca por similaridade tende a favorecer trechos com linguagem mais descritiva sobre trechos muito densos em números e nomes próprios — um trecho relevante pode, ocasionalmente, não aparecer entre os primeiros resultados de uma busca. Observado em mais de uma pergunta durante o desenvolvimento; ainda não quantificado de forma abrangente.
- O filtro de segurança nativo do provedor de IA produziu, ao menos uma vez, um falso positivo — bloqueou uma pergunta de negócio legítima por reagir a um padrão de texto comum em documentação técnica, sem relação real com conteúdo perigoso. Mitigado com uma segunda camada de verificação antes de recusar definitivamente uma resposta.
- O aplicativo de conversação (ver 13.6) mantém uma cópia própria de parte do código do assistente, por uma restrição técnica do ambiente onde ele roda — mudanças futuras na lógica do assistente precisam ser replicadas manualmente nessa cópia.

### 13.6 Interface

O assistente está disponível como um aplicativo de chat, hospedado no mesmo ambiente onde os dados do projeto residem — qualquer pessoa do time com acesso ao ambiente pode conversar com ele diretamente pelo navegador, sem instalação ou conhecimento técnico.

---
