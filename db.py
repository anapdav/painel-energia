# Banco de séries do pipeline Energia — formato longo, uma linha por (série, data)
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    serie_id   TEXT PRIMARY KEY,
    fonte      TEXT NOT NULL,      -- EIA, AGSI, SMARD, ONS, CCEE, JODI...
    area       TEXT NOT NULL,      -- US, EU, DE, BR, IN, mundo...
    produto    TEXT NOT NULL,      -- crude, gas_natural, eletricidade, gnl...
    descricao  TEXT NOT NULL,
    unidade    TEXT NOT NULL,
    freq       TEXT NOT NULL,      -- diaria, semanal, mensal
    url_fonte  TEXT
);
CREATE TABLE IF NOT EXISTS dados (
    serie_id    TEXT NOT NULL,
    data        TEXT NOT NULL,     -- ISO: YYYY-MM-DD (mensal = dia 01)
    valor       REAL,
    coletado_em TEXT NOT NULL,
    PRIMARY KEY (serie_id, data)
);
CREATE INDEX IF NOT EXISTS idx_dados_data ON dados(data);
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def grava_meta(con, chave, valor):
    con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (chave, str(valor)))


def le_meta(con, chave, padrao=None):
    r = con.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
    return r[0] if r else padrao


def conecta():
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    return con


def registra_serie(con, serie_id, fonte, area, produto, descricao, unidade, freq, url_fonte=None):
    con.execute(
        "INSERT OR REPLACE INTO series VALUES (?,?,?,?,?,?,?,?)",
        (serie_id, fonte, area, produto, descricao, unidade, freq, url_fonte),
    )


def grava_dados(con, serie_id, pares):
    """pares = iterável de (data_iso, valor). Substitui revisões (INSERT OR REPLACE)."""
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    con.executemany(
        "INSERT OR REPLACE INTO dados VALUES (?,?,?,?)",
        [(serie_id, d, v, agora) for d, v in pares],
    )


def resumo(con):
    """(serie_id, descricao, n, primeira, ultima, ultimo_valor) por série."""
    sql = """
    SELECT s.serie_id, s.descricao, s.unidade, COUNT(d.data), MIN(d.data), MAX(d.data),
           (SELECT valor FROM dados WHERE serie_id = s.serie_id ORDER BY data DESC LIMIT 1)
    FROM series s LEFT JOIN dados d ON d.serie_id = s.serie_id
    GROUP BY s.serie_id ORDER BY s.serie_id
    """
    return con.execute(sql).fetchall()
