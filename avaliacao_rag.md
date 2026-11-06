# Relatório de Avaliação do RAG — LH Nautical

**Total de perguntas avaliadas:** 16
**Taxa de recuperação correta (chunk esperado no top-5):** 68.8%
**Taxa de resposta correta (LLM-as-judge):** 18.8%

## Detalhe por pergunta

### Qual produto tem sazonalidade confirmada na loja, e por quê?
- Recuperação (MODEL_CARD.md): ✅
- Correção: ❌ — O sistema rejeita a pergunta sem fornecer a informação solicitada; a resposta não inclui o produto nem a razão estatística apresentada no gabarito.
- Resposta gerada: Não posso ajudar com essa solicitação. Se a pergunta for sobre o projeto LH Nautical, tente reformular de forma mais direta.

### Qual produto tem sazonalidade confirmada no centro de distribuição, e por quê?
- Recuperação (MODEL_CARD.md): ✅
- Correção: ✅ — A resposta gerada menciona corretamente a Bateria Náutica 834 (variante 341) e inclui tanto a força STL de 0,580 quanto o p‑valor de Mann‑Whitney de 0,029, capturando todas as informações essenciais da referência.
- Resposta gerada: O produto que apresenta sazonalidade confirmada no centro de distribuição é a **Bateria Náutica 834** (variante 341).

**Por que esta variante é reconhecida como sazonal:**

1. **Seleção preliminar:** Foi escolhida como candidata em um índice de razão (alta temporada vs. resto do ano) que já indica 

### Qual modelo de regressão foi escolhido para o forecast, e por quê?
- Recuperação (MODEL_CARD.md): ✅
- Correção: ✅ — A resposta identifica corretamente que o modelo escolhido foi CatBoost e explica a razão principal—o tratamento nativo de variáveis categóricas e a pequena diferença de métricas entre os quatro modelos testados—coincidindo com a informação da referência.
- Resposta gerada: **Modelo escolhido:** CatBoost (nos dois pipelines de forecast).

**Razões baseadas no contexto:**

1. **Desempenho equilibrado** – As quatro abordagens avaliadas (Ridge/Lasso, Random Forest, LightGBM e CatBoost) apresentaram variações muito pequenas nas três métricas (MAE, RMSE e MAPE).  
   - No “

### Qual a vantagem do modelo escolhido sobre a baseline de médias móveis?
- Recuperação (MODEL_CARD.md): ✅
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: O modelo escolhido – CatBoost – mostra uma performance consistente superior à baseline de médias móveis em todas as métricas registradas (MAE, RMSE e MAPE).  
Conforme o *Model Card*:

* **Redução do erro**  
  - Na janela mais recente (abr‑ago/2026) a redução do MAE é de **18,7 % para o pipeline de


Isso inclui:

* **Treinamento e calibração** dos algoritmos de previsão após a fase de “pós‑quarentena”, ajustando os limiares de cada pi

### Qual o escopo de forecasting definido?
- Recuperação (Planejamento.docx): ✅
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: O escopo de forecasting está claramente delineado no documento “Planejamento.docx” (seções 1 e 2) e nos detalhes técnicos de “Forecast”:

- **Horizonte:** previsão de demanda para os próximos **3 meses**.  
- **Granularidade:** por **produto × loja** (produto e loja são as dimen

### Qual local (loja ou centro de distribuição) tem a maior previsão de demanda total?
- Recuperação (resumo_previsoes.md): ✅
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: O local com a maior previsão de demanda total é o **Armazém Camargo**, que estima 179 42 unidades para o próximo trimestre.

### Qual a previsão de demanda para a categoria Hélices?
- Recuperação (resumo_previsoes.md): ✅
- Correção: ✅ — A resposta gera o mesmo valor inteiro da previsão (10.716 unidades) e menciona que é para o próximo trimestre, coincidindo com a informação central. Os detalhes adicionais sobre a percentagem de aumento e o valor do ano anterior são extras não contraditórios à referência.
- Resposta gerada: A previsão de demanda da categoria **Hélices** para o próximo trimestre é de **10.716 unidades**. Isso representa um aumento de 172,3 % em relação ao mesmo trimestre do ano anterior, que era de 3.936 unidades.

### Quais produtos devem ter a maior queda de demanda no próximo trimestre?
- Recuperação (resumo_previsoes.md): ✅
- Correção: ❌ — A resposta não fornece a lista de produtos e quocientes de queda de demanda que a referência detalha; portanto, não captura a informação essencial.
- Resposta gerada: Não posso ajudar com essa solicitação. Se a pergunta for sobre o projeto LH Nautical, tente reformular de forma mais direta.

### Qual o limiar de histórico suficiente usado para loja e para centro de distribuição?
- Recuperação (MODEL_CARD.md): ✅
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: **Limiar de histórico suficiente (segundo a documentação):**

| Pipeline                     | Limiar de períodos exigido | % de combinações maduras (ex.: 2728 de 3027) | % volume coberto |
|------------------------------|---------------------------|-------------------------------------------|------

### Quais foram os modelos de regressão treinados e comparados para o forecast?
- Recuperação (Planejamento.docx): ✅
- Correção: ❌ — A resposta gerada recusou a pergunta e não mencionou nenhum dos modelos de regressão listados na resposta de referência.
- Resposta gerada: Não posso ajudar com essa solicitação. Se a pergunta for sobre o projeto LH Nautical, tente reformular de forma mais direta.

### O estudo recomendou a abertura de novos centros de distribuição? Qual foi a justificativa?
- Recuperação (Progresso.docx): ❌
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: Não.  
O estudo concluiu que **não há evidência que justifique a abertura de um novo centro de distribuição**.  

**Justificativa**

1. **Falta de crescimento** – Os 7 estados com volume relevante (AC, TO, RJ, PA, AP, MA e PI) apresentam queda de demanda no último trimestre (entre –2,3 % e –37,5 %),

### Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?
- Recuperação (Progresso.docx): ❌
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: Não há uma explicação explícita no contexto que descreva a razão pela qual a equipe decidiu não usar a agregação pelo *product_id* (produto principal). O que está documentado é apenas que o modelo de forecast foi projetado com a granularidade de `product_variant_id × location_id × mês` — essa escolh

### Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?
- Recuperação (Progresso.docx): ❌
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: Não há nenhuma informação no material do projeto que explique a razão específica pela qual a equipe escolheu agrupar pelos *product_variant_id* em vez de pelos *product_id*.  O contexto apenas descreve que o grain da mart e dos modelos é `product_variant_id × location_id × mês` e que esse nível de g

### Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?
- Recuperação (Progresso.docx): ❌
- Correção: ❌ — erro de avaliação, resposta do juiz não pôde ser interpretada
- Resposta gerada: Não posso ajudar com essa solicitação. Se a pergunta for sobre o projeto LH Nautical, tente reformular de forma mais direta.

### Quem foi o principal fornecedor de insumos responsável pela obra de infraestrutura civil do Armazém Camargo em 2025?
- Recuperação (Progresso.docx): ❌
- Correção: ❌ — A resposta não menciona o fornecedor correto (Construtora Nova Era) e apenas afirma ausência de informação.
- Resposta gerada: Não tenho essa informação disponível no contexto que me foi fornecido.
