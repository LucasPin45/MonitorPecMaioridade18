# app_req_urgencia_maria_da_penha.py
# Streamlit 1.54+
# Monitor de Assinaturas — REQ de Urgência (art. 155 RICD)
# PL 5.128/2025 — "Falsa Denúncia / Maria da Penha"
# Código: CD263486371900

from __future__ import annotations

import io
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import requests
import streamlit as st

# ═══════════════════════════════════════════
# Config
# ═══════════════════════════════════════════

st.set_page_config(
    page_title="Monitor — REQ Urgência Maria da Penha",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
USER_AGENT = "monitor-req-urgencia-mariada-penha/assinaturas (streamlit)"
META_DEFAULT = 257  # maioria absoluta — art. 155 RICD

# ═══════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
code, pre, .stCode { font-family: 'JetBrains Mono', monospace !important; }

.hero-header {
    background: linear-gradient(135deg, #4a0d1a 0%, #7b1e2e 50%, #a53045 100%);
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
    top: -30%; right: -10%;
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-header h1 { margin: 0 0 0.3rem 0; font-size: 1.7rem; font-weight: 700; letter-spacing: -0.02em; }
.hero-header p  { margin: 0; opacity: 0.85; font-size: 0.92rem; }
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 6px;
    padding: 0.15rem 0.6rem;
    font-size: 0.78rem; font-weight: 600;
    margin-bottom: 0.6rem; letter-spacing: 0.04em;
}

.kpi-card {
    background: white; border: 1px solid #e8ecf1;
    border-radius: 12px; padding: 1.2rem 1.4rem;
    text-align: center; transition: box-shadow 0.2s ease;
}
.kpi-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.kpi-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7a8d; margin-bottom: 0.35rem; }
.kpi-value { font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 0.15rem; }
.kpi-sub   { font-size: 0.75rem; color: #8a96a3; }
.kpi-green   .kpi-value { color: #0d9668; }
.kpi-red     .kpi-value { color: #d94052; }
.kpi-blue    .kpi-value { color: #1a6fb5; }
.kpi-amber   .kpi-value { color: #c08a1e; }
.kpi-crimson .kpi-value { color: #9b1c2e; }
.kpi-purple  .kpi-value { color: #6d28d9; }

.progress-wrapper { margin: 1.2rem 0 1.8rem 0; }
.progress-label-row { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5rem; }
.prog-title { font-weight: 600; font-size: 0.95rem; color: #2c3e50; }
.prog-pct   { font-weight: 700; font-size: 1.1rem; }
.progress-track { background: #e9edf2; border-radius: 10px; height: 26px; position: relative; overflow: hidden; }
.progress-fill  { height: 100%; border-radius: 10px; transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1); position: relative; }
.progress-fill::after {
    content: ''; position: absolute; top:0; left:0; right:0; bottom:0;
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
}
.progress-marker { position: absolute; top: -4px; bottom: -4px; width: 2px; background: #2c3e50; opacity: 0.5; z-index: 2; }
.progress-marker-label { position: absolute; top: -20px; transform: translateX(-50%); font-size: 0.7rem; font-weight: 600; color: #2c3e50; opacity: 0.7; white-space: nowrap; }

.status-banner { border-radius: 10px; padding: 0.8rem 1.2rem; font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
.status-ok   { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.status-warn { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }

[data-testid="stDataEditor"] { border: 1px solid #e8ecf1; border-radius: 10px; overflow: hidden; }

section[data-testid="stSidebar"] { background: #f8fafb; }
section[data-testid="stSidebar"] .stTextArea textarea { font-size: 0.82rem; line-height: 1.4; font-family: 'JetBrains Mono', monospace; }

.streamlit-expanderHeader { font-weight: 600; }
button[data-baseweb="tab"] { font-weight: 600; font-size: 0.88rem; }
.block-container { padding-top: 1.5rem; max-width: 1200px; }

.chart-title { font-size: 0.88rem; font-weight: 600; color: #374151; margin-bottom: 0.6rem; }

.alias-suggestion {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 0.6rem 1rem; margin: 0.3rem 0;
    font-size: 0.82rem; color: #374151;
}
.alias-suggestion code { background: #e2e8f0; padding: 0.1rem 0.3rem; border-radius: 3px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# Aliases e stopwords
# ═══════════════════════════════════════════

ALIASES_OFICIAIS: Dict[str, str] = {
    "benes leocadio": "Benes Leocádio",
    "gilvan da federal": "Gilvan da Federal",
    "rodrigo estacho": "Rodrigo Estacho",
    "cabo gilberto silva": "Cabo Gilberto Silva",
    "delegado paulo bilynskyj": "Delegado Paulo Bilynskyj",
    "capitao alden": "Capitão Alden",
    "evair vieira de melo": "Evair Vieira de Melo",
    "mario frias": "Mario Frias",
}

STOPWORDS_LINHAS = {
    "autoria", "coautoria deputado(s)", "coautoria deputados",
    "subscritor", "subscritores", "assinaturas", "assinaram", "assinou",
}

ASSINANTES_RAW_DEFAULT = """Julia Zanatta
Capitão Alden
Evair Vieira de Melo
Mario Frias
Delegado Paulo Bilynskyj
Cabo Gilberto Silva
"""

PREFIX_STRIP_RE = re.compile(
    r"^(dep|deputado|dra|dr|delegada|delegado|coronel|capitao|capitao|pr|pastor|general|sargento|cabo)\s+",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════
# Normalização e parsing
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
    seen: set = set()
    out: List[str] = []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        k = normalize_name(ln)
        if not k or k in STOPWORDS_LINHAS or k in seen:
            continue
        seen.add(k)
        out.append(ln)
    return out


# ═══════════════════════════════════════════
# API Câmara
# ═══════════════════════════════════════════

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
def fetch_deputados_em_exercicio() -> Tuple[List[Dep], str]:
    url = f"{CAMARA_API_BASE}/deputados"
    params = {"itens": 600, "ordem": "ASC", "ordenarPor": "nome"}
    data = requests_get_json(url, params=params)
    dados = data.get("dados", []) or []
    deps: List[Dep] = []
    for d in dados:
        try:
            deps.append(Dep(
                id=int(d.get("id")),
                nome=str(d.get("nome", "")).strip(),
                siglaPartido=str(d.get("siglaPartido", "")).strip(),
                siglaUf=str(d.get("siglaUf", "")).strip(),
                urlFoto=str(d.get("urlFoto", "")).strip(),
            ))
        except Exception:
            continue
    deps = [x for x in deps if x.nome and x.id]
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    return deps, ts


# ═══════════════════════════════════════════
# Matching
# ═══════════════════════════════════════════

def build_index(deps: List[Dep]) -> Dict[str, Dep]:
    return {dep.key: dep for dep in deps}


def _suggest_similar(query_key: str, idx: Dict[str, Dep], top_n: int = 3) -> List[str]:
    words = set(query_key.split())
    scored: List[Tuple[int, str]] = []
    for key, dep in idx.items():
        score = sum(1 for w in words if w in key)
        if score > 0:
            scored.append((score, dep.nome))
    scored.sort(key=lambda x: -x[0])
    return [nome for _, nome in scored[:top_n]]


def match_assinantes(
    assinantes_raw: List[str],
    deps: List[Dep],
) -> Tuple[pd.DataFrame, List[Tuple[str, List[str]]]]:
    idx = build_index(deps)
    resolved = [ALIASES_OFICIAIS.get(normalize_name(n), n) for n in assinantes_raw]
    found: List[Dep] = []
    nao_encontrados: List[Tuple[str, List[str]]] = []
    seen_dep_ids: set = set()

    for n in resolved:
        k = normalize_name(n)
        if not k:
            continue
        dep = idx.get(k)
        if dep is None:
            k2 = PREFIX_STRIP_RE.sub("", k).strip()
            dep = idx.get(k2)
        if dep is None:
            nao_encontrados.append((n, _suggest_similar(k, idx)))
            continue
        if dep.id in seen_dep_ids:
            continue
        seen_dep_ids.add(dep.id)
        found.append(dep)

    df = pd.DataFrame([
        {"Foto": x.urlFoto, "Nome": x.nome, "Partido": x.siglaPartido, "UF": x.siglaUf, "ID": x.id}
        for x in found
    ])
    if not df.empty:
        df = df.sort_values("Nome").reset_index(drop=True)
    return df, nao_encontrados


def make_df_nao_assinou(deps: List[Dep], df_assinou: pd.DataFrame) -> pd.DataFrame:
    assinou_ids = set(df_assinou["ID"].tolist()) if not df_assinou.empty else set()
    rows = [
        {"Foto": d.urlFoto, "Nome": d.nome, "Partido": d.siglaPartido, "UF": d.siglaUf, "ID": d.id}
        for d in deps if d.id not in assinou_ids
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Nome").reset_index(drop=True)
    return df


def build_df_bancada(deps: List[Dep], df_assinou: pd.DataFrame) -> pd.DataFrame:
    assinou_ids = set(df_assinou["ID"].tolist()) if not df_assinou.empty else set()
    totais: Dict[str, int] = {}
    assinaram_ct: Dict[str, int] = {}
    for d in deps:
        p = d.siglaPartido or "?"
        totais[p] = totais.get(p, 0) + 1
        if d.id in assinou_ids:
            assinaram_ct[p] = assinaram_ct.get(p, 0) + 1
    rows = []
    for p, total in totais.items():
        assinou = assinaram_ct.get(p, 0)
        rows.append({
            "Partido": p,
            "Total na Câmara": total,
            "Assinaram": assinou,
            "Faltam": total - assinou,
            "% Adesão": round(assinou / total * 100, 1) if total > 0 else 0.0,
        })
    return pd.DataFrame(rows).sort_values("Assinaram", ascending=False).reset_index(drop=True)


# ═══════════════════════════════════════════
# Helpers visuais
# ═══════════════════════════════════════════

def render_kpi(label: str, value, css_class: str = "", sub: str = ""):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    st.markdown(f"""
    <div class="kpi-card {css_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_progress_bar(assinou: int, meta: int, total: int):
    pct = min(assinou / meta * 100, 100) if meta > 0 else 0
    if pct >= 100:
        color, pct_color = "linear-gradient(90deg,#059669,#10b981)", "#059669"
    elif pct >= 60:
        color, pct_color = "linear-gradient(90deg,#d97706,#f59e0b)", "#d97706"
    else:
        color, pct_color = "linear-gradient(90deg,#9b1c2e,#c53050)", "#9b1c2e"
    marker_pct = (meta / total * 100) if total > 0 else 50
    st.markdown(f"""
    <div class="progress-wrapper">
        <div class="progress-label-row">
            <span class="prog-title">Progresso para {meta} assinaturas (maioria absoluta — art. 155 RICD)</span>
            <span class="prog-pct" style="color:{pct_color}">{assinou}/{meta} ({pct:.1f}%)</span>
        </div>
        <div class="progress-track">
            <div class="progress-fill" style="width:{min(pct,100):.2f}%;background:{color};"></div>
            <div class="progress-marker" style="left:{marker_pct:.1f}%;">
                <span class="progress-marker-label">{meta}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_table(df: pd.DataFrame, search_text: str = ""):
    if df.empty:
        st.info("Nenhum deputado com os filtros aplicados.")
        return
    df_show = df.copy()
    if search_text.strip():
        mask = df_show.apply(
            lambda r: any(search_text.lower() in str(r[c]).lower() for c in ["Nome", "Partido", "UF"]),
            axis=1,
        )
        df_show = df_show[mask].reset_index(drop=True)
    if df_show.empty:
        st.info(f'Nenhum resultado para "{search_text}".')
        return
    st.data_editor(
        df_show, hide_index=True, disabled=True, use_container_width=True,
        column_config={
            "Foto":    st.column_config.ImageColumn("📷", help="Foto oficial — Câmara", width="large"),
            "Nome":    st.column_config.TextColumn("Nome", width="large"),
            "Partido": st.column_config.TextColumn("Partido", width="small"),
            "UF":      st.column_config.TextColumn("UF", width="small"),
            "ID":      None,
        },
    )
    st.caption(f"Exibindo {len(df_show)} deputado(s)")


def to_xlsx_multi(df_assinou: pd.DataFrame, df_nao_assinou: pd.DataFrame, df_bancada: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for df, sheet, cols in [
            (df_assinou,     "Assinaram",    ["Nome", "Partido", "UF"]),
            (df_nao_assinou, "Não Assinaram", ["Nome", "Partido", "UF"]),
            (df_bancada,     "Por Bancada",   ["Partido", "Total na Câmara", "Assinaram", "Faltam", "% Adesão"]),
        ]:
            df_exp = df[[c for c in cols if c in df.columns]] if not df.empty else pd.DataFrame(columns=cols)
            df_exp.to_excel(writer, index=False, sheet_name=sheet)
            ws = writer.sheets[sheet]
            for i, col in enumerate(df_exp.columns, 1):
                max_len = max(df_exp[col].astype(str).str.len().max() if not df_exp.empty else 0, len(col)) + 3
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max_len, 40)
    return buf.getvalue()


def plot_partido(df_assinou: pd.DataFrame) -> None:
    grouped = df_assinou.groupby("Partido").size().reset_index(name="Qtd")
    grouped = grouped.sort_values("Qtd", ascending=True).tail(15)
    if grouped.empty:
        st.info("Sem dados suficientes.")
        return
    fig, ax = plt.subplots(figsize=(6, max(3, len(grouped) * 0.45)))
    ax.barh(grouped["Partido"], grouped["Qtd"], color="#9b1c2e", height=0.65, edgecolor="none")
    for bar in ax.patches:
        w = bar.get_width()
        ax.text(w + 0.15, bar.get_y() + bar.get_height() / 2, f"{int(w)}", va="center", fontsize=8, fontweight="bold", color="#2c3e50")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def plot_uf(df_assinou: pd.DataFrame) -> None:
    grouped = df_assinou.groupby("UF").size().reset_index(name="Qtd").sort_values("Qtd", ascending=False)
    if grouped.empty:
        st.info("Sem dados suficientes.")
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(grouped["UF"], grouped["Qtd"], color="#c53050", width=0.65, edgecolor="none")
    for bar in ax.patches:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.15, f"{int(h)}", ha="center", va="bottom", fontsize=7, fontweight="bold", color="#2c3e50")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="x", labelsize=7, rotation=45)
    ax.tick_params(axis="y", labelsize=8)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def plot_oportunidade(df_bancada: pd.DataFrame) -> None:
    top = df_bancada.sort_values("Total na Câmara", ascending=False).head(15)
    top = top.sort_values("Assinaram", ascending=True)
    if top.empty:
        st.info("Sem dados suficientes.")
        return
    fig, ax = plt.subplots(figsize=(7, max(3, len(top) * 0.5)))
    ax.barh(top["Partido"], top["Assinaram"], color="#0d9668", height=0.65, edgecolor="none", label="Assinaram")
    ax.barh(top["Partido"], top["Faltam"], left=top["Assinaram"], color="#e5e7eb", height=0.65, edgecolor="none", label="Potencial restante")
    for _, row in top.iterrows():
        if row["Assinaram"] > 0:
            ax.text(row["Assinaram"] / 2, row["Partido"], str(int(row["Assinaram"])),
                    va="center", ha="center", fontsize=7, fontweight="bold", color="white")
        ax.text(row["Total na Câmara"] + 0.4, row["Partido"], f'{row["% Adesão"]:.0f}%',
                va="center", ha="left", fontsize=7, color="#6b7a8d")
    ax.set_xlim(0, top["Total na Câmara"].max() * 1.18)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.7)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


# ═══════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚡ Lista de Assinantes")
    st.caption(
        "Cole a lista do **Infoleg Autenticador** (campo 'Assinaturas do Documento') — "
        "um nome por linha."
    )
    assinantes_text = st.text_area(
        "Lista",
        value=ASSINANTES_RAW_DEFAULT,
        height=320,
        label_visibility="collapsed",
        placeholder="Cole a lista aqui…",
    )
    assinantes_list = parse_assinantes(assinantes_text)
    st.markdown(f"**{len(assinantes_list)}** nome(s) identificado(s)")

    st.divider()
    st.markdown("### ⚙️ Configuração")
    meta_custom = st.number_input(
        "Meta de assinaturas",
        min_value=1, max_value=513, value=META_DEFAULT,
        help="Art. 155 RICD exige maioria absoluta = 257.",
    )

    st.divider()
    if st.button("🔄 Atualizar dados da API", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Proposição:** PL 5.128/2025")
    st.markdown("**Código:** `CD263486371900`")
    st.caption("Fonte: [Dados Abertos — Câmara](https://dadosabertos.camara.leg.br)")


# ═══════════════════════════════════════════
# Carregar dados
# ═══════════════════════════════════════════

with st.spinner("Consultando deputados em exercício…"):
    deps, fetch_ts = fetch_deputados_em_exercicio()

df_assinou, nao_encontrados = match_assinantes(assinantes_list, deps)
df_nao_assinou = make_df_nao_assinou(deps, df_assinou)
df_bancada     = build_df_bancada(deps, df_assinou)

total_api    = len(deps)
assinou_n    = int(df_assinou.shape[0])
nao_assinou_n = total_api - assinou_n
faltam       = max(0, int(meta_custom) - assinou_n)
pct_meta     = (assinou_n / int(meta_custom) * 100) if meta_custom > 0 else 0
partidos_rep = int(df_assinou["Partido"].nunique()) if not df_assinou.empty else 0


# ═══════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════

st.markdown(f"""
<div class="hero-header">
    <div class="hero-badge">⚡ REQ DE URGÊNCIA — ART. 155 RICD</div>
    <h1>Monitor de Assinaturas — PL 5.128/2025</h1>
    <p>
        <strong>Falsas denúncias / Lei Maria da Penha</strong> &nbsp;·&nbsp;
        Autoria: Dep. Júlia Zanatta (PL/SC) &nbsp;·&nbsp;
        Código: CD263486371900
    </p>
    <p style="margin-top:0.5rem;opacity:0.7;font-size:0.82rem;">
        Meta: <strong>{int(meta_custom)} assinaturas</strong> (maioria absoluta) &nbsp;·&nbsp;
        Deputados em exercício: <strong>{total_api}</strong> &nbsp;·&nbsp;
        🕐 Dados da API: <strong>{fetch_ts}</strong>
    </p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# KPIs
# ═══════════════════════════════════════════

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    render_kpi("Assinaram", assinou_n, "kpi-green", f"de {total_api} em exercício")
with k2:
    render_kpi("Faltam p/ meta",
               faltam if faltam > 0 else "✓",
               "kpi-amber" if faltam > 0 else "kpi-green",
               f"meta: {int(meta_custom)}")
with k3:
    render_kpi("% da meta", f"{pct_meta:.1f}%", "kpi-crimson", f"{assinou_n} de {int(meta_custom)}")
with k4:
    render_kpi("Partidos", partidos_rep, "kpi-purple", "bancadas representadas")
with k5:
    render_kpi("Não assinaram", nao_assinou_n, "kpi-red",
               f"{(nao_assinou_n / total_api * 100):.0f}% da Câmara")


# ═══════════════════════════════════════════
# Progresso
# ═══════════════════════════════════════════

render_progress_bar(assinou_n, int(meta_custom), total_api)


# ═══════════════════════════════════════════
# Status banner
# ═══════════════════════════════════════════

if nao_encontrados:
    st.markdown(
        f'<div class="status-banner status-warn">⚠️ {len(nao_encontrados)} nome(s) não reconhecido(s) na base oficial — verifique o expander abaixo.</div>',
        unsafe_allow_html=True,
    )
elif assinou_n >= int(meta_custom):
    st.markdown('<div class="status-banner status-ok">✅ Meta atingida! Todos os nomes reconhecidos.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="status-banner status-ok">✅ Todos os nomes reconhecidos na base oficial.</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════
# Tabs principais
# ═══════════════════════════════════════════

st.markdown("---")

tab_vis, tab_assinou_t, tab_nao_assinou_t, tab_bancada_t = st.tabs([
    "📊 Visão Geral",
    f"✅ Assinaram ({assinou_n})",
    f"❌ Não assinaram ({nao_assinou_n})",
    "🎯 Por Bancada",
])

ufs      = sorted({d.siglaUf for d in deps if d.siglaUf})
partidos = sorted({d.siglaPartido for d in deps if d.siglaPartido})


# ─── Visão Geral ──────────────────────────────────────────────────────────────

with tab_vis:
    gc1, gc2 = st.columns(2)
    with gc1:
        st.markdown('<div class="chart-title">Assinaturas por Partido (top 15)</div>', unsafe_allow_html=True)
        plot_partido(df_assinou)
    with gc2:
        st.markdown('<div class="chart-title">Assinaturas por Estado</div>', unsafe_allow_html=True)
        plot_uf(df_assinou)


# ─── Assinaram ────────────────────────────────────────────────────────────────

with tab_assinou_t:
    fa1, fa2, fa3 = st.columns([2, 2, 3])
    with fa1:
        uf_sel_a = st.multiselect("UF", options=ufs, default=[], key="uf_assinou")
    with fa2:
        partido_sel_a = st.multiselect("Partido", options=partidos, default=[], key="part_assinou")
    with fa3:
        search_a = st.text_input("🔍 Buscar", key="search_assinou", placeholder="Nome, partido ou UF…")

    df_view_a = df_assinou.copy()
    if uf_sel_a:
        df_view_a = df_view_a[df_view_a["UF"].isin(uf_sel_a)]
    if partido_sel_a:
        df_view_a = df_view_a[df_view_a["Partido"].isin(partido_sel_a)]
    render_table(df_view_a.reset_index(drop=True), search_a)

    if not df_assinou.empty:
        st.download_button(
            "⬇️ Baixar relatório completo (Excel — 3 abas: Assinaram / Não Assinaram / Por Bancada)",
            data=to_xlsx_multi(df_assinou, df_nao_assinou, df_bancada),
            file_name="monitor_req_urgencia_maria_da_penha.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ─── Não assinaram ────────────────────────────────────────────────────────────

with tab_nao_assinou_t:
    fn1, fn2, fn3 = st.columns([2, 2, 3])
    with fn1:
        uf_sel_n = st.multiselect("UF", options=ufs, default=[], key="uf_nao_assinou")
    with fn2:
        partido_sel_n = st.multiselect("Partido", options=partidos, default=[], key="part_nao_assinou")
    with fn3:
        search_n = st.text_input("🔍 Buscar", key="search_nao_assinou", placeholder="Nome, partido ou UF…")

    df_view_n = df_nao_assinou.copy()
    if uf_sel_n:
        df_view_n = df_view_n[df_view_n["UF"].isin(uf_sel_n)]
    if partido_sel_n:
        df_view_n = df_view_n[df_view_n["Partido"].isin(partido_sel_n)]
    render_table(df_view_n.reset_index(drop=True), search_n)


# ─── Por Bancada ──────────────────────────────────────────────────────────────

with tab_bancada_t:
    st.markdown(
        "Visão estratégica por partido: quantos deputados cada bancada tem, quantos já assinaram "
        "e o potencial restante. Use para priorizar onde concentrar o esforço de coleta."
    )

    bc1, bc2 = st.columns([1, 1])

    with bc1:
        st.markdown('<div class="chart-title">Bancada: assinaram ✅ vs. potencial restante (top 15 por tamanho)</div>', unsafe_allow_html=True)
        plot_oportunidade(df_bancada)

    with bc2:
        st.markdown('<div class="chart-title">Tabela detalhada</div>', unsafe_allow_html=True)
        search_b = st.text_input("🔍 Filtrar partido", key="search_bancada", placeholder="Ex: PL, PT, UNIÃO…")
        df_b_view = df_bancada.copy()
        if search_b.strip():
            df_b_view = df_b_view[df_b_view["Partido"].str.contains(search_b.strip(), case=False)]

        st.dataframe(
            df_b_view.reset_index(drop=True),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Partido":         st.column_config.TextColumn("Partido", width="small"),
                "Total na Câmara": st.column_config.NumberColumn("Total", format="%d"),
                "Assinaram":       st.column_config.NumberColumn("✅ Assinaram", format="%d"),
                "Faltam":          st.column_config.NumberColumn("❌ Faltam", format="%d"),
                "% Adesão":        st.column_config.ProgressColumn(
                    "% Adesão", min_value=0, max_value=100, format="%.1f%%"
                ),
            },
        )
        st.caption(f"{len(df_b_view)} partido(s) exibido(s)")


# ═══════════════════════════════════════════
# Nomes não reconhecidos (com sugestões)
# ═══════════════════════════════════════════

if nao_encontrados:
    st.markdown("---")
    with st.expander(f"⚠️ Nomes não reconhecidos ({len(nao_encontrados)}) — sugestões de correção", expanded=True):
        st.markdown(
            "Esses nomes constam na lista mas não foram localizados entre os deputados em exercício. "
            "Podem ser senadores, ex-deputados, ou grafia diferente do nome parlamentar oficial. "
            "Para cada um são sugeridos os nomes mais próximos encontrados na API:"
        )
        for nome, sugestoes in nao_encontrados:
            sug_html = ""
            if sugestoes:
                sug_html = "  →  " + " / ".join(f"<code>{s}</code>" for s in sugestoes)
            st.markdown(
                f'<div class="alias-suggestion">❓ <strong>{nome}</strong>{sug_html}</div>',
                unsafe_allow_html=True,
            )
        st.caption(
            "Para corrigir: adicione o alias correto no dicionário ALIASES_OFICIAIS no topo do arquivo, "
            "ou ajuste o nome diretamente na lista colada na sidebar."
        )
