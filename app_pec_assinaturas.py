# app_pec_assinaturas_api_v2.py
# Streamlit - Painel de assinaturas PEC (Assinou x Não assinou)
# Fonte de deputados em exercício: API Dados Abertos da Câmara (sem Excel)
# Matching robusto: strict -> loose -> heurística por tokens (apelido/título)
#
# Requisitos:
#   pip install streamlit pandas requests unidecode
#
# Rodar:
#   streamlit run app_pec_assinaturas_api_v2.py

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
import streamlit as st
from unidecode import unidecode


# =========================
# CONFIG
# =========================
META_ASSINATURAS = 171
API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
TIMEOUT = 30

# Cole a lista que a Câmara exibe (um por linha). Pode vir com "Subscritor"/"Coautoria".
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

# Linhas lixo administrativas
BLACKLIST_LINES = {
    "subscritor",
    "coautoria deputado(s)",
    "coautoria deputados",
    "coautoria deputadas",
    "coautoria",
}

# Prefixos/títulos comuns
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

# Sufixos comuns
SUFIXOS = {
    "junior", "júnior", "jr", "jr.",
    "filho", "neto",
    "pai",
}

# Stopwords de ligação (não ajudam no match)
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
    while out and out[0] in {norm_basic(t) for t in TITULOS_PREFIXO}:
        out = out[1:]
    return out


def strip_suffixes(tok: List[str]) -> List[str]:
    out = tok[:]
    while out and out[-1] in {norm_basic(t) for t in SUFIXOS}:
        out = out[:-1]
    return out


def norm_strict_name(s: str) -> str:
    return norm_basic(s)


def norm_loose_name(s: str) -> str:
    # remove títulos no começo + sufixos no fim + stopwords
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
        if pagina > 30:
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
# Heurística forte p/ apelidos
# =========================
def token_set_similarity(a_tokens: List[str], b_tokens: List[str]) -> float:
    """Jaccard simples em tokens (0..1)."""
    sa, sb = set(a_tokens), set(b_tokens)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def nickname_firstname_score(a: str, b: str) -> float:
    """
    Score leve para primeiros nomes parecidos (paulinho ~ paulo).
    Usa prefixo de 3 letras e distância simples.
    """
    a = norm_basic(a)
    b = norm_basic(b)
    if not a or not b:
        return 0.0
    # prefixo 3
    pa = a[:3]
    pb = b[:3]
    return 1.0 if pa == pb else 0.0


def best_fuzzy_candidate(
    signer: str,
    df_dep: pd.DataFrame,
    min_score: float = 0.55,
    min_margin: float = 0.10,
) -> Tuple[Optional[int], float]:
    """
    Encontra melhor candidato por heurística token-set.
    Aceita somente se:
      - score >= min_score
      - diferença para o 2º colocado >= min_margin
    Também exige que o ÚLTIMO sobrenome bata (ex.: freire, ramagem, telhada, waiapi).
    """
    s_tok = tokens(signer)
    s_tok = strip_prefix_titles(s_tok)
    s_tok = strip_suffixes(s_tok)
    if not s_tok:
        return None, 0.0

    s_last = s_tok[-1]  # sobrenome final do assinante (muito informativo)

    best_i = None
    best = -1.0
    second = -1.0

    for i, row in df_dep.iterrows():
        cand_name = row["nome"]
        c_tok = tokens(cand_name)
        c_last = c_tok[-1] if c_tok else ""

        # regra dura: último sobrenome deve bater
        if not c_last or c_last != s_last:
            continue

        score = token_set_similarity(s_tok, c_tok)

        # bô
