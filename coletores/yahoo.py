# Coletor Yahoo Finance — futuros de petróleo, intradiário
# ATENÇÃO DE ROTULAGEM: cotação de MERCADO via API não-oficial do Yahoo
# (query1.finance.yahoo.com), atraso típico ~15 min. Não é fonte primária
# regulatória — usar para acompanhamento intraday; a série oficial segue EIA.
#
# PAREAMENTO DE VENCIMENTOS (lição de 23/07/2026): o contínuo BZ=F rola de
# contrato dias antes do CL=F e pode ficar defasado — comparar WTI e Brent de
# meses diferentes inverte o spread. Regra: descobrir o vencimento do CL=F e
# cotar o Brent do MESMO mês via ticker explícito (BZ{cod}{aa}.NYM).
import json
import re
import urllib.request
from datetime import datetime, timezone

import db

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MES_CODIGO = {"Jan": "F", "Feb": "G", "Mar": "H", "Apr": "J", "May": "K",
              "Jun": "M", "Jul": "N", "Aug": "Q", "Sep": "U", "Oct": "V",
              "Nov": "X", "Dec": "Z"}


def _chart(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=6mo&interval=1d"
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=60))
    return d["chart"]["result"][0]


def _grava(con, registra_serie, grava_dados, log, sid, r, desc):
    ts, closes = r["timestamp"], r["indicators"]["quote"][0]["close"]
    pares = [(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
              round(float(v), 2)) for t, v in zip(ts, closes) if v is not None]
    meta = r["meta"]
    atual, t_atual = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if atual is not None and t_atual:
        dt = datetime.fromtimestamp(t_atual, tz=timezone.utc).astimezone()
        pares.append((dt.date().isoformat(), round(float(atual), 2)))
        db.grava_meta(con, f"{sid}_hora", dt.strftime("%d/%m/%Y %H:%M"))
        db.grava_meta(con, f"{sid}_contrato", meta.get("shortName", ""))
    registra_serie(con, sid, "Yahoo", "mercado", "crude", desc,
                   "USD/barril", "diaria", f"query1.finance.yahoo.com [{meta.get('symbol')}]")
    grava_dados(con, sid, sorted(set(pares)))
    log(f"  {sid}: {atual} USD/b [{meta.get('shortName','')}]")


def coleta(con, registra_serie, grava_dados, log=print):
    # 1) WTI: contínuo CL=F (1º vencimento) — extrai o mês do contrato
    try:
        r_cl = _chart("CL=F")
    except Exception as e:
        log(f"  [ERRO] yahoo_wti_fut: {type(e).__name__}: {e}")
        return
    _grava(con, registra_serie, grava_dados, log, "yahoo_wti_fut", r_cl,
           "WTI futuro 1º venc. (NYMEX via Yahoo Finance, ~15min atraso)")

    # 2) Brent: contrato do MESMO mês do WTI (ticker explícito)
    nome = r_cl["meta"].get("shortName", "")           # ex. "Crude Oil Sep 26"
    m = re.search(r"([A-Z][a-z]{2}) (\d{2})$", nome)
    sym_bz = "BZ=F"
    if m and m.group(1) in MES_CODIGO:
        sym_bz = f"BZ{MES_CODIGO[m.group(1)]}{m.group(2)}.NYM"
    try:
        r_bz = _chart(sym_bz)
    except Exception as e:
        log(f"  [AVISO] {sym_bz} indisponível ({type(e).__name__}); usando BZ=F contínuo")
        r_bz = _chart("BZ=F")
    _grava(con, registra_serie, grava_dados, log, "yahoo_brent_fut", r_bz,
           "Brent futuro pareado com o vencimento do WTI (via Yahoo, ~15min atraso)")
    # shortName dos contratos BZ não traz o mês -> rotular com o mês pareado
    if m:
        db.grava_meta(con, "yahoo_brent_fut_contrato",
                      f"Brent {m.group(1)} {m.group(2)} (pareado c/ WTI)")
