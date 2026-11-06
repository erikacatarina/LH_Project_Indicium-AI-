"""Interface Streamlit para o RAG — LH Nautical.

Reaproveita responder_pergunta() sem duplicar a lógica de negócio —
guardrails.py e geracao.py são cópias de src/rag/, mantidas dentro desta
pasta porque o Databricks Apps não permite acessar arquivos fora de
source_code_path (ver nota no início deste guia).
"""

import streamlit as st

from geracao import responder_pergunta

st.set_page_config(page_title="LH Nautical — Assistente de Análise", page_icon="⚓")
st.title("⚓ LH Nautical — Assistente de Análise")
st.caption(
    "Pergunte sobre o forecast de demanda, sazonalidade, modelos de regressão, "
    "crescimento por local, ou necessidade de novos centros de distribuição."
)

if "historico" not in st.session_state:
    st.session_state.historico = []

for pergunta, resposta in st.session_state.historico:
    with st.chat_message("user"):
        st.write(pergunta)
    with st.chat_message("assistant"):
        st.write(resposta)

pergunta_usuario = st.chat_input("Digite sua pergunta...")

if pergunta_usuario:
    with st.chat_message("user"):
        st.write(pergunta_usuario)

    with st.chat_message("assistant"):
        with st.spinner("Consultando o material do projeto..."):
            resposta = responder_pergunta(pergunta_usuario)
        st.write(resposta)

    st.session_state.historico.append((pergunta_usuario, resposta))