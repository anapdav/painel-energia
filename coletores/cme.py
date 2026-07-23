# Coletor CME Group — futuros de petróleo direto da bolsa (atraso 10 min,
# declarado pela própria fonte no campo quoteDelay).
# Endpoint do site (não documentado): /CmeWS/mvc/quotes/v2/{productId}
#   WTI (CL) = 425 | Brent Last Day Financial (BZ) = 424
# PAREAMENTO: o front month do CL define o vencimento; o Brent cotado é o
# contrato BZ do MESMO mês (quoteCode ex.: CLU6 -> BZU6). Lição de 23/07/2026:
# contínuos de fontes redistribuidoras rolam em datas diferentes e invertem o
# spread — aqui o pareamento é explícito por código de contrato.
# Histórico: a série diária acumula um ponto por pregão (a API não fornece
# histórico); até 23/07/2026 os pontos vieram do Yahoo (mesmos dados CME
# redistribuídos) — emenda documentada na descrição da série.
import re
from datetime import datetime, timezone

from curl_cffi import requests as cfr

import db

MESES_EN = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05",
            "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10",
            "Nov": "11", "Dec": "12"}


def _quotes(pid):
    r = cfr.get(f"https://www.cmegroup.com/CmeWS/mvc/quotes/v2/{pid}",
                impersonate="chrome", timeout=60,
                headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _data_iso(trade_date):
    """'23 Jul 2026' -> '2026-07-23'"""
    d, m, a = trade_date.split()
    return f"{a}-{MESES_EN[m]}-{d.zfill(2)}"


def coleta(con, registra_serie, grava_dados, log=print):
    try:
        d_cl = _quotes(425)
    except Exception as e:
        log(f"  [ERRO] cme WTI: {type(e).__name__}: {e}")
        return
    atraso = d_cl.get("quoteDelay", "10 minutes")
    data = _data_iso(d_cl["tradeDate"])
    front = next((q for q in d_cl["quotes"] if q.get("isFrontMonth")),
                 d_cl["quotes"][0])
    cod = front["quoteCode"]                       # ex. CLU6
    sufixo_venc = cod[len("CL"):]                  # ex. U6

    try:
        d_bz = _quotes(424)
        q_bz = next((q for q in d_bz["quotes"]
                     if q["quoteCode"] == f"BZ{sufixo_venc}"), None)
    except Exception as e:
        log(f"  [ERRO] cme Brent: {type(e).__name__}: {e}")
        q_bz = None

    agora = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    for sid, q, nome in [("fut_wti", front, "WTI"), ("fut_brent", q_bz, "Brent")]:
        if q is None:
            log(f"  [AVISO] cme: contrato {nome} {sufixo_venc} não encontrado")
            continue
        valor = _num(q.get("last"))
        rotulo_fech = ""
        if valor is None or valor == 0:            # mercado fechado -> settle
            valor = _num(q.get("priorSettle"))
            rotulo_fech = " (settle anterior)"
        if valor is None:
            log(f"  [AVISO] cme {nome}: sem preço utilizável")
            continue
        registra_serie(con, sid, "CME", "mercado", "crude",
                       f"Futuro de {nome}, vencimento pareado pelo front month do "
                       f"WTI (CME, atraso {atraso}; até 23/07/2026 pontos via "
                       "Yahoo — mesmos dados CME redistribuídos)",
                       "USD/barril", "diaria",
                       "cmegroup.com /CmeWS/mvc/quotes/v2")
        grava_dados(con, sid, [(data, round(valor, 2))])
        db.grava_meta(con, f"{sid}_hora", agora)
        db.grava_meta(con, f"{sid}_contrato",
                      f"{nome} {q.get('expirationMonth', cod)}{rotulo_fech}")
        log(f"  {sid}: {valor} USD/b [{q['quoteCode']}] em {data}")
