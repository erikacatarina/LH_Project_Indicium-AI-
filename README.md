# ⚓ LH Nautical - Plataforma de Dados, Previsão de Demanda e Assistente Inteligente

Solução completa de dados para a **LH Nautical**, um varejo náutico brasileiro (loja física + e-commerce, desde 2020, sede em Florianópolis). O projeto cobre toda a jornada do dado: da extração no sistema transacional até um assistente de inteligência artificial que responde perguntas sobre o negócio em linguagem natural.

---

## Sumário

- [Sobre o Projeto](#sobre-o-projeto)
- [Arquitetura Geral](#arquitetura-geral)
- [1. Ingestão de Dados](#1-ingestão-de-dados)
- [2. Modelagem de Dados (dbt)](#2-modelagem-de-dados-dbt)
- [3. Previsão de Demanda](#3-previsão-de-demanda)
- [4. Assistente Inteligente (RAG)](#4-assistente-inteligente-rag)
- [5. Dashboard de Business Intelligence](#5-dashboard-de-business-intelligence)
- [Como Reproduzir o Ambiente](#como-reproduzir-o-ambiente)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Limitações Conhecidas](#limitações-conhecidas)
- [Equipe](#equipe)

---

## Sobre o Projeto 

A LH Nautical identificou seis dificuldades recorrentes na gestão do negócio:

1. **Faturamento líquido inconsistente** - dificuldade de enxergar receita real, descontada de impostos e devoluções.
2. **Invisibilidade do cliente omnichannel** - loja física e e-commerce eram enxergados como negócios separados.
3. **Morosidade na decisão comercial** - informação espalhada, sem relatório consolidado.
4. **Falta de segmentação de clientes de alto valor** - nenhuma visão de quais clientes geram mais retorno.
5. **Ruptura de estoque e falta de previsibilidade temporal** - compras reativas, sem previsão de demanda.
6. **Ineficiência em campanhas por categoria de produto** - dificuldade de identificar produtos/categorias prioritários.

Este repositório resolve as seis, em camadas sucessivas: primeiro organizando o dado (ingestão + modelagem), depois expondo ele em um dashboard executivo (Power BI), e por fim adicionando duas capacidades preditivas - um modelo de previsão de demanda e um assistente de IA que qualquer pessoa do time pode consultar em linguagem natural.

---

## Arquitetura Geral

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│  [SQL Server]  →  [🥉 Bronze]  →  [🥈 Silver]  →  [🥇 Gold]  → ┬─ [Power BI]     │
│   Sistema de       Ingestão        Modelagem       Dados         │               │
│   vendas da        (PySpark        dimensional     prontos       ├─ [Modelo      │
│   loja             + JDBC)         (dbt Core)       para          │  de          │
│                                                     consumo        │  Previsão]  │
│                                                                    │             │
│                                                                    └─ [Assistente│
│                                                                       de IA/RAG] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Toda a plataforma roda sobre **Databricks** (Lakehouse + Unity Catalog), com dois ambientes isolados por catálogo: `dev` (desenvolvimento) e `prd` (produção). O deploy de cada camada é automatizado via **Databricks Asset Bundles** e **Bitbucket Pipelines** - um merge na branch `dev` implanta em desenvolvimento, um merge na branch `main` implanta em produção.

---

## 1. Ingestão de Dados

**O que faz:** extrai 13 tabelas do sistema transacional (SQL Server) e as carrega, sem transformação de regra de negócio, na camada Bronze do Lakehouse - a base sobre a qual tudo mais é construído.

| Item | Detalhe |
|---|---|
| Tabelas extraídas | 13 (pedidos, itens de pedido, pagamentos, devoluções, clientes, produtos, categorias, marcas, locais, funcionários, notas fiscais, entre outras) - cerca de 293 mil linhas no total |
| Volume/estratégia | Extração completa (full load) a cada execução - o volume é baixo o suficiente para não exigir carga incremental |
| Formato de armazenamento | Delta Lake, com escrita em modo `overwrite` - garante que rodar o processo mais de uma vez produz sempre o mesmo resultado |
| Tecnologia | PySpark, conectando via JDBC (conexão criptografada) |
| Orquestração | Databricks Workflows - agendado diariamente em produção, execução manual em desenvolvimento |
| Credenciais | Databricks Secrets - nunca expostas em código ou no repositório |

**Dado sensível:** a tabela de funcionários contém CPF, que é mascarado (mantendo só os últimos dígitos visíveis) antes de chegar em qualquer camada de consumo.

---

## 2. Modelagem de Dados (dbt)

**O que faz:** transforma o dado bruto da Bronze num modelo dimensional (esquema estrela) pronto para consumo - 35 modelos ao todo, organizados em três camadas.

| Camada | Modelos | Papel |
|---|---|---|
| Staging | 13 | Padronização 1:1 com a origem, sem regra de negócio |
| Intermediate | 10 | Conformação de entidades, correções e enriquecimento |
| Marts | 12 (9 dimensões + 3 fatos) | Dado final, pronto para análise |

**As 3 tabelas de fato:**
- `fct_orders` - vendas, no grão de item de pedido.
- `fct_returns` - devoluções, no grão de item devolvido.
- `fct_desempenho_mensal_produto_vendedor` - um snapshot mensal por produto e vendedor.

**As 9 dimensões:** cliente (com segmentação por valor/recência/frequência), produto, calendário (com feriados e marcação de alta temporada náutica), funcionário, local, canal de venda, status do pedido, método de pagamento e status de pagamento.

**Decisões de modelagem que valem registrar:**
- O grão de vendas e devoluções é o **item**, não o pedido inteiro - isso permite relacionar cada linha diretamente com o produto vendido.
- Descontos são **rateados proporcionalmente** entre os itens de um mesmo pedido (a origem não guarda desconto por item).
- Pedidos sem vendedor (compras pelo site) recebem um vendedor padrão, identificado como "E-commerce".
- "Alta temporada náutica" (dezembro a março) é uma suposição de negócio, baseada no verão brasileiro - período em que a demanda por produtos náuticos tende a subir.

**Qualidade de dado:** todas as chaves primárias e relacionamentos são testados automaticamente, além de quatro testes de negócio específicos (ex.: conferir que a receita líquida bate com a soma dos itens, que não existe ciclo na hierarquia de categorias).

---

## 3. Previsão de Demanda

**O que faz:** prevê a demanda de cada produto, em cada loja e centro de distribuição, para os próximos 3 meses e responde quatro perguntas centrais para o planejamento de estoque e expansão da rede.

### As quatro perguntas respondidas

1. **Quanto cada produto vai vender, em cada local, nos próximos 3 meses?** E existe algum produto com padrão sazonal comprovado estatisticamente?
2. **Qual modelo de previsão é o mais adequado, e por quê?**
3. **Qual loja e qual centro de distribuição devem crescer mais?**
4. **A rede precisa de um novo centro de distribuição? Se sim, onde?**

### Como a previsão é feita

- **Dois modelos independentes**, um para lojas e outro para centros de distribuição os dois nunca são combinados no treino, porque representam tipos de demanda diferentes (venda ao consumidor final vs. movimentação logística entre a rede).
- **Quatro algoritmos de regressão foram testados e comparados** (Ridge, Random Forest, LightGBM e CatBoost) contra uma base de comparação simples (média móvel).
- **Modelo escolhido: CatBoost**, para os dois tipos de local. As diferenças de precisão entre os quatro algoritmos testados foram pequenas, a decisão final se baseou na vantagem prática do CatBoost em lidar nativamente com variáveis de categoria de produto, sem exigir pré-processamento adicional.
- **O modelo supera a previsão ingênua (média móvel) entre 11% e 21%**, dependendo da época do ano, a vantagem é um pouco menor durante a alta temporada, quando a demanda é naturalmente mais imprevisível para qualquer método.
- Além da previsão pontual, o modelo também estima uma **faixa de confiança** (intervalo de 80%), usada como referência para estoque de segurança.

### Principais achados

- **Sazonalidade comprovada estatisticamente** em dois produtos (baterias náuticas, tanto na linha de lojas quanto na de centros de distribuição), o padrão é consistente com a troca/recarga de bateria antes do início da temporada de navegação.
- **Crescimento por local** e **necessidade de novos centros de distribuição** são reavaliados a cada ciclo de previsão, cruzando o crescimento real de demanda por região com a cobertura já existente da rede, evitando abrir um novo centro de distribuição baseado em ruído estatístico de uma base pequena de vendas.

### Onde os resultados vivem

- Previsões: tabela `fct_previsao_demanda`, no catálogo de produção, atualizada mensalmente.
- Relatório consolidado, respondendo as quatro perguntas com gráficos: `docs/Relatorio_Analise_Previsao.md` (gerado automaticamente, todo mês).
- Documentação técnica completa do modelo (métricas, premissas verificadas, limitações): `docs/MODEL_CARD.md`.

---

## 4. Assistente Inteligente (RAG)

**O que faz:** um assistente conversacional que responde perguntas em português sobre o projeto previsão de demanda, sazonalidade, modelos usados, crescimento por região consultando a documentação e os resultados reais do projeto antes de responder, para nunca inventar informação.

### Como funciona, em linhas gerais

1. A documentação do projeto e um resumo das previsões mais recentes são organizados em pequenos trechos pesquisáveis.
2. Quando alguém faz uma pergunta, o assistente busca os trechos mais relevantes para aquela pergunta.
3. Um modelo de linguagem gera a resposta **usando apenas esses trechos como base** - se a informação não estiver disponível, o assistente responde que não sabe, em vez de inventar um número ou um fato.

### Camadas de segurança

Antes de qualquer resposta ser gerada, a pergunta passa por verificações automáticas que:
- Removem dados sensíveis (como CPF ou e-mail) da pergunta antes de qualquer processamento.
- Bloqueiam tentativas de manipular o assistente para ignorar suas instruções.
- Barram pedidos de conteúdo impróprio, perigoso ou fora do propósito do assistente (que é falar sobre este projeto).

A resposta final também passa por uma segunda checagem, antes de ser entregue.

### Como usar

O assistente está disponível como um aplicativo interno no Databricks (Databricks Apps), qualquer pessoa do time com acesso ao workspace pode abrir a interface e conversar com ele diretamente, sem precisar de conhecimento técnico.

---

## 5. Dashboard de Business Intelligence

**O que faz:** um relatório executivo interativo (Power BI), com 11 páginas, conectado diretamente aos dados de produção cobrindo faturamento, comportamento de pedidos, distribuição geográfica, perfil de clientes e desempenho de produtos.

### Principais páginas

| Página | O que mostra |
|---|---|
| Geral | Visão executiva macro - receita, pedidos, ticket médio, comparação com o ano anterior |
| Pedidos | Detalhamento de pedidos, com opção de visualizar em mapa ou em tabela |
| Regiões | Desempenho por localização geográfica |
| Clientes | Segmentação de clientes por valor e frequência de compra |
| Produtos | Ranking de produtos por receita e margem, curva ABC |
| Relatório Gerencial | Versão formatada para exportação em PDF, com filtro por ano |

### Como os dados chegam até o Power BI

O relatório se conecta diretamente ao catálogo de produção do Databricks, importando as 12 tabelas de dado finais (dimensões e fatos). Para trocar de ambiente (por exemplo, de desenvolvimento para produção), basta atualizar dois parâmetros de conexão, nenhuma consulta individual precisa ser alterada.

Documentação técnica completa (dicionário de medidas, modelo de dados, tema visual): `docs/Documentacao_PowerBI.md`.

---

## Como Reproduzir o Ambiente

### Pré-requisitos

- Python 3.10+
- Acesso a um workspace Databricks com Unity Catalog
- Um SQL Warehouse ativo no workspace
- Databricks CLI (versão com suporte a `bundle`):
  ```bash
  curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
  databricks configure --token
  ```

### Configuração inicial (uma única vez por workspace)

```bash
python infra/setup_catalogs.py
```
Cria os catálogos `dev` e `prd`, e os schemas `bronze`, `silver` e `gold` em cada um.

### Rodando a ingestão e a modelagem localmente

```bash
# Ingestão
python src/ingestion/ingest_bronze.py --catalog dev

# Modelagem (dbt)
cd dbt/lh_nautical
pip install -r requirements.txt
dbt deps
cp .env.example .env   # preencher com suas credenciais
dotenv run -- dbt build
```

### Rodando a previsão de demanda e o assistente de IA

```bash
# Na raiz do repositório
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher com suas credenciais
```

A geração da previsão e a atualização do assistente rodam como jobs agendados no Databricks, não exigem execução manual no dia a dia. Para rodar manualmente:
```bash
databricks bundle run lh_nautical_producao_mensal --target prd
databricks bundle run lh_nautical_rag_chunking --target prd
```

### Deploy

```bash
databricks bundle validate
databricks bundle deploy --target dev   # ou --target prd
```
O deploy também acontece automaticamente a cada merge nas branches `dev` e `main`, via Bitbucket Pipelines.

---

## Estrutura do Repositório

```
lh-nautical/
├── bitbucket-pipelines.yml
├── databricks.yml
├── README.md                          # este arquivo
├── infra/
│   └── setup_catalogs.py
├── src/
│   ├── ingestion/
│   │   └── ingest_bronze.py
│   ├── forecast/                      # previsão de demanda
│   ├── rag/                           # assistente de IA
│   └── relatorio/                     # geração automática do relatório de previsão
├── app/                               # aplicativo do assistente de IA (Databricks Apps)
├── dbt/
│   └── lh_nautical/
│       ├── models/
│       │   ├── staging/
│       │   ├── intermediate/
│       │   └── marts/
│       ├── macros/
│       ├── seeds/
│       └── tests/
└── docs/
    ├── MODEL_CARD.md                  # documentação técnica do modelo de previsão e do RAG
    ├── Relatorio_Analise_Previsao.md  # relatório de negócio, atualizado mensalmente
    ├── Documentacao_PowerBI.md        # documentação técnica do dashboard
    └── relatorios/                    # histórico mensal de relatórios e gráficos
```

---

## Limitações Conhecidas

- O cálculo de imposto é uma aproximação (soma simples de alíquotas) - a origem não guarda o valor de imposto já calculado por item.
- O período de "alta temporada náutica" é uma suposição de negócio, não uma medição direta de sazonalidade real de mercado.
- Combinações de produto e local com histórico de vendas insuficiente usam uma estimativa simplificada (média da categoria), em vez do modelo completo de previsão.
- A precisão do modelo de previsão cai um pouco durante a alta temporada, quando a demanda é naturalmente mais volátil - uma oportunidade de melhoria já identificada para trabalho futuro.
- O assistente de IA ocasionalmente pode deixar de recuperar a informação mais relevante para perguntas muito específicas - uma limitação conhecida de sistemas de busca por similaridade, sendo monitorada e documentada em `docs/MODEL_CARD.md`.

---

## Equipe

**Representante de Negócios:** Aline Satomi Noce

**Time de Desenvolvimento:** Bruna Aparecida da Silva Santos Nogueira, Carla Lira Rodrigues, Erika Catarina e Renan Amaral de Oliveira

**Stakeholders:** Beatriz Kenup, Hevans Vinicius Pereira e Leonardo Gasparotto Menini