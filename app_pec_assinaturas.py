# app_pec_assinaturas_api.py
# Streamlit - Painel de assinaturas de PEC (Assinou x Não assinou)
# Fonte de deputados: API Dados Abertos da Câmara (sem Excel)
#
# Requisitos:
#   pip install streamlit pandas requests unidecode
#
# Rodar:
#   streamlit run app_pec_assinaturas_api.py

import re
import unicodedata
from difflib import get_close_matches
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
import streamlit as st
from unidecode import unidecode


# =========================
# CONFIG
# =========================
META_ASSINATURAS = 171

# Cole aqui a lista da Câmara (um por linha). Pode vir com lixo tipo "Subscritor" e "Coautoria Deputado(s)".
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
Coautoria Deputado(s)
"""

# Itens administrativos/lixo que aparecem na listagem e NÃO são parlamentares
BLACKLIST_LINES = {
    "subscritor",
    "coautoria deputado(s)",
    "coautoria deputados",
    "coautoria deputadas",
    "coautoria",
}

# Títulos/prefixos comuns (nome parlamentar) — removemos APENAS no modo "loose"
TITULOS_PREFIXO = [
    "deputado", "deputada",
    "delegado", "delegada",
    "coronel",
    "capitao", "capitão",
    "general",
    "sargento",
    "pastor",
    "dr", "dra", "doutor", "doutora",
    "pr", "pr.", "pra", "pra.",
]

# Sufixos que frequentemente aparecem/omitem ("Júnior", "Filho", etc.) — removemos APENAS no modo "loose"
SUFIXOS = [
    "junior", "júnior", "jr", "jr.",
    "filho", "neto",
    "pai",
]

API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 30


# =========================
# Normalização / parsing
# =========================
def norm_basic(s: str) -> str:
    """Normalização básica: sem acento, minúsculo, sem pontuação, espaços únicos."""
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


def norm_strict_name(s: str) -> str:
    """Chave estrita: mantém sufixos (junior etc.), só normaliza caracteres."""
    return norm_basic(s)


def norm_loose_name(s: str) -> str:
    """
    Chave 'loose': remove títulos no início e sufixos comuns,
    para bater nome parlamentar com nome civil/cadastral.
    """
    x = norm_basic(s)
    if not x:
        return ""

    parts = x.split()

    # remove títulos do início (um ou mais)
    while parts and parts[0] in {norm_basic(t) for t in TITULOS_PREFIXO}:
        parts = parts[1:]

    # remove sufixos no fim (um ou mais)
    while parts and parts[-1] in {norm_basic(t) for t in SUFIXOS}:
        parts = parts[:-1]

    return " ".join(parts).strip()


def parse_assinantes(texto: str) -> List[str]:
    """Extrai nomes válidos (remove linhas vazias e lixo administrativo)."""
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
@st.cache_data(ttl=60 * 60)  # 1h
def fetch_deputados_em_exercicio() -> pd.DataFrame:
    """
    Busca deputados em exercício via API /deputados (paginado).
    Retorna dataframe com colunas principais.
    """
    sess = requests.Session()
    sess.headers.update({"Accept": "application/json"})

    itens = 100
    pagina = 1
    rows = []

    while True:
        url = f"{API_BASE}/deputados"
        params = {
            "itens": itens,
            "pagina": pagina,
            "ordem": "ASC",
            "ordenarPor": "nome",
        }
        r = sess.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        dados = j.get("dados", [])
        if not dados:
            break

        # Na prática, esse endpoint costuma listar apenas os deputados em exercício.
        # Mesmo assim, nós tratamos como "base oficial" do painel.
        for d in dados:
            rows.append({
                "id": d.get("id"),
                "nome": d.get("nome"),
                "siglaPartido": d.get("siglaPartido"),
                "siglaUf": d.get("siglaUf"),
                "urlFoto": d.get("urlFoto"),
                "uri": d.get("uri"),
            })

        pagina += 1

        # proteção
        if pagina > 20:
            break

    df = pd.DataFrame(rows).dropna(subset=["id", "nome"])
    df["nome_strict"] = df["nome"].map(norm_strict_name)
    df["nome_loose"] = df["nome"].map(norm_loose_name)
    return df


def build_loose_index(df_dep: pd.DataFrame) -> Dict[str, List[int]]:
    """
    Índice loose_key -> lista de índices do dataframe.
    Usado para auto-match somente quando único.
    """
    idx = {}
    for i, row in df_dep.reset_index(drop=True).iterrows():
        k = row["nome_loose"]
        if not k:
            continue
        idx.setdefault(k, []).append(i)
    return idx


def resolve_signer_to_deputy(
    signer_name: str,
    df_dep: pd.DataFrame,
    loose_index: Dict[str, List[int]],
) -> Tuple[Optional[int], str]:
    """
    Resolve um assinante para um deputado do DF:
    1) match estrito por nome_strict
    2) match loose (só se chave cair em UM único deputado)
    3) sem match
    Retorna (idx_deputy, modo)
    """
    s_strict = norm_strict_name(signer_name)
    s_loose = norm_loose_name(signer_name)

    # (1) estrito
    hit_strict = df_dep.index[df_dep["nome_strict"] == s_strict].tolist()
    if len(hit_strict) == 1:
        return int(hit_strict[0]), "strict"
    if len(hit_strict) > 1:
        # raro: nomes idênticos (quase impossível), evita falso positivo
        return None, "ambiguous_strict"

    # (2) loose com unicidade
    cand = loose_index.get(s_loose, [])
    if len(cand) == 1:
        return int(cand[0]), "loose_unique"
    if len(cand) > 1:
        return None, "ambiguous_loose"

    return None, "no_match"


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# =========================
# UI (sem sidebar)
# =========================
st.set_page_config(page_title="PEC — Assinou x Não assinou (API Câmara)", layout="wide")
st.title("PEC — Assinou x Não assinou (Deputados em exercício via API da Câmara)")

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    meta = st.number_input("Meta de assinaturas", min_value=1, value=META_ASSINATURAS, step=1)
with col2:
    camara_oficial = st.number_input("Contagem oficial (Câmara)", min_value=0, value=93, step=1)
with col3:
    busca = st.text_input("🔎 Buscar (nome/partido/UF)", value="").strip()

st.markdown("### Cole a lista dos assinantes (um por linha)")
assinantes_text = st.text_area("", value=ASSINANTES_RAW_DEFAULT, height=220)

st.markdown("### Variantes (opcional — só se você quiser forçar grafia específica)")
variantes_text = st.text_area("Um por linha (ex.: 'Alexandre Ramagem', 'José Telhada', etc.)", value="", height=100)

st.divider()

# ===== carrega base oficial (API) =====
with st.spinner("Carregando deputados em exercício via API da Câmara..."):
    df_dep = fetch_deputados_em_exercicio()

if df_dep.empty:
    st.error("Não consegui obter deputados via API (base vazia).")
    st.stop()

loose_index = build_loose_index(df_dep)

# ===== processa assinantes =====
assinantes = parse_assinantes(assinantes_text)
variantes = parse_assinantes(variantes_text)

# Variantes entram como assinantes adicionais (mas só ajudam se forem nomes do cadastro/API)
assinantes_all = assinantes + [v for v in variantes if v not in assinantes]

matches = []
unmatched = []
ambiguous = []

df_dep_reset = df_dep.reset_index(drop=True)

for name in assinantes_all:
    idx, mode = resolve_signer_to_deputy(name, df_dep_reset, loose_index)
    if idx is None:
        if mode.startswith("ambiguous"):
            ambiguous.append({"Nome (lista)": name, "Motivo": mode})
        else:
            unmatched.append({"Nome (lista)": name, "Motivo": mode})
        continue

    dep = df_dep_reset.loc[idx].to_dict()
    matches.append({
        "Nome (lista)": name,
        "Match": mode,
        "id": dep.get("id"),
        "Nome (API)": dep.get("nome"),
        "Partido": dep.get("siglaPartido"),
        "UF": dep.get("siglaUf"),
        "urlFoto": dep.get("urlFoto"),
    })

df_match = pd.DataFrame(matches).drop_duplicates(subset=["id"])  # evita contar duas vezes
assinou_ids = set(df_match["id"].dropna().astype(int).tolist())

# monta base final (deputados em exercício)
df_base = df_dep_reset.copy()
df_base["Assinou"] = df_base["id"].astype(int).isin(assinou_ids)

# métricas
total = len(df_base)
assinou_n = int(df_base["Assinou"].sum())
nao_n = total - assinou_n
faltam_meta = max(int(meta) - assinou_n, 0)
delta_oficial = int(camara_oficial) - assinou_n

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Deputados em exercício (API)", total)
m2.metric("Assinou (painel)", assinou_n)
m3.metric("Não assinou (painel)", nao_n)
m4.metric(f"Faltam p/ {int(meta)}", faltam_meta)
m5.metric("Diferença p/ oficial", delta_oficial)

if delta_oficial == 0:
    st.success("✅ Painel alinhado com a contagem oficial informada.")
elif delta_oficial > 0:
    st.warning(
        "⚠️ O painel está abaixo do oficial. "
        "Isso normalmente significa: algum assinante ainda não está casando com o nome da API (apelido/título/grafia). "
        "Veja as abas 'Não encontrados' e 'Sugestões'."
    )
else:
    st.warning(
        "⚠️ O painel está acima do oficial (possível duplicidade ou lista com nomes além do que a Câmara está contando). "
        "Revise a lista e a aba 'Ambíguos'."
    )

# filtros
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

# tabelas principais
cols_show = ["Assinou", "nome", "siglaPartido", "siglaUf", "id", "urlFoto"]
df_assinou = df_view[df_view["Assinou"]].copy()
df_nao = df_view[~df_view["Assinou"]].copy()

# Diagnósticos adicionais: sugestões para não encontrados
nome_api_lista = df_dep_reset["nome"].dropna().astype(str).tolist()
sugestoes = []
for item in unmatched[:300]:
    n = item["Nome (lista)"]
    cand = get_close_matches(n, nome_api_lista, n=5, cutoff=0.60)
    sugestoes.append({
        "Nome (lista)": n,
        "Sugestões (API)": " | ".join(cand),
    })
df_sug = pd.DataFrame(sugestoes)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["✅ Assinou", "❌ Não assinou", "📎 Match detalhado", "🧪 Não encontrados", "⚠️ Ambíguos"]
)

with tab1:
    st.subheader(f"✅ Assinou ({len(df_assinou)})")
    st.dataframe(df_assinou[cols_show], use_container_width=True, height=520)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Baixar CSV (assinou)", to_csv_bytes(df_assinou[cols_show]), "pec_assinou.csv", "text/csv")
    with c2:
        st.download_button("Baixar CSV (IDs assinou)", to_csv_bytes(df_assinou[["id", "nome"]]), "pec_assinou_ids.csv", "text/csv")

with tab2:
    st.subheader(f"❌ Não assinou ({len(df_nao)})")
    st.dataframe(df_nao[cols_show], use_container_width=True, height=520)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Baixar CSV (não assinou)", to_csv_bytes(df_nao[cols_show]), "pec_nao_assinou.csv", "text/csv")
    with c2:
        st.download_button("Baixar CSV (IDs não assinou)", to_csv_bytes(df_nao[["id", "nome"]]), "pec_nao_assinou_ids.csv", "text/csv")

with tab3:
    st.subheader(f"📎 Match detalhado (lista → API) ({len(df_match)})")
    if df_match.empty:
        st.info("Nenhum match feito (revise a lista).")
    else:
        st.dataframe(df_match, use_container_width=True, height=520)
        st.download_button("Baixar CSV (match)", to_csv_bytes(df_match), "pec_match_lista_api.csv", "text/csv")

with tab4:
    st.subheader(f"🧪 Nomes da lista que NÃO casaram com a API ({len(unmatched)})")
    if not unmatched:
        st.success("Tudo casou com a API.")
    else:
        st.dataframe(pd.DataFrame(unmatched), use_container_width=True, height=300)
        st.subheader("💡 Sugestões automáticas (para você copiar em Variantes, se quiser)")
        st.dataframe(df_sug, use_container_width=True, height=520)

with tab5:
    st.subheader(f"⚠️ Ambíguos (evitei auto-match para não errar) ({len(ambiguous)})")
    if not ambiguous:
        st.success("Sem casos ambíguos.")
    else:
        st.dataframe(pd.DataFrame(ambiguous), use_container_width=True, height=520)

st.caption(
    "Obs.: o painel usa a lista de deputados via API da Câmara e faz match por nome (estrito) e por nome (loose) "
    "apenas quando o loose é único, para evitar contagem errada."
)
