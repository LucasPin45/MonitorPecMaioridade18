# app_pec_assinaturas.py
# Streamlit 1.54+
# Monitor de Assinaturas PEC — Interface comercial / usuário externo
# - Contagem de assinaturas (apenas deputados em exercício via API Câmara)
# - Matching robusto (normalização + aliases)
# - Dashboard visual com progresso, gráficos por partido/UF
# - Tabela com foto (miniatura) e filtros amigáveis

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# ═══════════════════════════════════════════
# Config
# ═══════════════════════════════════════════

st.set_page_config(
    page_title="Monitor de Assinaturas — PEC",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
USER_AGENT = "monitorpecmaioridade18/assinaturas (streamlit)"
META_171 = 171  # quórum necessário

# ═══════════════════════════════════════════
# CSS customizado
# ═══════════════════════════════════════════

st.markdown("""
<style>
/* ---------- Tipografia e base ---------- */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
code, pre, .stCode {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ---------- Header hero ---------- */
.hero-header {
    background: linear-gradient(135deg, #0c2340 0%, #1a4f7a 50%, #2d7d9a 100%);
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    color: white;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -30%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-header h1 {
    margin: 0 0 0.3rem 0;
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}
.hero-header p {
    margin: 0;
    opacity: 0.85;
    font-size: 0.95rem;
}

/* ---------- Card KPI ---------- */
.kpi-card {
    background: white;
    border: 1px solid #e8ecf1;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    text-align: center;
    transition: box-shadow 0.2s ease;
}
.kpi-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7a8d;
    margin-bottom: 0.35rem;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.15rem;
}
.kpi-sub {
    font-size: 0.75rem;
    color: #8a96a3;
}
.kpi-green .kpi-value { color: #0d9668; }
.kpi-red .kpi-value   { color: #d94052; }
.kpi-blue .kpi-value  { color: #1a6fb5; }
.kpi-amber .kpi-value { color: #c08a1e; }

/* ---------- Barra de progresso customizada ---------- */
.progress-wrapper {
    margin: 1.2rem 0 1.8rem 0;
}
.progress-label-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
}
.progress-label-row .prog-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: #2c3e50;
}
.progress-label-row .prog-pct {
    font-weight: 700;
    font-size: 1.1rem;
}
.progress-track {
    background: #e9edf2;
    border-radius: 10px;
    height: 26px;
    position: relative;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 10px;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    position: relative;
}
.progress-fill::after {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
}
.progress-marker {
    position: absolute;
    top: -4px;
    bottom: -4px;
    width: 2px;
    background: #2c3e50;
    opacity: 0.5;
    z-index: 2;
}
.progress-marker-label {
    position: absolute;
    top: -20px;
    transform: translateX(-50%);
    font-size: 0.7rem;
    font-weight: 600;
    color: #2c3e50;
    opacity: 0.7;
    white-space: nowrap;
}

/* ---------- Seção status ---------- */
.status-banner {
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    font-weight: 600;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
}
.status-ok {
    background: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
}
.status-warn {
    background: #fffbeb;
    color: #92400e;
    border: 1px solid #fde68a;
}

/* ---------- Tabela melhorada ---------- */
[data-testid="stDataEditor"] {
    border: 1px solid #e8ecf1;
    border-radius: 10px;
    overflow: hidden;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: #f8fafb;
}
section[data-testid="stSidebar"] .stTextArea textarea {
    font-size: 0.82rem;
    line-height: 1.4;
    font-family: 'JetBrains Mono', monospace;
}

/* ---------- Expander ---------- */
.streamlit-expanderHeader {
    font-weight: 600;
}

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.88rem;
}

/* ---------- Remove excesso de padding Streamlit ---------- */
.block-container {
    padding-top: 1.5rem;
    max-width: 1200px;
}

/* ---------- Badges ---------- */
.badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-green { background: #d1fae5; color: #065f46; }
.badge-red   { background: #fee2e2; color: #991b1b; }
.badge-gray  { background: #f1f5f9; color: #475569; }

/* ---------- Chart labels ---------- */
.chart-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: #374151;
    margin-bottom: 0.6rem;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# Aliases e stopwords
# ═══════════════════════════════════════════

ALIASES_OFICIAIS: Dict[str, str] = {
    "benes leocadio": "Benes Leocádio",
    "gilvan da federal": "Gilvan da Federal",
    "rodrigo estacho": "Rodrigo Estacho",
}

STOPWORDS_LINHAS = {
    "coautoria deputado(s)",
    "coautoria deputados",
    "subscritor",
    "subscritores",
    "assinaturas",
    "assinaram",
    "assinou",
}

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
Benes Leocádio
Gilvan da Federal
Rodrigo Estacho
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


# ═══════════════════════════════════════════
# Funções de normalização e matching
# ═══════════════════════════════════════════

def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = _strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_assinantes(raw: str) -> List[str]:
    lines = []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln_norm = normalize_name(ln)
        if not ln_norm:
            continue
        if ln_norm in STOPWORDS_LINHAS:
            continue
        lines.append(ln)

    seen = set()
    out = []
    for x in lines:
        k = normalize_name(x)
        if k in seen:
            continue
        seen.add(k)
        out.append(x.strip())
    return out


def requests_get_json(url: str, params: Optional[dict] = None, timeout: int = 20) -> dict:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"Falha ao acessar API da Câmara: {last_err}")


@dataclass
class Dep:
    id: int
    nome: str
    siglaPartido: str
    siglaUf: str
    urlFoto: str

    @property
    def key(self) -> str:
        return normalize_name(self.nome)


@st.cache_data(ttl=60 * 20, show_spinner=False)
def fetch_deputados_em_exercicio() -> List[Dep]:
    url = f"{CAMARA_API_BASE}/deputados"
    params = {"itens": 600, "ordem": "ASC", "ordenarPor": "nome"}
    data = requests_get_json(url, params=params)
    dados = data.get("dados", []) or []
    deps: List[Dep] = []
    for d in dados:
        try:
            deps.append(
                Dep(
                    id=int(d.get("id")),
                    nome=str(d.get("nome", "")).strip(),
                    siglaPartido=str(d.get("siglaPartido", "")).strip(),
                    siglaUf=str(d.get("siglaUf", "")).strip(),
                    urlFoto=str(d.get("urlFoto", "")).strip(),
                )
            )
        except Exception:
            continue
    deps = [x for x in deps if x.nome and x.id]
    return deps


def build_index(deps: List[Dep]) -> Dict[str, Dep]:
    idx: Dict[str, Dep] = {}
    for dep in deps:
        idx[dep.key] = dep
    return idx


def apply_aliases(names: List[str]) -> List[str]:
    out = []
    for n in names:
        k = normalize_name(n)
        if k in ALIASES_OFICIAIS:
            out.append(ALIASES_OFICIAIS[k])
        else:
            out.append(n)
    return out


def match_assinantes(
    assinantes_raw: List[str],
    deps: List[Dep],
) -> Tuple[pd.DataFrame, List[str]]:
    idx = build_index(deps)
    assinantes_raw = apply_aliases(assinantes_raw)
    found: List[Dep] = []
    nao_encontrados: List[str] = []
    seen_dep_ids = set()

    for n in assinantes_raw:
        k = normalize_name(n)
        if not k:
            continue
        dep = idx.get(k)
        if dep is None:
            k2 = re.sub(
                r"^(dep|deputado|dra|dr|delegado|coronel|capitao|pr|pastor|general|sargento)\s+",
                "", k,
            ).strip()
            dep = idx.get(k2)

        if dep is None:
            nao_encontrados.append(n)
            continue
        if dep.id in seen_dep_ids:
            continue
        seen_dep_ids.add(dep.id)
        found.append(dep)

    df = pd.DataFrame(
        [
            {
                "Foto": x.urlFoto,
                "Nome": x.nome,
                "Partido": x.siglaPartido,
                "UF": x.siglaUf,
                "ID": x.id,
            }
            for x in found
        ]
    )
    if not df.empty:
        df = df.sort_values(["Nome"], ascending=True).reset_index(drop=True)
    return df, nao_encontrados


def make_df_nao_assinou(deps: List[Dep], df_assinou: pd.DataFrame) -> pd.DataFrame:
    assinou_ids = set(df_assinou["ID"].tolist()) if not df_assinou.empty else set()
    rows = []
    for d in deps:
        if d.id in assinou_ids:
            continue
        rows.append(
            {
                "Foto": d.urlFoto,
                "Nome": d.nome,
                "Partido": d.siglaPartido,
                "UF": d.siglaUf,
                "ID": d.id,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Nome"], ascending=True).reset_index(drop=True)
    return df


# ═══════════════════════════════════════════
# Helpers de visualização
# ═══════════════════════════════════════════

def render_progress_bar(assinou: int, meta: int, total: int):
    pct = min(assinou / meta * 100, 100) if meta > 0 else 0
    # Cor: verde se atingiu, âmbar se > 60%, vermelho se < 60%
    if pct >= 100:
        color = "linear-gradient(90deg, #059669 0%, #10b981 100%)"
        pct_color = "#059669"
    elif pct >= 60:
        color = "linear-gradient(90deg, #d97706 0%, #f59e0b 100%)"
        pct_color = "#d97706"
    else:
        color = "linear-gradient(90deg, #dc2626 0%, #ef4444 100%)"
        pct_color = "#dc2626"

    marker_pct = (meta / total * 100) if total > 0 else 33

    st.markdown(f"""
    <div class="progress-wrapper">
        <div class="progress-label-row">
            <span class="prog-title">Progresso para {meta} assinaturas</span>
            <span class="prog-pct" style="color:{pct_color}">{assinou}/{meta} ({pct:.0f}%)</span>
        </div>
        <div class="progress-track">
            <div class="progress-fill" style="width:{min(pct,100):.1f}%; background:{color};"></div>
            <div class="progress-marker" style="left:{marker_pct:.1f}%;">
                <span class="progress-marker-label">{meta}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi(label: str, value, css_class: str = "", sub: str = ""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    st.markdown(f"""
    <div class="kpi-card {css_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_table(df: pd.DataFrame, search_text: str = ""):
    """Renderiza tabela com foto, filtrada por busca de texto."""
    if df.empty:
        st.info("Nenhum deputado nesta lista com os filtros aplicados.")
        return

    df_show = df.copy()

    # Filtro de busca textual
    if search_text.strip():
        mask = df_show.apply(
            lambda row: search_text.lower() in str(row["Nome"]).lower()
            or search_text.lower() in str(row["Partido"]).lower()
            or search_text.lower() in str(row["UF"]).lower(),
            axis=1,
        )
        df_show = df_show[mask].reset_index(drop=True)

    if df_show.empty:
        st.info(f'Nenhum resultado para "{search_text}".')
        return

    st.data_editor(
        df_show,
        hide_index=True,
        disabled=True,
        use_container_width=True,
        column_config={
            "Foto": st.column_config.ImageColumn(
                "📷",
                help="Foto oficial — Câmara dos Deputados",
                width="small",
            ),
            "Nome": st.column_config.TextColumn("Nome", width="large"),
            "Partido": st.column_config.TextColumn("Partido", width="small"),
            "UF": st.column_config.TextColumn("UF", width="small"),
            "ID": None,  # esconde ID — não interessa ao usuário externo
        },
    )
    st.caption(f"Exibindo {len(df_show)} deputado(s)")


def build_chart_data_partido(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("Partido").size().reset_index(name="Qtd")
    grouped = grouped.sort_values("Qtd", ascending=False).head(15)
    return grouped


def build_chart_data_uf(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("UF").size().reset_index(name="Qtd")
    grouped = grouped.sort_values("Qtd", ascending=False)
    return grouped


# ═══════════════════════════════════════════
# SIDEBAR — Entrada de dados
# ═══════════════════════════════════════════

with st.sidebar:
    st.markdown("### 📋 Lista de Assinantes")
    st.caption(
        "Cole abaixo a lista de quem assinou — um nome por linha. "
        "Dados copiados do **Infoleg Autenticador**."
    )
    assinantes_text = st.text_area(
        "Lista (um nome por linha)",
        value=ASSINANTES_RAW_DEFAULT,
        height=340,
        label_visibility="collapsed",
        placeholder="Cole a lista aqui — um nome por linha…",
    )

    assinantes_list = parse_assinantes(assinantes_text)
    st.markdown(f"**{len(assinantes_list)}** nome(s) identificado(s) na lista colada")

    st.divider()
    st.markdown("### ⚙️ Configuração")
    meta_custom = st.number_input(
        "Meta de assinaturas",
        min_value=1,
        max_value=513,
        value=META_171,
        help="PECs exigem 171 assinaturas (1/3 da Câmara).",
    )

    st.divider()
    st.caption("Fonte: [Dados Abertos — Câmara dos Deputados](https://dadosabertos.camara.leg.br)")


# ═══════════════════════════════════════════
# Carregar dados e calcular
# ═══════════════════════════════════════════

with st.spinner("Consultando deputados em exercício…"):
    deps = fetch_deputados_em_exercicio()

df_assinou, nao_encontrados = match_assinantes(assinantes_list, deps)
df_nao_assinou = make_df_nao_assinou(deps, df_assinou)

total_api = len(deps)
assinou_n = int(df_assinou.shape[0])
nao_assinou_n = total_api - assinou_n
faltam = max(0, int(meta_custom) - assinou_n)
pct_camara = (assinou_n / total_api * 100) if total_api > 0 else 0


# ═══════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════

st.markdown("""
<div class="hero-header">
    <h1>📋 Monitor de Assinaturas — PEC</h1>
    <p>Acompanhamento em tempo real das assinaturas coletadas, cruzando com a base oficial de deputados em exercício.</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# KPIs
# ═══════════════════════════════════════════

k1, k2, k3, k4 = st.columns(4)
with k1:
    render_kpi("Assinaram", assinou_n, "kpi-green", f"de {total_api} em exercício")
with k2:
    render_kpi("Faltam p/ meta", faltam if faltam > 0 else "✓", "kpi-amber" if faltam > 0 else "kpi-green", f"meta: {int(meta_custom)}")
with k3:
    render_kpi("Não assinaram", nao_assinou_n, "kpi-red", f"{pct_camara:.1f}% da Câmara")
with k4:
    render_kpi("Deputados (API)", total_api, "kpi-blue", "em exercício")


# ═══════════════════════════════════════════
# Barra de progresso
# ═══════════════════════════════════════════

render_progress_bar(assinou_n, int(meta_custom), total_api)


# ═══════════════════════════════════════════
# Status banner
# ═══════════════════════════════════════════

if nao_encontrados:
    st.markdown(
        f'<div class="status-banner status-warn">⚠️ {len(nao_encontrados)} nome(s) da lista não foram reconhecidos na base oficial — verifique na seção abaixo.</div>',
        unsafe_allow_html=True,
    )
elif assinou_n >= int(meta_custom):
    st.markdown(
        '<div class="status-banner status-ok">✅ Meta atingida! Todos os nomes foram reconhecidos na base oficial.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-banner status-ok">✅ Todos os nomes foram reconhecidos na base oficial.</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════
# Gráficos resumo
# ═══════════════════════════════════════════

st.markdown("---")

gcol1, gcol2 = st.columns(2)

with gcol1:
    st.markdown('<div class="chart-title">Assinaturas por Partido (top 15)</div>', unsafe_allow_html=True)
    chart_partido = build_chart_data_partido(df_assinou)
    if not chart_partido.empty:
        st.bar_chart(chart_partido, x="Partido", y="Qtd", color="#1a6fb5", horizontal=True, height=380)
    else:
        st.info("Sem dados para exibir.")

with gcol2:
    st.markdown('<div class="chart-title">Assinaturas por Estado</div>', unsafe_allow_html=True)
    chart_uf = build_chart_data_uf(df_assinou)
    if not chart_uf.empty:
        st.bar_chart(chart_uf, x="UF", y="Qtd", color="#059669", height=380)
    else:
        st.info("Sem dados para exibir.")


# ═══════════════════════════════════════════
# Tabelas — Assinou / Não Assinou
# ═══════════════════════════════════════════

st.markdown("---")

tab_assinou, tab_nao_assinou = st.tabs([
    f"✅ Assinaram ({assinou_n})",
    f"❌ Não assinaram ({nao_assinou_n})",
])

# ---- Filtros (compartilhados) ----
ufs = sorted({d.siglaUf for d in deps if d.siglaUf})
partidos = sorted({d.siglaPartido for d in deps if d.siglaPartido})

with tab_assinou:
    fa1, fa2, fa3 = st.columns([2, 2, 3])
    with fa1:
        uf_sel_a = st.multiselect("UF", options=ufs, default=[], key="uf_assinou")
    with fa2:
        partido_sel_a = st.multiselect("Partido", options=partidos, default=[], key="part_assinou")
    with fa3:
        search_a = st.text_input("🔍 Buscar por nome", key="search_assinou", placeholder="Digite o nome…")

    df_view_a = df_assinou.copy()
    if uf_sel_a:
        df_view_a = df_view_a[df_view_a["UF"].isin(uf_sel_a)]
    if partido_sel_a:
        df_view_a = df_view_a[df_view_a["Partido"].isin(partido_sel_a)]
    df_view_a = df_view_a.reset_index(drop=True)

    render_table(df_view_a, search_a)

    # Download CSV
    if not df_view_a.empty:
        csv = df_view_a[["Nome", "Partido", "UF"]].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Baixar lista (CSV)",
            data=csv,
            file_name="assinaram_pec.csv",
            mime="text/csv",
        )

with tab_nao_assinou:
    fn1, fn2, fn3 = st.columns([2, 2, 3])
    with fn1:
        uf_sel_n = st.multiselect("UF", options=ufs, default=[], key="uf_nao_assinou")
    with fn2:
        partido_sel_n = st.multiselect("Partido", options=partidos, default=[], key="part_nao_assinou")
    with fn3:
        search_n = st.text_input("🔍 Buscar por nome", key="search_nao_assinou", placeholder="Digite o nome…")

    df_view_n = df_nao_assinou.copy()
    if uf_sel_n:
        df_view_n = df_view_n[df_view_n["UF"].isin(uf_sel_n)]
    if partido_sel_n:
        df_view_n = df_view_n[df_view_n["Partido"].isin(partido_sel_n)]
    df_view_n = df_view_n.reset_index(drop=True)

    render_table(df_view_n, search_n)

    if not df_view_n.empty:
        csv_n = df_view_n[["Nome", "Partido", "UF"]].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Baixar lista (CSV)",
            data=csv_n,
            file_name="nao_assinaram_pec.csv",
            mime="text/csv",
        )


# ═══════════════════════════════════════════
# Nomes não reconhecidos
# ═══════════════════════════════════════════

if nao_encontrados:
    st.markdown("---")
    with st.expander(f"⚠️ Nomes não reconhecidos ({len(nao_encontrados)})", expanded=False):
        st.markdown(
            "Esses nomes **não casaram** com nenhum deputado em exercício na base oficial. "
            "Possivelmente esteja fora do mandato. "
            
        )
        for nome in nao_encontrados:
            st.markdown(f"- `{nome}`")