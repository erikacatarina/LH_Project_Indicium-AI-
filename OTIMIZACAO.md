# Decisões de Otimização - Pipeline de Ingestão Bronze

## 1. Estratégia de Extração: Full Load

Optamos por full load (extração completa) para as 13 tabelas em escopo, em vez de extração incremental.

**Alternativa avaliada e descartada:** incremental via join com a tabela pai para order_items (via orders.updated_at) e return_items (via returns.updated_at), já que essas duas tabelas não possuem coluna de
data própria.

**Justificativa da escolha por full load:**

- Volume total do projeto: ~293.000 linhas nas 13 tabelas - volume baixo
- Tempo de leitura medido: poucos segundos para a tabela orders (50.000 linhas), que é a tabela com volume mais alto do escopo
- Incremental exigiria controle de estado adicional (watermark) e join para as tabelas sem data própria, adicionando complexidade sem ganho de performance proporcional neste volume
- Full load com overwrite garante idempotência trivial de provar - rodar o pipeline 2x produz o mesmo resultado, sem risco de updates "silenciosos" perdidos por uma falha no controle de watermark

## 2. Script Único vs. Script por Tabela

Optamos por um único script (ingest_bronze.py) iterando sobre as 13 tabelas, em vez de um script/notebook por tabela com execução paralela.

**Justificativa:**

- Simplicidade de manutenção
- Volume de dados não exige paralelismo real para caber na janela de execução diária
- Menor superfície de configuração no Databricks Workflows

## 3. Schema Explícito em vez de Inferência Automática

Todas as 13 tabelas têm schema declarado explicitamente (dicionário SCHEMAS no script), com cast forçado por coluna.

**Justificativa:**

- Evita que o Spark infira o tipo errado caso uma coluna venha vazia em uma execução específica
- Garante consistência de tipo entre execuções, mesmo com mudanças no conteúdo dos dados
- Identificado ponto de atenção real: payments.installments deve ser ShortType, não IntegerType (inferência automática provavelmente acertaria IntegerType por padrão)

## 4. Particionamento: Auto-Otimização Nativa, sem PARTITIONED BY

Conforme CONVENTIONS.md, não aplicamos particionamento físico tradicional, dado o volume do projeto estar muito abaixo do limiar de 1TB. A coluna ingestion_date é gravada em todas as tabelas Bronze
desde já, preparando uma futura migração para Liquid Clustering (CLUSTER BY) caso o volume cresça significativamente.

## 5. Modularização do Script

O ingest_bronze.py é estruturado em 6 funções de responsabilidade única (conectar_jdbc, aplicar_schema, extrair_tabela, montar_nome_tabela_bronze, escrever_bronze, main), facilitando
manutenção, testes isolados e reuso de lógica.

## 6. Resultado Medido

| Métrica                                   | Valor                                    |
| ------------------------------------------ | ---------------------------------------- |
| Volume total (13 tabelas)                  | ~293.000 linhas                          |
| Tempo de leitura — orders (50.000 linhas) | 0.60 segundos                            |
| Estratégia de escrita                     | Overwrite (full load + idempotência)    |
| Particionamento físico                    | Não aplicado (auto-otimização nativa) |
| Schema                                     | Explícito, com cast forçado por coluna |
