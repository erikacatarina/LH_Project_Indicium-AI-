"""Avaliação formal do RAG — LH Nautical.

Conjunto de perguntas-gabarito + LLM-as-judge automático + checagem de
recuperação. Script customizado, não Agent Bricks,
decisão justificada pelo risco de API nova sem tempo de validação, dado o
histórico de bugs reais já enfrentados neste projeto.

Uso (a partir da raiz do repositório, com o venv da raiz ativado):
    python -m src.rag.avaliacao
"""

import json

import pandas as pd
from databricks.sdk import WorkspaceClient

from src.rag.geracao import recuperar_chunks, responder_pergunta
from src.rag.guardrails import extrair_texto_resposta
from src.rag.perguntas_gabarito import PERGUNTAS_GABARITO

MODELO_JUIZ = "databricks-gpt-oss-20b"

PROMPT_AVALIACAO_CORRECAO = """Você é um avaliador de qualidade de respostas de um sistema de perguntas e respostas. \
Compare a resposta gerada com a resposta de referência (gabarito) e responda EXCLUSIVAMENTE em JSON, no formato:
{{"correta": true ou false, "justificativa": "explicação breve"}}

A resposta gerada deve ser considerada correta se capturar a informação essencial da referência, mesmo com \
palavras diferentes ou detalhes extras, não precisa ser idêntica. Se a resposta de referência indicar que o \
sistema deveria admitir não saber (ex.: pergunta fora do escopo do corpus), considere correta uma resposta que \
também admita não saber, mesmo sem citar a referência literalmente.

Pergunta: {pergunta}
Resposta de referência (gabarito): {resposta_esperada}
Resposta gerada pelo sistema: {resposta_gerada}
"""

def checar_recuperacao(pergunta: str, documento_esperado: str, num_resultados: int = 5) -> bool:
    """Verifica se algum chunk do documento esperado apareceu entre os recuperados.

    Args:
        pergunta: Pergunta do conjunto-gabarito.
        documento_esperado: Nome do documento onde a resposta deveria estar.
        num_resultados: Quantos chunks considerar (mesmo top-k usado em produção).

    Returns:
        True se pelo menos um chunk do documento esperado apareceu no top-k.
    """
    chunks = recuperar_chunks(pergunta, num_resultados=num_resultados)
    return any(c["documento"] == documento_esperado for c in chunks)


def avaliar_resposta(pergunta: str, resposta_esperada: str, resposta_gerada: str, cliente_openai) -> tuple[bool, str]:
    """Julga se a resposta gerada está correta, comparando com o gabarito.

    Returns:
        Tupla (correta: bool, justificativa: str). Em caso de falha ao
        interpretar a resposta do juiz, retorna (False, "erro de avaliação"),
        não conta como acerto por padrão, para não inflar a métrica.
    """
    resposta = cliente_openai.chat.completions.create(
        model=MODELO_JUIZ,
        messages=[{
            "role": "user",
            "content": PROMPT_AVALIACAO_CORRECAO.format(
                pergunta=pergunta, resposta_esperada=resposta_esperada, resposta_gerada=resposta_gerada
            ),
        }],
        max_tokens=200,
        extra_body={"enable_safety_filter": True},
    )

    try:
        conteudo = extrair_texto_resposta(resposta.choices[0].message)
        resultado = json.loads(conteudo)
        return bool(resultado.get("correta", False)), resultado.get("justificativa", "")
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError):
        return False, "erro de avaliação, resposta do juiz não pôde ser interpretada"


def main():
    """Roda a avaliação completa e escreve o relatório em docs/rag_corpus/avaliacao_rag.md."""
    workspace_client = WorkspaceClient()
    cliente_openai = workspace_client.serving_endpoints.get_open_ai_client()

    resultados = []
    for item in PERGUNTAS_GABARITO:
        recuperacao_ok = checar_recuperacao(item["pergunta"], item["documento_esperado"])
        resposta_gerada = responder_pergunta(item["pergunta"])
        correta, justificativa = avaliar_resposta(
            item["pergunta"], item["resposta_esperada"], resposta_gerada, cliente_openai
        )

        resultados.append({
            "pergunta": item["pergunta"],
            "documento_esperado": item["documento_esperado"],
            "recuperacao_ok": recuperacao_ok,
            "resposta_gerada": resposta_gerada,
            "correta": correta,
            "justificativa": justificativa,
        })
        print(f"[{'OK' if correta else 'FALHOU'}] recuperação={recuperacao_ok} — {item['pergunta'][:60]}...")

    df = pd.DataFrame(resultados)

    taxa_recuperacao = df["recuperacao_ok"].mean() * 100
    taxa_correcao = df["correta"].mean() * 100

    linhas_relatorio = [
        "# Relatório de Avaliação do RAG — LH Nautical",
        "",
        f"**Total de perguntas avaliadas:** {len(df)}",
        f"**Taxa de recuperação correta (chunk esperado no top-5):** {taxa_recuperacao:.1f}%",
        f"**Taxa de resposta correta (LLM-as-judge):** {taxa_correcao:.1f}%",
        "",
        "## Detalhe por pergunta",
        "",
    ]

    for _, linha in df.iterrows():
        status_recuperacao = "✅" if linha["recuperacao_ok"] else "❌"
        status_correcao = "✅" if linha["correta"] else "❌"
        linhas_relatorio.append(f"### {linha['pergunta']}")
        linhas_relatorio.append(f"- Recuperação ({linha['documento_esperado']}): {status_recuperacao}")
        linhas_relatorio.append(f"- Correção: {status_correcao} — {linha['justificativa']}")
        linhas_relatorio.append(f"- Resposta gerada: {linha['resposta_gerada'][:300]}")
        linhas_relatorio.append("")

    with open("docs/rag_corpus/avaliacao_rag.md", "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas_relatorio))

    print(f"\nRelatório gerado: docs/rag_corpus/avaliacao_rag.md")
    print(f"Taxa de recuperação: {taxa_recuperacao:.1f}% | Taxa de correção: {taxa_correcao:.1f}%")


if __name__ == "__main__":
    main()