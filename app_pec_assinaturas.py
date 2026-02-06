# app_pec_assinaturas.py
# Requisitos:
#   pip install streamlit pandas openpyxl unidecode
#
# Rodar:
#   streamlit run app_pec_assinaturas.py

import io
import re
import unicodedata
from difflib import get_close_matches
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st


# =========================
# CONFIG
# =========================
META_ASSINATURAS = 171

ASSINANTES_RAW_DEFAULT = """Júlia Zanatta
Adilson Barroso
Alberto Fraga
Alberto Mourão
Alceu Moreira
Alexandre Guimarães
Aluisio Mendes
Altineu Côrtes
André Fernandes
Benes Leocádio
Bia Kicis
Bibo Nunes
Bruno Ganem
Cabo Gilberto Silva
Capitão Alberto Neto
Capitão Alden
Carlos Jordy
Caroline de Toni
Chris Tonietto
Clarissa Tércio
Coronel Assis
Coronel Chrisóstomo
Coronel Telhada
Coronel Ulysses
Covatti Filho
Cristiane Lopes
Daniel Freitas
Dayany Bittencourt
Delegado Bruno Lima
Delegado Caveira
Delegado Éder Mauro
Delegado Fabio Costa
Delegado Palumbo
Delegado Paulo Bilynskyj
Delegado Ramagem
Diego Garcia
Dilceu Sperafico
Domingos Sávio
Dr. Frederico
Dr. Jaziel
Dr. Victor Linhalis
Evair Vieira de Melo
Fausto Jr.
Fred Linhares
General Girão
General Pazuello
Geovania de Sá
Gilson Marques
Gilvan da Federal
Giovani Cherini
Gutemberg Reis
Gustavo Gayer
Ismael
Jorge Goetten
José Medeiros
Junior Lourenço
Junio Amaral
Kim Kataguiri
Lincoln Portela
Luciano Alves
Luisa Canziani
Luiz Lima
Luiz Philippe de Orleans e Bragança
Marcel van Hattem
Marcos Pollon
Mario Frias
Mauricio do Vôlei
Mauricio Marcon
Messias Donato
Nelson Barbudo
Nicoletti
Nikolas Ferreira
Padovani
Pastor Diniz
Pastor Eurico
Paulinho Freire
Pedro Lupion
Pedro Westphalen
Pezenti
Pr. Marco Feliciano
Priscila Costa
Ricardo Guidi
Ricardo Salles
Roberta Roma
Roberto Duarte
Roberto Monteiro Pai
Rodolfo Nogueira
Rosangela Moro
Sargento Fahur
Sargento Gonçalves
Sargento Portugal
Silvia Waiãpi
Sóstenes Cavalcante
Subscritor
Vinicius Gurgel
Wellington Roberto
Zé Trovão
Zucco
"""


# Sinônimos aceitos no Excel (auto-detect)
COLUMN_SYNONYMS: Dict[str, List[str]] = {
    "nome": ["Nome Parlamentar", "Nome", "Parlamentar", "Deputado", "Deputada"],
    "partido": ["Partido", "Sigla Partido", "SiglaPartido", "SG_PARTIDO"],
    "uf": ["UF", "Estado", "Sigla UF", "SG_UF"],
    "anexo": ["Anexo"],
    "gabinete": ["Gabinete"],
    "telefone": ["Telefone", "Fone", "Telefone Gabinete"],
    "email": ["E-mail", "Email", "Correio Eletrônico", "Correio Eletronico", "E mail", "e-mail"],
}


# =========================
# UTIL
# =========================
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_name(s: str) -> str:
    return normalize_text(s)


def parse_names(text: str) -> List[str]:
    out = []
    seen = set()
    for line in (text or "").splitlines():
        n = line.strip()
        if not n:
            continue
        k = normalize_name(n)
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def find_column(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    """Encontra coluna por sinônimos (case/acento-insensitive)."""
    cols = list(df.columns)
    cols_norm = {c: normalize_text(c) for c in cols}
    keys_norm = [normalize_text(k) for k in keys]

    # match exato normalizado
    for c, cn in cols_norm.items():
        if cn in keys_norm:
            return c

    # match por "contém"
    for c, cn in cols_norm.items():
        for kn in keys_norm:
            if kn and kn in cn:
                return c
    return None


def read_excel(uploaded_file) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(uploaded_file.getvalue()), engine="openpyxl")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def safe_str(x) -> str:
    return "" if pd.isna(x) else str(x)


# =========================
# UI (SEM SIDEBAR)
# =========================
st.set_page_config(page_title="PEC — Assinaturas", layout="wide")
st.title("PEC — Painel de Assinaturas (Assinou x Não assinou)")

st.markdown("### 1) Envie o Excel (todos os parlamentares)")
uploaded = st.file_uploader("Arquivo .xlsx", type=["xlsx"])

colA, colB = st.columns([1, 1])
with colA:
    meta = st.number_input("Meta de assinaturas", min_value=1, value=META_ASSINATURAS, step=1)
with colB:
    busca_rapida = st.text_input("🔎 Achar parlamentar (nome, partido, UF, telefone, e-mail)", value="").strip()

st.markdown("### 2) Cole a lista dos ASSINANTES (um nome por linha)")
assinantes_text = st.text_area("", value=ASSINANTES_RAW_DEFAULT, height=220)

st.markdown("### 3) Variantes (opcional, para corrigir grafias/apelidos)")
variantes_text = st.text_area("Se um nome não bater, inclua aqui a grafia como está no Excel (um por linha)", value="", height=120)

st.divider()

if not uploaded:
    st.info("Envie o Excel para o painel rodar.")
    st.stop()

# =========================
# LOAD + DETECT COLS
# =========================
try:
    df_raw = read_excel(uploaded)
except Exception as e:
    st.error(f"Não consegui ler o Excel. Erro: {e}")
    st.stop()

# detectar colunas
col_nome = find_column(df_raw, COLUMN_SYNONYMS["nome"])
col_partido = find_column(df_raw, COLUMN_SYNONYMS["partido"])
col_uf = find_column(df_raw, COLUMN_SYNONYMS["uf"])
col_anexo = find_column(df_raw, COLUMN_SYNONYMS["anexo"])
col_gab = find_column(df_raw, COLUMN_SYNONYMS["gabinete"])
col_tel = find_column(df_raw, COLUMN_SYNONYMS["telefone"])
col_email = find_column(df_raw, COLUMN_SYNONYMS["email"])

# exigir apenas o essencial (nome). O resto é “best effort”
if not col_nome:
    st.error(f"Não achei a coluna de NOME. Colunas encontradas: {list(df_raw.columns)}")
    st.stop()

df = df_raw.copy()
df["_nome_raw"] = df[col_nome].astype(str).str.strip()
df["_nome_key"] = df["_nome_raw"].map(normalize_name)

# Lista assinantes
assinantes = parse_names(assinantes_text)
variantes = parse_names(variantes_text)

assinantes_key: Set[str] = {normalize_name(n) for n in assinantes}
assinantes_key |= {normalize_name(n) for n in variantes}

df["Assinou"] = df["_nome_key"].isin(assinantes_key)

# =========================
# METRICS
# =========================
total = len(df)
assinou_n = int(df["Assinou"].sum())
nao_n = total - assinou_n
faltam = max(int(meta) - assinou_n, 0)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total (Excel)", total)
m2.metric("Assinou", assinou_n)
m3.metric("Não assinou", nao_n)
m4.metric(f"Faltam p/ {int(meta)}", faltam)

# =========================
# FILTROS
# =========================
df_view = df.copy()

# cria uma coluna de “texto pesquisável” pra busca rápida
search_fields = [col_nome]
for c in [col_partido, col_uf, col_tel, col_email, col_gab, col_anexo]:
    if c:
        search_fields.append(c)

df_view["_search"] = df_view[search_fields].astype(str).agg(" | ".join, axis=1)

if busca_rapida:
    df_view = df_view[df_view["_search"].str.contains(busca_rapida, case=False, na=False)]

# filtros UF/Partido se existirem
f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    if col_uf:
        ufs = sorted(df_view[col_uf].dropna().astype(str).unique().tolist())
        uf_sel = st.multiselect("Filtrar UF", options=ufs, default=[])
    else:
        uf_sel = []
        st.caption("UF: (coluna não encontrada)")

with f2:
    if col_partido:
        parts = sorted(df_view[col_partido].dropna().astype(str).unique().tolist())
        part_sel = st.multiselect("Filtrar Partido", options=parts, default=[])
    else:
        part_sel = []
        st.caption("Partido: (coluna não encontrada)")

with f3:
    only_nao = st.checkbox("Mostrar só NÃO assinou", value=False)

if uf_sel and col_uf:
    df_view = df_view[df_view[col_uf].astype(str).isin(uf_sel)]
if part_sel and col_partido:
    df_view = df_view[df_view[col_partido].astype(str).isin(part_sel)]
if only_nao:
    df_view = df_view[~df_view["Assinou"]]

# =========================
# TABELAS
# =========================
cols_show = ["Assinou", col_nome]
for c in [col_partido, col_uf, col_anexo, col_gab, col_tel, col_email]:
    if c and c not in cols_show:
        cols_show.append(c)

df_assinou = df_view[df_view["Assinou"]].copy()
df_nao = df_view[~df_view["Assinou"]].copy()

# =========================
# DIAGNÓSTICOS (achar)
# =========================
excel_keys = set(df["_nome_key"].dropna().unique().tolist())
assinantes_nao_encontrados = [n for n in assinantes if normalize_name(n) not in excel_keys]

# sugestões de match (para apelidos/grafias)
# pega top 5 sugestões por nome não encontrado
nome_excel_lista = df["_nome_raw"].dropna().astype(str).tolist()

sugestoes = []
for n in assinantes_nao_encontrados[:200]:
    cand = get_close_matches(n, nome_excel_lista, n=5, cutoff=0.60)
    sugestoes.append({"Assinante (lista)": n, "Sugestões (Excel)": " | ".join(cand)})

df_sug = pd.DataFrame(sugestoes)

# =========================
# ABAS
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["✅ Assinou", "❌ Não assinou", "🧪 Não encontrados", "💡 Sugestões de match"])

with tab1:
    st.subheader(f"✅ Assinou ({len(df_assinou)})")
    st.dataframe(df_assinou[cols_show], use_container_width=True, height=520)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Baixar CSV (assinou)", to_csv_bytes(df_assinou[cols_show]), "pec_assinou.csv", "text/csv")
    with c2:
        # contatos, se existirem
        contato_cols = [col_nome]
        for c in [col_partido, col_uf, col_tel, col_email]:
            if c:
                contato_cols.append(c)
        st.download_button("Baixar CSV (assinou - contatos)", to_csv_bytes(df_assinou[contato_cols]), "pec_assinou_contatos.csv", "text/csv")

with tab2:
    st.subheader(f"❌ Não assinou ({len(df_nao)})")
    st.dataframe(df_nao[cols_show], use_container_width=True, height=520)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Baixar CSV (não assinou)", to_csv_bytes(df_nao[cols_show]), "pec_nao_assinou.csv", "text/csv")
    with c2:
        contato_cols = [col_nome]
        for c in [col_partido, col_uf, col_tel, col_email]:
            if c:
                contato_cols.append(c)
        st.download_button("Baixar CSV (não assinou - contatos)", to_csv_bytes(df_nao[contato_cols]), "pec_nao_assinou_contatos.csv", "text/csv")

with tab3:
    st.subheader("🧪 Nomes da sua lista que NÃO bateram com o Excel")
    if not assinantes_nao_encontrados:
        st.success("Todos os nomes da lista bateram com o Excel.")
    else:
        st.warning(f"{len(assinantes_nao_encontrados)} nome(s) não encontrados.")
        st.dataframe(pd.DataFrame({"Não encontrados": assinantes_nao_encontrados}), use_container_width=True, height=520)

with tab4:
    st.subheader("💡 Sugestões de match (para corrigir grafia/apelido)")
    if df_sug.empty:
        st.info("Sem sugestões (ou todos bateram).")
    else:
        st.dataframe(df_sug, use_container_width=True, height=520)

st.caption(
    f"Colunas detectadas → Nome: {col_nome} | Partido: {col_partido or '-'} | UF: {col_uf or '-'} | "
    f"Telefone: {col_tel or '-'} | Email: {col_email or '-'}"
)
