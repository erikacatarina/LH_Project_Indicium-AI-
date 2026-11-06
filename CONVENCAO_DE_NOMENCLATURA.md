# CONVENÇÃO DE NOMENCLATURA — LH Nautical (Data Platform)

> 1. Documento de decisões de nomenclatura e padronização do projeto **LH Nautical**.
> 2. Todas as convenções aqui definidas devem ser seguidas por **todos** os membros do time.
> 3. Atualizações devem ser aprovadas pelo time antes de serem aplicadas.

---

<br>

## 1. Regras Universais de Sintaxe

> Todas as entidades criadas no ambiente _(catálogos, esquemas, tabelas, colunas, volumes e views)_ devem seguir **estritamente** as regras abaixo:

<br>

- **Formato geral:** Todos os nomes usam **letras minúsculas:**

```
✅ Certo: vendas_varejo | data_cadastro
❌ Errado: Vendas_Varejo | DataCadastro | VENDAS
```

<br>

- **Separação:** Palavras separadas por _underscore_ (`_`) **Snake Case**, exceto clusters, que usam _hífen_ (`-`) **Kebab Case**:

```
✅ Certo: tabela_clientes_ativos (tabela) | shared-dev-clst (cluster)
❌ Errado: tabela-clientes-ativos (tabela) | shared_dev_clst (cluster)
```

<br>

- **Escrita e Formatação:** Sem espaços, acentos ou caracteres especiais

```
✅ Certo: configuracao_usuario | preco_unitario
❌ Errado: configuração_usuário | preço_unitário | id cliente
```

<br>

- **Camadas Bronze e Silver:** O nome da tabela deve ser precedido pelo prefixo `<origem>_` e seguido pelo nome original da origem (convertido para `snake_case`).

```
✅ Certo: Origem: ORDERS (sistema sql) ➡️ Databricks: sql_orders
❌ Errado: Origem: ORDERS ➡️ Databricks: orders | orders_bronze | tb_orders
```

> 💡 **Nota de Projeto:** O prefixo `<origem>` identifica o sistema de origem do dado (ex: `sql_orders`, `crm_orders`, `ga_users`). No escopo atual da LH Nautical, a fonte principal é o banco SQL Server transacional, identificada pelo prefixo `sql_`. Adotamos o prefixo desde já, devido a possibilidade de incorporar novas fontes de dados. Isso evita colisão de nomes e retrabalho de renomeação no meio do projeto.

<br>

- **Camada Gold:** O nome da tabela **não segue a origem nem o prefixo de sistema**. Ele deve refletir o modelo de negócio (Fatos e Dimensões), utilizando os prefixos `fct_` (para tabelas fato) ou `dim_` (para tabelas dimensão).

```
✅ Certo: Origem: sql_orders + sql_order_items ➡️ Databricks: fct_vendas
❌ Errado: Origem: sql_orders + sql_order_items ➡️ Databricks: gold_sql_orders_order_items
```

<br>

- Nomes devem ser **descritivos e consistentes** entre camadas

```
✅ Certo: sql_orders (Bronze/Silver) ➡️ fct_vendas (Gold)
❌ Errado: ord (Bronze) ➡️ fato_vendas_consolidado (Gold)
```

---

<br>

## 2. Ambientes (Catalog)

O ecossistema está dividido em três ambientes isolados logicamente, onde cada ambiente corresponde a um **Catálogo** (`Catalog`) no Unity Catalog, disponível por padrão mesmo no Databricks Free Edition, que provisiona automaticamente um metastore e permite a criação de catálogos adicionais:

| Ambiente        | Catalog | Descrição                                                                        |
| --------------- | ------- | ---------------------------------------------------------------------------------- |
| Desenvolvimento | `dev` | Criação de código, testes rápidos e exploração de dados.                     |
| Produção      | `prd` | Ambiente final e oficial. Consumido por relatórios executivos e dashboards de BI. |

---

<br>

## 3. Camadas Medallion Architecture (Schemas)

A evolução, o refino e a qualidade dos dados dentro de cada ambiente são organizados através da Arquitetura Medallion, onde cada camada corresponde a um Esquema (`Schema`) no Unity Catalog:

| Camada | Schema     | Descrição                                                                                                                                                 |
| ------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bronze | `bronze` | Dados Brutos (Raw): Guarda o histórico completo dos dados da forma exata como vieram da origem, sem filtros ou transformações.                           |
| Silver | `silver` | Dados Higienizados (Single Source of Truth): Dados limpos, com tipos de dados corrigidos, desduplicados, enriquecidos e prontos para uso geral na empresa.  |
| Gold   | `gold`   | Dados de Negócio (Analytics Ready): Modelagem dimensional (Fatos e Dimensões) e agregações focadas em performance para BI, IA e relatórios executivos. |

---

<br>

## 4. Nomenclatura de Tabelas

As tabelas representam o terceiro nível do namespace do Unity Catalog. A sua nomenclatura varia de acordo com a camada da Arquitetura Medallion:

### Formato

```
<catalog>.<schema>.<origem>_<nome_original_tabela>  (Bronze e Silver)
<catalog>.<schema>.<fct_ ou dim_><nome_negocio>     (Gold)
```

### Regras

| Componente                 | Descrição                                                                                                         |
| :------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| `<catalog>`              | Ambiente (`dev` ou `prd`).                                                                                      |
| `<schema>`               | Camada (`bronze`, `silver` ou `gold`).                                                                        |
| `<origem>`               | Abreviação do sistema de origem do dado. No projeto atual:`sql` (banco transacional SQL Server da LH Nautical). |
| `<nome_original_tabela>` | Nome da tabela na origem, convertido para`snake_case` e minúsculas.                                              |

### Tabela de Origens Homologadas (`<origem>`)

| Prefixo | Sistema de Origem                            | Status                                                      |
| :------ | :------------------------------------------- | :---------------------------------------------------------- |
| `sql` | Banco SQL Server transacional da LH Nautical | ✅ Ativo — fonte atual do projeto                          |
| `rag` | Fontes externas para o RAG                   | 🔜 Reservado — a confirmar nas próximas etapas do projeto |

> Novas origens devem ser adicionadas a esta tabela antes de serem usadas no código, seguindo o fluxo de governança.

### Exemplos no Ambiente de Produção

| Camada | Tabela Original (Fonte)                    | Nome Final no Databricks       |
| :----- | :----------------------------------------- | :----------------------------- |
| Bronze | `orders`                                 | `prd.bronze.sql_orders`      |
| Bronze | `order_items`                            | `prd.bronze.sql_order_items` |
| Bronze | `customers`                              | `prd.bronze.sql_customers`   |
| Silver | `orders` (tratado)                       | `prd.silver.sql_orders`      |
| Gold   | `sql_orders` + `sql_order_items` + ... | `prd.gold.fct_vendas`       |
| Gold   | `sql_customers`                          | `prd.gold.dim_cliente`       |

---

<br>

## 5. Otimização e Organização de Dados (Liquid Clustering)

Para garantir alta performance de leitura e escrita e evitar a fragmentação de arquivos (problema de _small files_), adotamos as diretrizes modernas de otimização do Delta Lake.

### Campo de Controle de Carga

Todas as tabelas na camada **Bronze** e **Silver** devem conter obrigatoriamente o campo de controle de auditoria abaixo:

| Campo              | Tipo     | Formato        | Descrição                                                 |
| :----------------- | :------- | :------------- | :---------------------------------------------------------- |
| `ingestion_date` | `DATE` | `YYYY-MM-DD` | Data em que o dado foi processado e carregado no Lakehouse. |

### Regra de Otimização

Considerando o volume total do projeto (~293.000 linhas nas 13 tabelas em escopo — muito abaixo de 1TB), **não utilizamos particionamento físico tradicional por pastas** (`PARTITIONED BY`) em nenhuma tabela. Em vez disso:

1. **Padrão para o projeto:** O Databricks gerencia os arquivos automaticamente através do recurso nativo de auto-otimização, não é necessário nenhuma configuração adicional para as tabelas do escopo atual.
2. **Caso o volume cresça significativamente** (acima de 1TB ou alto volume diário, conforme discutido na documentação de escalabilidade): aplicar **Liquid Clustering** baseado na coluna `ingestion_date` através do comando `CLUSTER BY (ingestion_date)`.

<br>

> 💡 **Nota Técnica:** O `ingestion_date` é gravado em todas as tabelas Bronze/Silver desde já, mesmo sem `CLUSTER BY` ativo, para que a migração para Liquid Clustering, se necessária, não exija reprocessamento histórico.

🔗 Para mais detalhes, consulte a [Documentação Oficial do Databricks - Liquid Clustering](https://docs.databricks.com/aws/en/delta/clustering).

<br>

## 6. Jobs e Clusters — `databricks.yml`

Com a adoção do **Databricks Asset Bundles (DABs)**, a infraestrutura de agendamento, orquestração e computação é tratada como código (IaC). Para evitar conflitos de deploy e garantir a portabilidade do projeto, a nomenclatura de Jobs e Clusters é dividida entre o identificador lógico no código e o nome visual injetado dinamicamente por ambiente.

### 6.1 Jobs

#### Identificador do Recurso (No Código YAML)

É a chave única utilizada internamente dentro dos arquivos de configuração para mapear o recurso do Job. Deve ser escrita estritamente em **caixa baixa** e **snake_case**, sem prefixos manuais de ambiente.

- **Formato:** `lh_nautical_<camada>_<tipo>`

| Componente      | Descrição                                                                                            |
| :-------------- | :----------------------------------------------------------------------------------------------------- |
| `lh_nautical` | Prefixo fixo: identifica o projeto/empresa.                                                            |
| `<camada>`    | Camada de dados:`bronze`, `silver`, `gold` ou `all` (caso o Job passe por mais de uma camada). |
| `<tipo>`      | Tipo de operação (ver tabela abaixo).                                                                |

#### Tipos de Operação Homologados (`<tipo>`)

| Tipo               | Descrição                                                           | Exemplo de ID no YAML                 |
| :----------------- | :-------------------------------------------------------------------- | :------------------------------------ |
| `ingestion`      | Carga de dados da origem para a camada Bronze.                        | `lh_nautical_bronze_ingestion`      |
| `transformation` | Processamento, limpeza e modelagem de dados.                          | `lh_nautical_silver_transformation` |
| `export`         | Envio de dados tratados para sistemas externos (Ex: CRM, APIs, Apps). | `lh_nautical_gold_export`           |
| `maintenance`    | Rotinas de infraestrutura e limpeza (Ex:`VACUUM`, `OPTIMIZE`).    | `lh_nautical_all_maintenance`       |
| `quality`        | Validação de regras de negócio e testes de qualidade de dados.     | `lh_nautical_silver_quality`        |
| `inference`      | Execução e scoring de modelos de Machine Learning / IA.             | `lh_nautical_gold_inference`        |

#### Nome de Exibição do Job (Na Interface Web)

Para isolar visualmente os Jobs nos workspaces, o nome visível na UI do Databricks deve obrigatoriamente injetar a variável de ambiente do Bundle.

- **Formato de Configuração:** `${bundle.environment}_lh_nautical_<camada>_<tipo>`
- **Exemplo de renderização final em Produção:** `prd_lh_nautical_bronze_ingestion`

---

### 6.2 Clusters

Os nomes de clusters utilizam hífens em vez de underscores, seguindo a convenção padrão de infraestrutura de nuvem (`kebab-case`).

Tal como nos Jobs, a configuração do cluster no Bundle deve ser parametrizada dinamicamente para herdar o ambiente ativo do deployment.

- **Formato de Configuração:** `lh-nautical-cluster-${bundle.environment}`

| Componente                | Descrição                                                          |
| :------------------------ | :------------------------------------------------------------------- |
| `lh-nautical`           | Prefixo fixo: identifica a empresa/projeto.                          |
| `cluster`               | Palavra fixa identificadora do tipo de recurso.                      |
| `${bundle.environment}` | Variável nativa que assume o ambiente de deploy:`dev` ou `prd`. |

#### Como o nome será renderizado na interface após o Deploy:

- **Desenvolvimento:** `lh-nautical-cluster-dev`
- **Produção:** `lh-nautical-cluster-prd`

---

<br>

### 6.3 Exemplo Prático de Configuração no `databricks.yml`

Para referência do time de engenharia, abaixo está o padrão correto de declaração de um Job e de um Cluster utilizando as diretrizes de Bundles:

```yaml
bundle:
  name: lh-nautical

# ── Ambientes de deploy ───────────────────────────────────────────────────────
targets:
  dev:
    mode: development   
    default: true     
    resources:
      jobs:
        lh_nautical_bronze_ingestion:
          schedule:
            pause_status: PAUSED   # dev nunca roda automaticamente
          tasks:
            - task_key: run_ingestion
              spark_python_task:
                python_file: ./src/ingestion/ingest_bronze.py
                parameters:
                  - "--catalog"
                  - "dev"        

  prd:
    mode: production  
    workspace:
      root_path: /Workspace/Users/renan_kramer@hotmail.com/.bundle/${bundle.name}/${bundle.target}
    resources:
      jobs:
        lh_nautical_bronze_ingestion:
          schedule:
            pause_status: UNPAUSED   
          tasks:
            - task_key: run_ingestion
              spark_python_task:
                python_file: ./src/ingestion/ingest_bronze.py
                parameters:
                  - "--catalog"
                  - "prd"

# ── Recursos: Jobs ────────────────────────────────────────────────────────────
resources:
  jobs:
    lh_nautical_bronze_ingestion:
      name: "${bundle.environment}_lh_nautical_bronze_ingestion"
      tasks:
        - task_key: run_ingestion
          description: "Extrai as 13 tabelas do SQL Server e grava na camada Bronze"
          environment_key: default
          spark_python_task:
            python_file: ./src/ingestion/ingest_bronze.py
          max_retries: 1
          min_retry_interval_millis: 300000
      environments:
        - environment_key: default
          spec:
            environment_version: "2"

      # Alertas de falha por e-mail
      email_notifications:
        on_failure:
          - renan_kramer@hotmail.com
          - brunasanog.contato@gmail.com
          - erikacatarina98@gmail.com
          - carlaliradev@gmail.com

      # Schedule global (pause_status controlado por target acima)
      schedule:
        quartz_cron_expression: "0 0 6 * * ?"
        timezone_id: "America/Sao_Paulo"
        pause_status: PAUSED
```

<br>

## 7. Inventário de Tabelas (Escopo de Origem)

> 📋 O inventário completo das tabelas do banco transacional, com classificação **Incluir/Excluir** e justificativas, está documentado em [`ANALISE_FONTE_DADOS.md`](./ANALISE_FONTE_DADOS.md) (Task 2.4).
>
> **Resumo:** 13 tabelas incluídas no escopo (origem das 1 fato + 6 dimensões do Star Schema) e 11 tabelas excluídas (cadeia de suprimentos, estoque interno e atributos de catálogo não utilizados nas dores mapeadas).

---

<br>

## 8. Governança, Versionamento e Próximos Passos

> Este documento estabelece as diretrizes fundamentais de arquitetura e nomenclatura para a modernização do nosso Lakehouse no Databricks.

Como o ecossistema de dados é **dinâmico**, qualquer necessidade de desvio ou evolução dos padrões estabelecidos aqui deve seguir o seguinte fluxo:

1. **Alinhamento do Time:** Alinhe a mudança rapidamente com o time (na Daily ou alinhamento técnico).
2. **Atualização do Manual:** Uma vez aprovada pelo time, a mudança deve ser documentada neste arquivo `.md` antes da implementação no código.

---

<br>
