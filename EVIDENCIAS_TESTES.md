# Evidências dos Testes — Camada Bronze

**Projeto:** LH Nautical — Programa LH 2026-05
**Grupo:** Grupo 1
**Data de execução:** 24-06-2026
**Responsável Técnico:** Érika Santa Catarina

---

## Teste 6.1 — Idempotência

**Objetivo:** confirmar que executar o pipeline múltiplas vezes produz o mesmo resultado, sem duplicação de dados.

**Método:** pipeline executado duas vezes consecutivas em dev. Contagens comparadas antes e depois da segunda execução.

**Mecanismo de idempotência:** `mode="overwrite"` na escrita Delta cada execução substitui completamente o conteúdo anterior da tabela.

**Data:** 24-06-2026

**Ambiente:** dev

**Execuções realizadas:** 2

### Resultado

```
=== CONTAGENS DEPOIS DA SEGUNDA EXECUÇÃO ===
Tabela                         Antes     Depois       Resultado
-----------------------------------------------------------------
sql_orders                    50000      50000   ✅ IDEMPOTENTE
sql_order_items              150321     150321   ✅ IDEMPOTENTE
sql_payments                  54635      54635   ✅ IDEMPOTENTE
sql_returns                    1000       1000   ✅ IDEMPOTENTE
sql_return_items               1409       1409   ✅ IDEMPOTENTE
sql_fiscal_invoices           35079      35079   ✅ IDEMPOTENTE
sql_customers                  2000       2000   ✅ IDEMPOTENTE
sql_products                    500        500   ✅ IDEMPOTENTE
sql_product_variants           1009       1009   ✅ IDEMPOTENTE
sql_categories                   14         14   ✅ IDEMPOTENTE
sql_brands                       12         12   ✅ IDEMPOTENTE
sql_locations                     6          6   ✅ IDEMPOTENTE
sql_employees                    15         15   ✅ IDEMPOTENTE

✅ PIPELINE IDEMPOTENTE — todas as contagens são iguais
```

**Conclusão:** Pipeline idempotente confirmado, modo overwrite
garante que múltiplas execuções produzem o mesmo resultado.

## Teste 6.2 — Contagem de Linhas e Tempo de Execução

**Objetivo:** registrar o volume de dados processado e o tempo de execução, validando as decisões de otimização documentadas em `docs/OTIMIZACAO.md`.

**Data:** 24-06-2026
**Ambiente:** dev e prd

```
=== VALIDAÇÃO CRUZADA — Delta vs. Esperado ===
sql_orders                esperado= 50,000 | real= 50,000 | ✅
sql_order_items           esperado=150,321 | real=150,321 | ✅
sql_payments              esperado= 54,635 | real= 54,635 | ✅
sql_returns               esperado=  1,000 | real=  1,000 | ✅
sql_return_items          esperado=  1,409 | real=  1,409 | ✅
sql_fiscal_invoices       esperado= 35,079 | real= 35,079 | ✅
sql_customers             esperado=  2,000 | real=  2,000 | ✅
sql_products              esperado=    500 | real=    500 | ✅
sql_product_variants      esperado=  1,009 | real=  1,009 | ✅
sql_categories            esperado=     14 | real=     14 | ✅
sql_brands                esperado=     12 | real=     12 | ✅
sql_locations             esperado=      6 | real=      6 | ✅
sql_employees             esperado=     15 | real=     15 | ✅
```

**Tempo de execução:**

- dev: ~1 minuto e 12 segundos
- prd: ~1 minuto e 23 segundos

**Conclusão:** volume e tempo adequados para execução diária agendada às 6h. Decisão de full load validada empiricamente, ~293.000 linhas
processadas em menos de 2 minutos, sem necessidade de extração incremental para este volume.

## Teste 6.3 — Tratamento de Erros e Retry

**Objetivo:** validar que o pipeline falha de forma controlada e que o retry automático configurado no `databricks.yml` funciona.

**Data:** 24-06-2026
**Ambiente:** dev

**Cenário testado:** tabela inexistente na lista `TABELAS_INCLUIR`
(`orders_teste_erro` no lugar de `orders`).

**Comportamento observado:**

- Tentativa 1: falhou com `ConnectionError` — tabela não encontrada
- Retry automático: disparado após 5 minutos (configurado no
  `databricks.yml`: `max_retries: 1`,
  `min_retry_interval_millis: 300000`)
- Tentativa 2: falhou novamente (tabela realmente não existe)
- Job encerrado com status `FAILED` — sem loop infinito

**Dados anteriores após a falha:**

| Tabela          | Linhas após falha | Status        |
| --------------- | ------------------ | ------------- |
| sql_order_items | 150.321            | ✅ Preservada |
| sql_customers   | 2.000              | ✅ Preservada |
| sql_orders      | 50.000             | ✅ Preservada |

**Conclusão:** pipeline falha de forma controlada e esperada. O retry automático funcionou conforme configurado. Dados de execuções
anteriores não são afetados por falhas, o `overwrite` só acontece após a extração bem-sucedida de cada tabela individualmente.
