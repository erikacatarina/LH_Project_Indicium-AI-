"""Pipeline de chunking estrutural do corpus do RAG — LH Nautical.

Extrai seções por header (Heading 1/2/3 em .docx; #/##/### em .md) de todos
os documentos do corpus, e fatia cada seção em chunks de ~300-500 tokens, com overlap
de 10-15%, sem corte fixo por token. Reindexação full a cada execução.

Executado como task Python serverless de um Databricks Job.
"""

import inspect
import re
import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Descobre a raiz do bundle subindo os frames até achar o caminho deste arquivo."""
    frame = inspect.currentframe()
    while frame:
        caminho = frame.f_locals.get("filename")
        if caminho and Path(caminho).name == "chunking.py":
            return Path(caminho).resolve().parents[2]
        frame = frame.f_back
    raise RuntimeError("Não foi possível localizar a raiz do bundle automaticamente.")


sys.path.append(str(_bundle_root()))

import argparse

import pandas as pd
from docx import Document as DocumentoDocx

CATALOGO_PLACEHOLDER = None  # definido em main() a partir do argumento --catalog

# Aproximação, não o tokenizer real do Qwen3-Embedding.
PALAVRAS_POR_TOKEN = 0.75
ALVO_TOKENS = 400
OVERLAP_PCT = 0.125
MIN_TOKENS = 150  # piso mínimo — seções abaixo disso são fundidas com a seguinte

CORPUS = [
    {"caminho": "docs/rag_corpus/Planejamento.docx", "tipo": "docx", "checkpoint": "CP5"},
    {"caminho": "docs/MODEL_CARD.md", "tipo": "md", "checkpoint": "CP5"},
    {"caminho": "docs/rag_corpus/resumo_previsoes.md", "tipo": "md", "checkpoint": "CP5"},
]

def contar_tokens_aproximado(texto: str) -> int:
    """Aproxima a contagem de tokens a partir da contagem de palavras (heurística, não exata)."""
    return int(len(texto.split()) / PALAVRAS_POR_TOKEN)


def extrair_secoes_docx(caminho: Path, nome_documento: str) -> list[dict]:
    """Extrai seções (por Heading 1/2/3) de um arquivo .docx.

    Args:
        caminho: Caminho absoluto do arquivo .docx.
        nome_documento: Nome legível do documento, para o metadado do chunk.

    Returns:
        Lista de dicts {"documento", "secao", "caminho_lista", "nivel", "texto"},
        um por seção. "caminho_lista" guarda a hierarquia de headers como lista
        (não só a string já concatenada em "secao"), usada para checar parentesco
        na fusão de seções pequenas (_fundir_secoes_pequenas).
    """
    documento = DocumentoDocx(str(caminho))
    secoes = []
    secao_atual = None
    caminho_headers: list[str] = []

    for paragrafo in documento.paragraphs:
        estilo = paragrafo.style.name if paragrafo.style else ""
        texto = paragrafo.text.strip()
        if not texto:
            continue

        if estilo.startswith("Heading"):
            nivel = int(estilo.replace("Heading ", "")) if estilo[-1].isdigit() else 1
            if secao_atual is not None:
                secoes.append(secao_atual)
            caminho_headers = caminho_headers[: nivel - 1] + [texto]
            secao_atual = {
                "documento": nome_documento,
                "secao": " > ".join(caminho_headers),
                "caminho_lista": list(caminho_headers),
                "nivel": nivel,
                "texto": "",
            }
        elif secao_atual is not None:
            secao_atual["texto"] += texto + "\n"

    if secao_atual is not None:
        secoes.append(secao_atual)

    return secoes

def extrair_secoes_markdown(caminho: Path, nome_documento: str) -> list[dict]:
    """Extrai seções (por #, ## ou ###) de um arquivo Markdown.

    Returns:
        Lista de dicts {"documento", "secao", "caminho_lista", "nivel", "texto"} —
        mesma estrutura de extrair_secoes_docx, "caminho_lista" incluído pelo
        mesmo motivo (checar parentesco na fusão de seções pequenas).
    """
    with open(caminho, encoding="utf-8") as arquivo:
        linhas = arquivo.readlines()

    secoes = []
    secao_atual = None
    caminho_headers: list[str] = []

    for linha in linhas:
        casamento = re.match(r"^(#{1,3})\s+(.*)", linha)
        if casamento:
            nivel = len(casamento.group(1))
            titulo = casamento.group(2).strip()
            if secao_atual is not None:
                secoes.append(secao_atual)
            caminho_headers = caminho_headers[: nivel - 1] + [titulo]
            secao_atual = {
                "documento": nome_documento,
                "secao": " > ".join(caminho_headers),
                "caminho_lista": list(caminho_headers),
                "nivel": nivel,
                "texto": "",
            }
        elif secao_atual is not None and linha.strip():
            secao_atual["texto"] += linha

    if secao_atual is not None:
        secoes.append(secao_atual)

    return secoes

def _remover_secoes_vazias(secoes: list[dict]) -> list[dict]:
    """Remove seções sem texto próprio — headers que só agrupam subseções, sem
    conteúdo direto, não geram chunk (chunk vazio não tem valor de recuperação)."""
    return [secao for secao in secoes if secao["texto"].strip()]


def _fundir_secoes_pequenas(secoes: list[dict], min_tokens: int = MIN_TOKENS) -> list[dict]:
    """Funde seções consecutivas do mesmo documento e do mesmo header-pai cujo texto
    fica abaixo do piso mínimo de tokens, com a seção seguinte — evita chunks
    pequenos demais para carregar contexto útil de recuperação, sem nunca misturar
    seções de ramos diferentes da hierarquia (checagem por "caminho_lista[:-1]").

    Args:
        secoes: Lista de seções já sem as vazias, na ordem original do documento.
        min_tokens: Piso mínimo de tokens aproximados por chunk.

    Returns:
        Lista de seções, algumas possivelmente fundidas — o metadado "secao" de uma
        seção fundida concatena os caminhos das seções originais (" + "), preservando
        rastreabilidade de onde cada trecho do texto veio.
    """
    if not secoes:
        return secoes

    fundidas = []
    buffer = secoes[0].copy()

    for proxima in secoes[1:]:
        mesmo_pai = buffer["caminho_lista"][:-1] == proxima["caminho_lista"][:-1]
        if mesmo_pai and contar_tokens_aproximado(buffer["texto"]) < min_tokens:
            buffer = {
                "documento": buffer["documento"],
                "secao": f"{buffer['secao']} + {proxima['secao']}",
                "caminho_lista": buffer["caminho_lista"],
                "nivel": buffer["nivel"],
                "texto": buffer["texto"] + "\n\n" + proxima["texto"],
            }
        else:
            fundidas.append(buffer)
            buffer = proxima.copy()

    fundidas.append(buffer)  # última seção/buffer, mesmo que ainda fique abaixo do piso
    return fundidas

def dividir_secao_em_chunks(secao: dict, alvo_tokens: int = ALVO_TOKENS, overlap_pct: float = OVERLAP_PCT) -> list[dict]:
    """Divide o texto de uma seção em chunks de ~alvo_tokens, com overlap entre eles.

    Args:
        secao: Dicionário com "documento", "secao", "nivel", "texto".
        alvo_tokens: Tamanho-alvo de cada chunk, em tokens aproximados.
        overlap_pct: Fração do alvo de tokens a repetir entre chunks consecutivos.

    Returns:
        Lista de chunks — um só, se a seção já couber no alvo (com folga de 25%);
        vários, com overlap, se a seção for maior.
    """
    texto = secao["texto"].strip()
    tokens_totais = contar_tokens_aproximado(texto)

    if tokens_totais <= alvo_tokens * 1.25:
        return [{**secao, "texto": texto, "chunk_indice": 0}]

    paragrafos = [p for p in texto.split("\n") if p.strip()]
    chunks = []
    chunk_atual: list[str] = []
    tokens_chunk_atual = 0
    indice = 0

    for paragrafo in paragrafos:
        tokens_paragrafo = contar_tokens_aproximado(paragrafo)

        if tokens_chunk_atual + tokens_paragrafo > alvo_tokens and chunk_atual:
            chunks.append({**secao, "texto": "\n".join(chunk_atual), "chunk_indice": indice})
            indice += 1

            # Overlap: mantém os últimos parágrafos do chunk anterior no próximo,
            # até cobrir aproximadamente overlap_pct do alvo de tokens.
            tokens_overlap_alvo = alvo_tokens * overlap_pct
            chunk_overlap: list[str] = []
            tokens_acumulados = 0
            for p in reversed(chunk_atual):
                tokens_acumulados += contar_tokens_aproximado(p)
                chunk_overlap.insert(0, p)
                if tokens_acumulados >= tokens_overlap_alvo:
                    break
            chunk_atual = chunk_overlap
            tokens_chunk_atual = tokens_acumulados

        chunk_atual.append(paragrafo)
        tokens_chunk_atual += tokens_paragrafo

    if chunk_atual:
        chunks.append({**secao, "texto": "\n".join(chunk_atual), "chunk_indice": indice})

    return chunks

def main():
    """Extrai, fatia e escreve os chunks de todo o corpus numa tabela Delta."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args()

    raiz = _bundle_root()
    todos_chunks = []

    for info_documento in CORPUS:
        caminho_completo = raiz / info_documento["caminho"]
        nome_documento = caminho_completo.name

        if info_documento["tipo"] == "docx":
            secoes = extrair_secoes_docx(caminho_completo, nome_documento)
        else:
            secoes = extrair_secoes_markdown(caminho_completo, nome_documento)

        # Pipeline de pós-processamento, nesta ordem: remove seções sem texto próprio,
        # depois funde as pequenas com a seguinte (piso mínimo) — só então cada seção
        # (já consolidada) passa pela divisão em chunks (que cuida do teto máximo).
        secoes = _remover_secoes_vazias(secoes)
        secoes = _fundir_secoes_pequenas(secoes)

        for secao in secoes:
            for chunk in dividir_secao_em_chunks(secao):
                chunk["checkpoint"] = info_documento["checkpoint"]
                todos_chunks.append(chunk)

    df_chunks = pd.DataFrame(todos_chunks)
    df_chunks["chunk_id"] = (
        df_chunks["documento"] + "::" + df_chunks["secao"] + "::" + df_chunks["chunk_indice"].astype(str)
    )

    from databricks.sdk.runtime import spark
    spark_df = spark.createDataFrame(
        df_chunks[["chunk_id", "documento", "secao", "checkpoint", "chunk_indice", "texto"]]
    )
    spark_df.write.mode("overwrite").saveAsTable(f"{args.catalog}.gold.rag_chunks")

    print(f"{len(df_chunks)} chunks gerados, de {len(CORPUS)} documentos.")
    print(df_chunks.groupby("documento")["chunk_id"].count().to_string())


if __name__ == "__main__":
    main()