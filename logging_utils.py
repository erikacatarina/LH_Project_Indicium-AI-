"""Módulo de logging e tratamento de erros — LH Nautical.

Fornece funções padronizadas de log e handlers de erro para
uso no pipeline de ingestão Bronze.
"""
import logging
import sys


def configurar_logger(nome: str = "lh_nautical_ingestion") -> logging.Logger:
    """Configura e retorna um logger padronizado para o pipeline.

    Args:
        nome: Nome identificador do logger. Padrão: lh_nautical_ingestion.

    Returns:
        Logger configurado com formato padronizado e saída no console.
    """
    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formato = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formato)
        logger.addHandler(handler)

    return logger


def tratar_erro_conexao(logger: logging.Logger, tabela: str, erro: Exception) -> None:
    """Registra e trata erro de conexão com o banco de dados.

    Args:
        logger: Logger configurado para registro do erro.
        tabela: Nome da tabela que estava sendo processada quando o erro ocorreu.
        erro: Exceção capturada durante a tentativa de conexão.

    Raises:
        ConnectionError: Relança o erro original com contexto adicional.
    """
    logger.error(f"Falha de conexão ao processar a tabela '{tabela}': {erro}")
    raise ConnectionError(f"Erro de conexao na tabela {tabela}") from erro


def tratar_erro_schema(logger: logging.Logger, tabela: str, erro: Exception) -> None:
    """Registra e trata erro de incompatibilidade de schema.

    Args:
        logger: Logger configurado para registro do erro.
        tabela: Nome da tabela com schema incompatível.
        erro: Exceção capturada durante a validação ou escrita do schema.

    Raises:
        ValueError: Relança o erro original com contexto adicional.
    """
    logger.error(f"Schema incompativel na tabela '{tabela}': {erro}")
    raise ValueError(f"Erro de schema na tabela {tabela}") from erro


def tratar_erro_timeout(logger: logging.Logger, tabela: str, erro: Exception) -> None:
    """Registra e trata erro de timeout durante a extração.

    Args:
        logger: Logger configurado para registro do erro.
        tabela: Nome da tabela em que o timeout ocorreu.
        erro: Exceção capturada durante a operação que excedeu o tempo limite.

    Raises:
        TimeoutError: Relança o erro original com contexto adicional.
    """
    logger.error(f"Timeout ao processar a tabela '{tabela}': {erro}")
    raise TimeoutError(f"Timeout na tabela {tabela}") from erro
