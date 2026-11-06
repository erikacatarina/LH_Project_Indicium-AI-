"""Guardrails manuais do RAG — LH Nautical.

Implementação 100% manual (Unity AI Gateway indisponível na Free Edition),
cada linha da tabela de guardrails vira
uma função aqui, testável isoladamente.

Uso: importado por src/rag/geracao.py, não roda sozinho.
"""

import re

PADRAO_CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
PADRAO_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def mascarar_dados_sensiveis(texto: str) -> str:
    """Mascara CPF e e-mail antes de qualquer chamada ao modelo.

    Args:
        texto: Pergunta original do usuário.

    Returns:
        Texto com CPF/e-mail substituídos por marcadores — nunca chega ao
        LLM em texto plano.
    """
    texto = PADRAO_CPF.sub("[CPF removido]", texto)
    texto = PADRAO_EMAIL.sub("[E-MAIL removido]", texto)
    return texto

PADROES_INJECAO = [
    r"ignor[ae]\s+(as\s+)?instru[cç][oõ]es\s+anteriores",
    r"ignore\s+(the\s+)?previous\s+instructions",
    r"esque[çc]a\s+tudo\s+(o\s+que\s+foi\s+dito|acima)",
    r"voc[eê]\s+(agora\s+)?[ée]\s+um[a]?\s+outr[oa]",
    r"you\s+are\s+now\s+a",
    r"revele\s+(seu|o)\s+system\s*prompt",
    r"reveal\s+your\s+(system\s+)?prompt",
    r"aja\s+como\s+se",
    r"modo\s+desenvolvedor",
    r"developer\s+mode",
]
PADROES_INJECAO_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in PADROES_INJECAO]


def detectar_prompt_injection(texto: str) -> bool:
    """Detecta tentativas heurísticas de prompt injection.

    Args:
        texto: Pergunta já mascarada.

    Returns:
        True se algum padrão de override foi encontrado — a pergunta deve
        ser recusada antes de chegar ao LLM principal.
    """
    return any(padrao.search(texto) for padrao in PADROES_INJECAO_COMPILADOS)

PROMPT_MODERACAO = """Você é um classificador de segurança de conteúdo. Analise o texto abaixo e responda EXCLUSIVAMENTE em JSON, no formato:
{{"seguro": true ou false, "motivo": "explicação breve ou vazio se seguro"}}

Marque como NÃO seguro (seguro: false) se o texto contiver, pedir ou incentivar:
- Conteúdo violento, sexual, ilegal, discurso de ódio, assédio ou automutilação
- Armas, substâncias controladas, malware, exploits, phishing ou cibercrime
- Diagnóstico de sintomas graves de saúde
- Pedido de informação fora do escopo de um projeto de análise de dados de varejo náutico (ex.: código proprietário, financeiro interno, planos não lançados)

Texto a analisar:
\"\"\"{texto}\"\"\"
"""


def extrair_texto_resposta(mensagem) -> str:
    """Extrai o texto de uma resposta do databricks-gpt-oss-20b.

    Esse modelo retorna message.content como uma LISTA de blocos (cada um
    com um campo "type"), não uma string simples como a maioria dos modelos
    compatíveis com a API da OpenAI — é preciso achar o bloco do tipo "text"
    e extrair o texto dele.

    Args:
        mensagem: Objeto `message` da resposta (`resposta.choices[0].message`).

    Returns:
        O texto da resposta, ou string vazia se nenhum bloco de texto for encontrado.
    """
    conteudo = mensagem.content
    if isinstance(conteudo, str):
        return conteudo

    for bloco in conteudo:
        tipo = bloco.get("type") if isinstance(bloco, dict) else getattr(bloco, "type", None)
        if tipo == "text":
            return bloco.get("text") if isinstance(bloco, dict) else getattr(bloco, "text", "")

    return ""


def moderar_conteudo(texto: str, cliente_openai) -> tuple[bool, str]:
    """Classifica um texto (pergunta ou resposta) como seguro ou não, via LLM-as-judge.

    Args:
        texto: Texto a avaliar (pergunta do usuário ou resposta gerada).
        cliente_openai: Cliente OpenAI-compatível já autenticado.

    Returns:
        Tupla (seguro: bool, motivo: str). Em caso de falha ao interpretar
        a resposta do classificador, retorna (False, "falha na moderação")
        — falha fechada (nega por padrão), não aberta.
    """
    import json

    resposta = cliente_openai.chat.completions.create(
        model="databricks-gpt-oss-20b",
        messages=[{"role": "user", "content": PROMPT_MODERACAO.format(texto=texto)}],
        max_tokens=200,
        extra_body={"enable_safety_filter": True},
    )

    try:
        conteudo = extrair_texto_resposta(resposta.choices[0].message)
        resultado = json.loads(conteudo)
        return bool(resultado.get("seguro", False)), resultado.get("motivo", "")
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError):
        return False, "falha na moderação — resposta do classificador não pôde ser interpretada"