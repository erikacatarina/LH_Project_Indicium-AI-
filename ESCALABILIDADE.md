# Estratégia de Escalabilidade - Pipeline de Ingestão Bronze

## 1. Cenário Atual

O pipeline foi projetado e otimizado para o volume atual do projeto: ~293.000 linhas distribuídas em 13 tabelas, com execução completa em poucos segundos.
As decisões de otimização (full load, schema explícito, sem particionamento físico) são adequadas a este volume - ver OTIMIZACAO.md.

Este documento descreve como cada decisão se comportaria com um crescimento de 10x no volume (~2,9 milhões de linhas) e quais mudanças seriam necessárias.

## 2. Estratégia de Extração: Full Load → Incremental

**Comportamento com 10x o volume:** o tempo de extração full load cresceria proporcionalmente. Mesmo que ainda fosse tecnicamente viável, o tempo de execução diária aumentaria a ponto de tornar o
full load uma escolha cara em termos de custo computacional (DBUs consumidos a cada execução completa).

**Mudança recomendada:** migrar para extração incremental, usando a coluna updated_at já disponível em 11 das 13 tabelas. Para order_items e return_items (sem coluna de data própria), aplicar a
estratégia de join com a tabela pai (orders.updated_at e returns.updated_at, respectivamente) - alternativa já avaliada e descartada nesta fase, mas pronta para reativação quando o volume
justificar a complexidade adicional.

Seria necessário introduzir uma tabela de controle de watermark (ex: bronze_controle_ingestao) para rastrear a última data processada por tabela, e adaptar a lógica de escrita de overwrite para merge/upsert (garantindo idempotência sem reprocessar tudo).

## 3. Estrutura do Script: Opção A → Paralelização (Opção B)

**Comportamento com 10x o volume:** o script único, sequencial, processando uma tabela por vez, levaria 10x mais tempo para completar o ciclo de todas as tabelas.

**Mudança recomendada:** migrar para a Opção B - um notebook/task por tabela, orquestrados em paralelo pelo Databricks Workflows. Tabelas sem dependência entre si (a maioria das
13) podem ser extraídas simultaneamente, reduzindo o tempo total de execução de forma proporcional ao grau de paralelismo disponível no cluster.

## 4. Particionamento: Auto-Otimização → Liquid Clustering

**Comportamento com 10x o volume:** ainda abaixo do limiar de 1TB
(~2,9 milhões de linhas continuam sendo um volume pequeno em bytes
para a maioria das tabelas do projeto), a auto-otimização nativa
provavelmente continuaria suficiente.

**Gatilho de mudança:** se o volume ultrapassar 1TB em alguma tabela específica (cenário mais provável para order_items, dado seu volume já ser o maior do escopo), ativar Liquid Clustering via
CLUSTER BY (ingestion_date) - a coluna já está sendo gravada desde a primeira versão do pipeline, eliminando a necessidade de reprocessamento histórico para habilitar o clustering.

## 5. Configuração de Cluster

**Comportamento com 10x o volume:** o cluster single-node atual (adequado ao Free Edition) se tornaria um gargalo, já que não há paralelismo de workers para distribuir o
processamento.

**Mudança recomendada:** migrar para um cluster multi-node (fora do Free Edition) ou avaliar o uso de Databricks Serverless SQL/Jobs Compute com autoscaling, permitindo que o número de workers cresça
dinamicamente conforme a carga de cada execução.

## 6. Ingestão: PySpark Manual → Lakeflow Connect

O Databricks Lakeflow Connect oferece CDC (Change Data Capture) nativo para SQL Server, com ingestão incremental automática e idempotência garantida pela própria
ferramenta - eliminando a necessidade de implementar manualmente o controle de watermark e merge/upsert descritos no item 2.

**Quando seria a evolução natural:** com volume 10x maior, o Lakeflow Connect se torna a escolha de maior valor - gerenciando CDC automaticamente e reduzindo a manutenção manual de uma lógica de incremental construída do zero.

## 7. Resumo das Mudanças por Gatilho de Volume

| Componente              | Volume Atual (~293k)       | Gatilho de Mudança           | Volume 10x (~2,9M)                  |
| ----------------------- | -------------------------- | ----------------------------- | ----------------------------------- |
| Extração              | Full load                  | Tempo de execução crescente | Incremental (watermark + join)      |
| Estrutura do script     | Opção A (sequencial)     | Tempo de ciclo completo alto  | Opção B (paralelo via Workflows)  |
| Particionamento         | Auto-otimização nativa   | Tabela individual > 1TB       | Liquid Clustering (CLUSTER BY)      |
| Cluster                 | Single-node (Free Edition) | Gargalo de processamento      | Multi-node / Serverless autoscaling |
| Ferramenta de ingestão | PySpark + JDBC manual      | Tempo de execução crescente | Databricks Lakeflow Connect (CDC)   |
