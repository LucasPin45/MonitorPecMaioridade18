# app_pec_assinaturas.py
# Requisitos:
#   pip install streamlit pandas openpyxl unidecode
#
# Rodar:
#   streamlit run app_pec_assinaturas.py

import io
import re
import unicodedata
from typing import List, Set

import pandas as pd
import streamlit as st


# ====== CONFIG (ajuste aqui se quiser) ======
EXCEL_PATH_DEFAULT = r"C:\Users\P_245614\Desktop\deputado_totais.xlsx"
META_ASSINATURAS = 171

COL_NOME = "Nome Parlamentar"
COL_PARTIDO = "Partido"
COL_UF = "UF"
COL_ANEXO = "Anexo"
COL_GAB = "Gabinete"
COL_TEL = "Telefone"
COL_EMAIL = "E-mail"
# ===========================================


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


def normalize_name(s: str) -> str:
    """Normaliza para matching (sem acento, minúsculo, sem pontuação, espaços únicos)."""
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


def load_df_from_upload_or_path(uploaded_file, path_str: str) -> pd.DataFrame:
    if uploaded_file is not None:
        return pd.read_excel(io.BytesIO(uploaded_file.getvalue()), engine="openpyxl")
    return pd.read_excel(path_str, engine="openpyxl")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# ---------------- UI ----------------
st.set_page_config(page_title="PEC - Assinou x Não assinou", layout="wide")
st.title("PEC — Painel de Assinaturas (Assinou x Não assinou)")

with st.sidebar:
    st.header("Fonte de dados")
    excel_path = st.text_input("Caminho do Excel", value=EXCEL_PATH_DEFAULT)
    uploaded = st.file_uploader("Ou envie o Excel (.xlsx)", type=["xlsx"])

    st.divider()
    st.header("Assinantes")
    meta = st.number_input("Meta de assinaturas", min_value=1, value=META_ASSINATURAS, step=1)
    assinantes_text = st.text_area("Lista (um nome por linha)", value=ASSINANTES_RAW_DEFAULT, height=320)

    st.caption("Se algum nome não bater por grafia, adicione aqui uma variante:")
    variantes_text = st.text_area("Variantes adicionais", value="", height=120)

    st.divider()
    st.header("Filtros")
    q_nome = st.text_input("Buscar por nome (contém)", value="").strip()
    show_only_missing = st.checkbox("Mostrar apenas 'não assinou'", value=False)

# --------- Load ---------
try:
    df = load_df_from_upload_or_path(uploaded, excel_path)
except Exception as e:
    st.error(
        "Não consegui ler o Excel.\n\n"
        f"Erro: {e}\n\n"
        "Verifique:\n"
        "- Se o caminho está correto\n"
        "- Se o arquivo está aberto no Excel (às vezes bloqueia)\n"
        "- Se é realmente .xlsx"
    )
    st.stop()

# --------- Validate columns ---------
required = [COL_NOME, COL_PARTIDO, COL_UF, COL_ANEXO, COL_GAB, COL_TEL, COL_EMAIL]
missing_cols = [c for c in required if c not in df.columns]
if missing_cols:
    st.error(f"Faltam colunas no Excel: {missing_cols}\n\nColunas encontradas: {list(df.columns)}")
    st.stop()

# --------- Prepare names ---------
df = df.copy()
df["_nome_raw"] = df[COL_NOME].astype(str).str.strip()
df["_nome_key"] = df["_nome_raw"].map(normalize_name)

assinantes = parse_names(assinantes_text)
variantes = parse_names(variantes_text)

assinantes_key: Set[str] = {normalize_name(n) for n in assinantes}
assinantes_key |= {normalize_name(n) for n in variantes}

df["Assinou"] = df["_nome_key"].isin(assinantes_key)

# --------- Summary ---------
total = len(df)
assinou_n = int(df["Assinou"].sum())
nao_n = total - assinou_n
faltam = max(int(meta) - assinou_n, 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total deputados (Excel)", total)
c2.metric("Assinou", assinou_n)
c3.metric("Não assinou", nao_n)
c4.metric(f"Faltam para {int(meta)}", faltam)

# --------- Filters ---------
df_view = df.copy()

if q_nome:
    df_view = df_view[df_view[COL_NOME].astype(str).str.contains(q_nome, case=False, na=False)]

ufs = sorted([x for x in df_view[COL_UF].dropna().astype(str).unique().tolist() if str(x).strip()])
parts = sorted([x for x in df_view[COL_PARTIDO].dropna().astype(str).unique().tolist() if str(x).strip()])

f1, f2 = st.columns(2)
with f1:
    uf_sel = st.multiselect("UF", options=ufs, default=[])
with f2:
    part_sel = st.multiselect("Partido", options=parts, default=[])

if uf_sel:
    df_view = df_view[df_view[COL_UF].astype(str).isin(uf_sel)]
if part_sel:
    df_view = df_view[df_view[COL_PARTIDO].astype(str).isin(part_sel)]

if show_only_missing:
    df_view = df_view[~df_view["Assinou"]]

# --------- Build tables ---------
cols_show = ["Assinou", COL_NOME, COL_PARTIDO, COL_UF, COL_ANEXO, COL_GAB, COL_TEL, COL_EMAIL]

df_assinou = df_view[df_view["Assinou"]].copy()
df_nao = df_view[~df_view["Assinou"]].copy()

# --------- Missing names diagnostic (assinantes que não estão no Excel) ---------
excel_keys = set(df["_nome_key"].dropna().unique().tolist())
assinantes_nao_encontrados = []
for n in assinantes:
    k = normalize_name(n)
    if k and k not in excel_keys:
        assinantes_nao_encontrados.append(n)

# --------- Tabs ---------
tab1, tab2, tab3 = st.tabs(["✅ Assinou", "❌ Não assinou", "🧪 Nomes não encontrados"])

with tab1:
    st.subheader(f"✅ Assinou ({len(df_assinou)})")
    st.dataframe(df_assinou[cols_show], use_container_width=True, height=520)
    b1, b2 = st.columns(2)
    with b1:
        st.download_button(
            "Baixar CSV (assinou)",
            data=to_csv_bytes(df_assinou[cols_show]),
            file_name="pec_assinou.csv",
            mime="text/csv"
        )
    with b2:
        st.download_button(
            "Baixar CSV (assinou - contatos)",
            data=to_csv_bytes(df_assinou[[COL_NOME, COL_PARTIDO, COL_UF, COL_TEL, COL_EMAIL]]),
            file_name="pec_assinou_contatos.csv",
            mime="text/csv"
        )

with tab2:
    st.subheader(f"❌ Não assinou ({len(df_nao)})")
    st.dataframe(df_nao[cols_show], use_container_width=True, height=520)
    b1, b2 = st.columns(2)
    with b1:
        st.download_button(
            "Baixar CSV (não assinou)",
            data=to_csv_bytes(df_nao[cols_show]),
            file_name="pec_nao_assinou.csv",
            mime="text/csv"
        )
    with b2:
        st.download_button(
            "Baixar CSV (não assinou - contatos)",
            data=to_csv_bytes(df_nao[[COL_NOME, COL_PARTIDO, COL_UF, COL_TEL, COL_EMAIL]]),
            file_name="pec_nao_assinou_contatos.csv",
            mime="text/csv"
        )

with tab3:
    st.subheader("🧪 Assinantes da lista que NÃO foram encontrados no Excel")
    if not assinantes_nao_encontrados:
        st.success("Todos os nomes da lista de assinantes bateram com o Excel 🎯")
    else:
        st.warning(f"{len(assinantes_nao_encontrados)} nome(s) não encontrados (provável divergência de grafia).")
        st.write(assinantes_nao_encontrados)
        st.caption("Dica: copie esses nomes e coloque em 'Variantes adicionais' com a grafia que está no Excel.")
