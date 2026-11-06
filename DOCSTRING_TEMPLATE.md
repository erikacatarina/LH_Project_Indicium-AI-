# Template de Docstring — LH Nautical

Padrão: Google Style Docstrings

## Para Funções

```python
def extrair_tabela(nome_tabela: str, jdbc_url: str) -> DataFrame:
    """Extrai uma tabela do banco SQL Server via JDBC.

    Args:
        nome_tabela: Nome da tabela a ser extraída, conforme schema de origem.
        jdbc_url: URL de conexão JDBC, obtida via Databricks Secrets.

    Returns:
        DataFrame Spark contendo os dados extraídos da tabela.

    Raises:
        ConnectionError: Se a conexão com o banco falhar.
    """
```

## Para Módulos (início do arquivo)

```python
"""
Módulo de ingestão Bronze — LH Nautical.

Responsável por extrair as tabelas do banco SQL Server transacional
e gravá-las na camada Bronze do Delta Lake, com idempotência garantida
via overwrite controlado.
"""
```

## Regras

- Toda função pública deve ter docstring
- Args e Returns são obrigatórios quando aplicável
- Raises é obrigatório quando a função pode lançar exceção esperada
- Frases descritivas, em português, terminando com ponto final
