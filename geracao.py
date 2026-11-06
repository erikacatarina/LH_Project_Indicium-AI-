"""Geração de resposta via GPT-OSS-20B, com recuperação e guardrails — LH Nautical.

Uso (a partir da raiz do repositório, com o venv da raiz ativado, ou de um
notebook de demonstração):
    from src.rag.geracao import responder_pergunta
    print(responder_pergunta("Qual produto tem sazonalidade confirmada na loja?"))
"""

import os

from databricks.ai_search.client import AISearchClient
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

from guardrails import detectar_prompt_injection, extrair_texto_resposta, mascarar_dados_sensiveis, moderar_conteudo

load_dotenv()

CATALOGO = os.environ.get("DATABRICKS_CATALOG", "dev")
NOME_ENDPOINT_INDICE = "lh_nautical_rag_endpoint"
NOME_INDICE = f"{CATALOGO}.gold.rag_chunks_index"
MODELO_GERACAO = "databricks-gpt-oss-20b"

MENSAGEM_RECUSA_PADRAO = (
    "Não posso ajudar com essa solicitação. Se a pergunta for sobre o projeto "
    "LH Nautical, tente reformular de forma mais direta."
)

PROMPT_SISTEMA = """Você é um assistente que responde perguntas sobre o projeto de análise de \
dados da LH Nautical (varejo náutico), usando SOMENTE as informações fornecidas no contexto \
abaixo. Nunca invente números, decisões ou informações que não estejam explicitamente no \
contexto. Se a resposta não estiver no contexto, diga claramente que não tem essa informação \
disponível — não tente adivinhar ou complementar com conhecimento geral.

Contexto recuperado:
{contexto}
"""

def _criar_cliente_ai_search() -> AISearchClient:
    """Cria o cliente AISearchClient, cobrindo os 3 contextos reais deste projeto.

    Dentro de um app do Databricks, usa as credenciais do Service Principal do
    próprio app (DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET, injetadas
    automaticamente — nunca há DATABRICKS_TOKEN dentro de um app). Dentro de um
    Job/notebook, usa autodetecção. Localmente, usa PAT do .env.
    """
    if os.environ.get("DATABRICKS_CLIENT_ID") and os.environ.get("DATABRICKS_CLIENT_SECRET"):
        host = os.environ["DATABRICKS_HOST"]
        workspace_url = host if host.startswith("http") else f"https://{host}"
        return AISearchClient(
            workspace_url=workspace_url,
            service_principal_client_id=os.environ["DATABRICKS_CLIENT_ID"],
            service_principal_client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
        )

    try:
        return AISearchClient()
    except Exception:
        host = os.environ["DATABRICKS_HOST"]
        workspace_url = host if host.startswith("http") else f"https://{host}"
        return AISearchClient(
            workspace_url=workspace_url,
            personal_access_token=os.environ["DATABRICKS_TOKEN"],
        )



def recuperar_chunks(pergunta: str, num_resultados: int = 5) -> list[dict]:
    """Busca os chunks mais relevantes para a pergunta, no índice.

    Args:
        pergunta: Pergunta já mascarada e aprovada pelos guardrails de entrada.
        num_resultados: Quantos chunks recuperar.

    Returns:
        Lista de dicts {"documento", "secao", "texto", "score"}.
    """
    client = _criar_cliente_ai_search()
    indice = client.get_index(endpoint_name=NOME_ENDPOINT_INDICE, index_name=NOME_INDICE)

    resultado = indice.similarity_search(
        query_text=pergunta,
        columns=["documento", "secao", "texto"],
        num_results=num_resultados,
    )

    colunas = [c["name"] for c in resultado["manifest"]["columns"]]
    linhas = resultado["result"]["data_array"]
    return [dict(zip(colunas, linha)) for linha in linhas]

import openai


def _chamar_modelo_geracao(pergunta: str, contexto: str, cliente_openai, usar_filtro_nativo: bool) -> str:
    """Chama o GPT-OSS-20B para gerar a resposta, com ou sem o filtro nativo da Databricks.

    Args:
        pergunta: Pergunta já mascarada e aprovada pelos guardrails.
        contexto: Texto concatenado dos chunks recuperados.
        cliente_openai: Cliente OpenAI-compatível já autenticado.
        usar_filtro_nativo: Se True, inclui enable_safety_filter na chamada.

    Returns:
        Texto da resposta gerada pelo modelo.
    """
    extra_body = {"enable_safety_filter": True} if usar_filtro_nativo else {}
    resposta = cliente_openai.chat.completions.create(
        model=MODELO_GERACAO,
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA.format(contexto=contexto)},
            {"role": "user", "content": pergunta},
        ],
        max_tokens=600,
        extra_body=extra_body,
    )
    return extrair_texto_resposta(resposta.choices[0].message)


def gerar_resposta(pergunta: str, chunks: list[dict], cliente_openai) -> str | None:
    """Gera a resposta final, ancorada exclusivamente nos chunks recuperados.

    Se o filtro nativo (enable_safety_filter) bloquear a chamada, pede uma
    segunda opinião à moderação manual sobre o contexto recuperado antes de
    recusar de vez — evita que um falso positivo do classificador nativo
    bloqueie perguntas de negócio legítimas (Opção B, decisão do time).

    Args:
        pergunta: Pergunta já mascarada e aprovada pelos guardrails de entrada.
        chunks: Saída de recuperar_chunks.
        cliente_openai: Cliente OpenAI-compatível já autenticado.

    Returns:
        Texto da resposta, ou None se a moderação manual também considerar
        o conteúdo inseguro — recusa real, não um crash.
    """
    contexto = "\n\n---\n\n".join(f"[{c['documento']} > {c['secao']}]\n{c['texto']}" for c in chunks)

    try:
        return _chamar_modelo_geracao(pergunta, contexto, cliente_openai, usar_filtro_nativo=True)
    except openai.BadRequestError:
        pass  # filtro nativo bloqueou — segue para a segunda opinião abaixo

    seguro_contexto, motivo_contexto = moderar_conteudo(contexto, cliente_openai)
    if not seguro_contexto:
        return None

    try:
        return _chamar_modelo_geracao(pergunta, contexto, cliente_openai, usar_filtro_nativo=False)
    except openai.BadRequestError:
        return None

def responder_pergunta(pergunta_bruta: str) -> str:
    """Funil completo: guardrails de entrada → recuperação → geração → guardrails de saída.

    Args:
        pergunta_bruta: Pergunta exatamente como digitada pelo usuário.

    Returns:
        Resposta final, ou uma mensagem de recusa, dependendo do resultado
        de cada etapa do funil.
    """
    workspace_client = WorkspaceClient()
    cliente_openai = workspace_client.serving_endpoints.get_open_ai_client()

    pergunta = mascarar_dados_sensiveis(pergunta_bruta)

    if detectar_prompt_injection(pergunta):
        return MENSAGEM_RECUSA_PADRAO

    seguro_entrada, motivo_entrada = moderar_conteudo(pergunta, cliente_openai)
    if not seguro_entrada:
        return MENSAGEM_RECUSA_PADRAO

    chunks = recuperar_chunks(pergunta)
    if not chunks:
        return "Não encontrei informação relevante sobre isso no material do projeto."

    resposta = gerar_resposta(pergunta, chunks, cliente_openai)
    if resposta is None:
        # Bloqueado pelo filtro nativo, e a segunda opinião manual confirmou
        # inseguro (Opção B) — recusa real, não um crash.
        return MENSAGEM_RECUSA_PADRAO

    seguro_saida, motivo_saida = moderar_conteudo(resposta, cliente_openai)
    if not seguro_saida:
        return MENSAGEM_RECUSA_PADRAO

    return resposta