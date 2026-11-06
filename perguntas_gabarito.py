"""Conjunto de perguntas-gabarito para avaliação do RAG — LH Nautical.

Revisado manualmente pelo time antes de cada execução da avaliação.
Cada entrada tem a pergunta, a resposta de referência (o que
um humano consideraria correto), e o documento/seção onde essa informação
deveria estar, usado na checagem de recuperação.
"""

PERGUNTAS_GABARITO = [
    {
        "pergunta": "Qual produto tem sazonalidade confirmada na loja, e por quê?",
        "resposta_esperada": "Bateria Náutica 8635 (variante 396), com força STL de 0,816 e p-valor de Mann-Whitney de 0,0037, os dois indicando significância estatística.",
        "documento_esperado": "MODEL_CARD.md",
    },
    {
        "pergunta": "Qual produto tem sazonalidade confirmada no centro de distribuição, e por quê?",
        "resposta_esperada": "Bateria Náutica 834 (variante 341), com força STL de 0,580 e p-valor de Mann-Whitney de 0,029.",
        "documento_esperado": "MODEL_CARD.md",
    },
    {
        "pergunta": "Qual modelo de regressão foi escolhido para o forecast, e por quê?",
        "resposta_esperada": "CatBoost, nos dois pipelines — pela vantagem estrutural de tratar variáveis categóricas nativamente, sem precisar de one-hot encoding, já que a diferença de métrica entre os 4 modelos testados é pequena.",
        "documento_esperado": "MODEL_CARD.md",
    },
    {
        "pergunta": "Qual a vantagem do modelo escolhido sobre a baseline de médias móveis?",
        "resposta_esperada": "Entre 18,7% e 20,7% em condições normais; entre 11,3% e 11,6% em alta temporada histórica testada à parte.",
        "documento_esperado": "MODEL_CARD.md",
    },
    {
        "pergunta": "Qual é o objetivo geral desta etapa?",
        "resposta_esperada": "Nesta etapa, a LH Nautical utilizará o Data Warehouse já estruturado para gerar insights de previsão de demanda e logística, devendo responder a quatro questões centrais: a projeção trimestral por produto e loja (com análise de sazonalidade), a comparação de desempenho entre modelos de regressão e médias móveis, a identificação do Centro de Distribuição e loja com maior crescimento projetado, e a indicação de possíveis novos polos de distribuição.",
        "documento_esperado": "Planejamento.docx",
    },
    {
        "pergunta": "Qual o escopo de forecasting?",
        "resposta_esperada": "O projeto será executado sob as restrições do Databricks Free Edition (serverless, sem GPU, recursos limitados) e é composto por duas frentes operacionais: um Forecast trimestral (grão produto/loja) que compara modelos de regressão a uma baseline de médias móveis, salvando as previsões no Unity Catalog; e um sistema RAG estruturado com a documentação do projeto e resumos das previsões (usando embeddings Qwen3 e geração GPT-OSS-20B), com avaliação via LLM-as-judge e guardrails manuais. Todo o desenvolvimento será guiado por rigorosas premissas de engenharia, incluindo TDD, DRY, modularização com scripts, orquestração via Workflows e rastreabilidade pelo MLflow.",
        "documento_esperado": "Planejamento.docx",
    },
    {
        "pergunta": "Qual local (loja ou centro de distribuição) tem a maior previsão de demanda total?",
        "resposta_esperada": "O centro de distribuição Armazém Camargo tem previsão de demanda total de 17942 unidades para o próximo trimestre.",
        "documento_esperado": "resumo_previsoes.md",
    },
    {
        "pergunta": "Qual a previsão de demanda para a categoria Hélices?",
        "resposta_esperada": "A categoria Hélices tem previsão de demanda total de 10716 unidades para o próximo trimestre.",
        "documento_esperado": "resumo_previsoes.md",
    },
    {
        "pergunta": "Quais produtos devem ter a maior queda de demanda no próximo trimestre?",
        "resposta_esperada": "As combinações com maior queda prevista são: Vela Mestra 2410 na Armazém Novaes (-62.3%); Vela Mestra 2410 na Armazém Siqueira (-59.2%); Âncora Bruce 1231 na Loja Leão (-55.8%); Motor de Popa 7932 na Loja Leão (-52.4%); GPS Pltoter 3205 na Armazém Siqueira (-50.4%).",
        "documento_esperado": "resumo_previsoes.md",
    },
    {
        "pergunta": "Qual o limiar de histórico suficiente usado para loja e para centro de distribuição?",
        "resposta_esperada": "Loja: 14 meses / 20% de cobertura. Centro de Distribuição: 15 meses / 20% de cobertura — calibrados de forma independente por pipeline.",
        "documento_esperado": "MODEL_CARD.md",
    },

    {
        "pergunta": "Quais foram os modelos de regressão treinados e comparados para o forecast?",
        "resposta_esperada": "Os modelos treinados foram: Ridge/Lasso, Random Forest, LightGBM (ou XGBoost) e CatBoost.",
        "documento_esperado": "Planejamento.docx",
    },

    {
        "pergunta": "O estudo recomendou a abertura de novos centros de distribuição? Qual foi a justificativa?",
        "resposta_esperada": "Não. Os 7 estados com volume relevante de vendas estão com demanda em declínio, e mesmo o estado com maior volume (Piauí) representa menos de 30% do volume de uma única loja ou CD atual.",
        "documento_esperado": "Progresso.docx",
    },

    {
        "pergunta": "Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?",
        "resposta_esperada": "Optaram pela variante (SKU) porque produtos sob o mesmo ID tinham preços muito discrepantes. Misturá-los em uma previsão única perderia a informação exata necessária para orientar a reposição de estoque real.",
        "documento_esperado": "Progresso.docx",
    },

    {
        "pergunta": "Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?",
        "resposta_esperada": "Optaram pela variante (SKU) porque produtos sob o mesmo ID tinham preços muito discrepantes. Misturá-los em uma previsão única perderia a informação exata necessária para orientar a reposição de estoque real.",
        "documento_esperado": "Progresso.docx",
    },

    {
        "pergunta": "Por que a equipe evitou agregar os dados pelo produto principal (product_id) e optou por usar a variante do produto (product_variant_id)?",
        "resposta_esperada": "Optaram pela variante (SKU) porque produtos sob o mesmo ID tinham preços muito discrepantes. Misturá-los em uma previsão única perderia a informação exata necessária para orientar a reposição de estoque real.",
        "documento_esperado": "Progresso.docx",
    },

    {
        "pergunta": "Quem foi o principal fornecedor de insumos responsável pela obra de infraestrutura civil do Armazém Camargo em 2025?",
        "resposta_esperada": "O principal fornecedor de insumos foi a empresa Construtora Nova Era, especializada em obras de grande porte e com histórico de fornecimento para projetos logísticos.",
        "documento_esperado": "Progresso.docx",
    },

]