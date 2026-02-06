# app_pec_assinaturas.py
# Streamlit - Painel de assinaturas PEC (Assinou x Não assinou)
# Fonte de deputados em exercício: API Dados Abertos da Câmara (sem Excel)
# Matching robusto: strict -> loose -> fuzzy por tokens
#
# Requisitos:
#   pip install streamlit pandas requests unidecode
#
# Rodar:
#   streamlit run app_pec_assinaturas.py

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st


# =========================
# CONFIG
# =========================
META_ASSINATURAS = 171
API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 30

ASSINANTES_RAW_DEFAULT = """Júlia Zanatta
Adilson Barroso
Alexandre Guimarães
Alberto Fraga
Alberto Mourão
Alceu Moreira
Altineu Côrtes
Aluisio Mendes
André Fernandes
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
Giovani Cherini
Gutemberg Reis
Gustavo Gayer
Ismael
Jorge Goetten
José Medeiros
Junior Lourenço
Junio Amaral
Julia Zanatta
Kim Kataguiri
Lincoln Portela
Luciano Alves
Luisa Canziani
Luiz Carlos Motta
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
Vinicius Gurgel
Wellington Roberto
Zé Trovão
Zucco
Subscritor
Coautoria Deputado(s)
Abilio Brunini
"""

BLACKLIST_LINES = {
    "subscritor",
    "coautoria deputado(s)",
    "coautoria deputados",
    "coautoria deputadas",
    "coautoria",
}

TITULOS_PREFIXO = {
    "deputado", "deputada",
    "delegado", "delegada",
    "coronel",
    "capitao", "capitão",
    "general",
    "sargento",
    "pastor",
    "dr", "dra", "doutor", "doutora",
    "pr", "pr.", "pra", "pra.",
}

SUFIXOS = {"junior", "júnior", "jr", "jr.", "filho", "neto", "pai"}
STOPWORDS = {"de", "da", "do", "das", "dos", "e", "d"}


# =========================
# Normalização
# =========================
def norm_basic(s: str) -> str:
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


def tokens(s: str) -> List[str]:
    x = norm_basic(s)
    if not x:
        return []
    return [t for t in x.split() if t and t not in STOPWORDS]


def strip_prefix_titles(tok: List[str]) -> List[str]:
    out = tok[:]
    titles = {norm_basic(t) for t in TITULOS_PREFIXO}
    while out and out[0] in titles:
        out = out[1:]
    return out


def strip_suffixes(tok: List[str]) -> List[str]:
    out = tok[:]
    suf = {norm_basic(t) for t in SUFIXOS}
    while out and out[-1] in suf:
        out = out[:-1]
    return out


def norm_strict_name(s: str) -> str:
    return norm_basic(s)


def norm_loose_name(s: str) -> str:
    tok = tokens(s)
    tok = strip_prefix_titles(tok)
    tok = strip_suffixes(tok)
    return " ".join(tok).strip()


# =========================
# Parsing de assinantes
# =========================
def parse_assinantes(texto: str) -> List[str]:
    out = []
    seen = set()
    for line in (texto or "").splitlines():
        raw = line.strip()
        if not raw:
            continue
        key = norm_basic(raw)
        if key in BLACKLIST_LINES:
            continue
        if key and key not in seen:
            seen.add(key)
            out.append(raw)
    return out


# =========================
# API Câmara
# =========================
@st.cache_data(ttl=60 * 60)
def fetch_deputados_em_exercicio() -> pd.DataFrame:
    sess = requests.Session()
    sess.headers.update({"Accept": "application/json"})

    itens = 100
    pagina = 1
    rows = []

    while True:
        url = f"{API_BASE}/deputados"
        params = {"itens": itens, "pagina": pagina, "ordem": "ASC", "ordenarPor": "nome"}
        r = sess.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        dados = j.get("dados", [])
        if not dados:
            break

        for d in dados:
            rows.append(
                {
                    "id": d.get("id"),
                    "nome": d.get("nome"),
                    "siglaPartido": d.get("siglaPartido"),
                    "siglaUf": d.get("siglaUf"),
                    "urlFoto": d.get("urlFoto"),
                    "uri": d.get("uri"),
                }
            )

        pagina += 1
        if pagina > 40:
            break

    df = pd.DataFrame(rows).dropna(subset=["id", "nome"])
    df["nome_strict"] = df["nome"].map(norm_strict_name)
    df["nome_loose"] = df["nome"].map(norm_loose_name)
    return df.reset_index(drop=True)


def build_loose_index(df_dep: pd.DataFrame) -> Dict[str, List[int]]:
    idx: Dict[str, List[int]] = {}
    for i, row in df_dep.iterrows():
        k = row["nome_loose"]
        if k:
            idx.setdefault(k, []).append(int(i))
    return idx


# =========================
# Fuzzy matching
# =========================
def token_set_similarity(a_tokens: List[str], b_tokens: List[str]) -> float:
    sa, sb = set(a_tokens), set(b_tokens)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def nickname_firstname_score(a: str, b: str) -> float:
    a = norm_basic(a)
    b = norm_basic(b)
    if not a or not b:
        return 0.0
    return 1.0 if a[:3] == b[:3] else 0.0


def best_fuzzy_candidate(
    signer: str,
    df_dep: pd.DataFrame,
    min_score: float = 0.55,
    min_margin: float = 0.10,
) -> Tuple[Optional[int], float]:
    s_tok = tokens(signer)
    s_tok = strip_prefix_titles(s_tok)
    s_tok = strip_suffixes(s_tok)
    if not s_tok:
        return None, 0.0

    s_last = s_tok[-1]

    best_i = None
    best = -1.0
    second = -1.0

    for i, row in df_dep.iterrows():
        c_tok = tokens(row["nome"])
        if not c_tok:
            continue

        c_last = c_tok[-1]
        if c_last != s_last:
            continue

        score = token_set_similarity(s_tok, c_tok)

        if s_tok and c_tok:
            score += 0.05 * nickname_firstname_score(s_tok[0], c_tok[0])

        if score > best:
            second = best
            best = score
            best_i = int(i)
        elif score > second:
            second = score

    if best_i is None:
        return None, 0.0

    if best >= min_score and (best - second) >= min_margin:
        return best_i, best

    return None, best


def resolve_signer_to_deputy(
    signer_name: str,
    df_dep: pd.DataFrame,
    loose_index: Dict[str, List[int]],
) -> Tuple[Optional[int], str]:
    s_strict = norm_strict_name(signer_name)
    s_loose = norm_loose_name(signer_name)

    # (1) strict
    hit = df_dep.index[df_dep["nome_strict"] == s_strict].tolist()
    if len(hit) == 1:
        return int(hit[0]), "strict"
    if len(hit) > 1:
        return None, "ambiguous_strict"

    # (2) loose único
    cand = loose_index.get(s_loose, [])
    if len(cand) == 1:
        return int(cand[0]), "loose_unique"
    if len(cand) > 1:
        return None, "ambiguous_loose"

    # (3) fuzzy
    best_i, best_score = best_fuzzy_candidate(signer_name, df_dep)
    if best_i is not None:
        return best_i, f"fuzzy_tokens({best_score:.2f})"

    return None, "no_match"


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# =========================
# UI
# =========================
st.set_page_config(page_title="PEC — Assinou x Não assinou (API Câmara) v2", layout="wide")
st.title("PEC — Painel de Assinaturas (Assinou x Não assinou) — API Câmara (v2)")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    meta = st.number_input("Meta", min_value=1, value=META_ASSINATURAS, step=1)
with c2:
    oficial = st.number_input("Oficial (Câmara)", min_value=0, value=93, step=1)
with c3:
    busca = st.text_input("🔎 Buscar (nome/partido/UF)", value="").strip()

st.markdown("### Lista de assinantes (um por linha)")
assinantes_text = st.text_area(
    label="Lista de assinantes",
    value=ASSINANTES_RAW_DEFAULT,
    height=220,
    label_visibility="collapsed",
)

st.markdown("### Variantes (opcional)")
variantes_text = st.text_area(
    label="Variantes de nomes (forçar match)",
    value="",
    height=90,
    help="Se quiser forçar algum nome exatamente como na API, cole aqui (um por linha).",
)

st.divider()

# ===== base API =====
with st.spinner("Carregando deputados em exercício via API..."):
    df_dep = fetch_deputados_em_exercicio()

if df_dep.empty:
    st.error("API retornou base vazia.")
    st.stop()

loose_index = build_loose_index(df_dep)

# ===== processa lista =====
assinantes = parse_assinantes(assinantes_text)
variantes = parse_assinantes(variantes_text)
assinantes_all = assinantes + [v for v in variantes if v not in assinantes]

matches = []
unmatched = []
ambiguous = []

for name in assinantes_all:
    idx, mode = resolve_signer_to_deputy(name, df_dep, loose_index)
    if idx is None:
        if mode.startswith("ambiguous"):
            ambiguous.append({"Nome (lista)": name, "Motivo": mode})
        else:
            unmatched.append({"Nome (lista)": name, "Motivo": mode})
        continue

    dep = df_dep.loc[idx].to_dict()
    matches.append(
        {
            "Nome (lista)": name,
            "Match": mode,
            "id": int(dep["id"]),
            "Nome (API)": dep["nome"],
            "Partido": dep.get("siglaPartido"),
            "UF": dep.get("siglaUf"),
            "urlFoto": dep.get("urlFoto"),
        }
    )

df_match = pd.DataFrame(matches)
if not df_match.empty:
    df_match = df_match.drop_duplicates(subset=["id"])

assinou_ids = set(df_match["id"].dropna().astype(int).tolist()) if not df_match.empty else set()

# ===== base final =====
df_base = df_dep.copy()
df_base["Assinou"] = df_base["id"].astype(int).isin(assinou_ids)

total = len(df_base)
assinou_n = int(df_base["Assinou"].sum())
nao_n = total - assinou_n
faltam = max(int(meta) - assinou_n, 0)
delta = int(oficial) - assinou_n

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Deputados em exercício (API)", total)
m2.metric("Assinou (painel)", assinou_n)
m3.metric("Não assinou", nao_n)
m4.metric(f"Faltam p/ {int(meta)}", faltam)
m5.metric("Diferença p/ oficial", delta)

if delta == 0:
    st.success("✅ Bateu com o oficial.")
elif delta > 0:
    st.warning("⚠️ Abaixo do oficial: veja 'Não encontrados' e 'Ambíguos'.")
else:
    st.warning("⚠️ Acima do oficial: revise duplicidades/nomes na lista.")

# ===== filtros =====
df_view = df_base.copy()
if busca:
    df_view["_search"] = (
        df_view["nome"].astype(str)
        + " | " + df_view["siglaPartido"].astype(str)
        + " | " + df_view["siglaUf"].astype(str)
    )
    df_view = df_view[df_view["_search"].str.contains(busca, case=False, na=False)]

f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    ufs = sorted(df_view["siglaUf"].dropna().astype(str).unique().tolist())
    uf_sel = st.multiselect("UF", options=ufs, default=[])
with f2:
    parts = sorted(df_view["siglaPartido"].dropna().astype(str).unique().tolist())
    part_sel = st.multiselect("Partido", options=parts, default=[])
with f3:
    only_nao = st.checkbox("Mostrar só NÃO assinou", value=False)

if uf_sel:
    df_view = df_view[df_view["siglaUf"].astype(str).isin(uf_sel)]
if part_sel:
    df_view = df_view[df_view["siglaPartido"].astype(str).isin(part_sel)]
if only_nao:
    df_view = df_view[~df_view["Assinou"]]

cols_show = ["Assinou", "nome", "siglaPartido", "siglaUf", "id", "urlFoto"]
df_assinou = df_view[df_view["Assinou"]].copy()
df_nao = df_view[~df_view["Assinou"]].copy()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["✅ Assinou", "❌ Não assinou", "📎 Match detalhado", "🧪 Não encontrados", "⚠️ Ambíguos"]
)

with tab1:
    st.subheader(f"✅ Assinou ({len(df_assinou)})")
    st.dataframe(df_assinou[cols_show], width="stretch", height=520)
    st.download_button("Baixar CSV (assinou)", to_csv_bytes(df_assinou[cols_show]), "pec_assinou.csv", "text/csv")

with tab2:
    st.subheader(f"❌ Não assinou ({len(df_nao)})")
    st.dataframe(df_nao[cols_show], width="stretch", height=520)
    st.download_button("Baixar CSV (não assinou)", to_csv_bytes(df_nao[cols_show]), "pec_nao_assinou.csv", "text/csv")

with tab3:
    st.subheader(f"📎 Match detalhado (lista → API) ({len(df_match)})")
    if df_match.empty:
        st.info("Nenhum match feito.")
    else:
        st.dataframe(df_match, width="stretch", height=520)
        st.download_button("Baixar CSV (match)", to_csv_bytes(df_match), "pec_match.csv", "text/csv")

with tab4:
    st.subheader(f"🧪 Não encontrados ({len(unmatched)})")
    if not unmatched:
        st.success("Tudo casou com a API.")
    else:
        st.dataframe(pd.DataFrame(unmatched), width="stretch", height=520)

with tab5:
    st.subheader(f"⚠️ Ambíguos ({len(ambiguous)})")
    if not ambiguous:
        st.success("Sem ambíguos.")
    else:
        st.dataframe(pd.DataFrame(ambiguous), width="stretch", height=520)

st.caption(
    "Matching v2: strict → loose (remove títulos/sufixos) → fuzzy por tokens (exige mesmo sobrenome final + unicidade por margem)."
)
