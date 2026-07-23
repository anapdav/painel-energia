# Coletor CFTC — Commitments of Traders, Disaggregated Futures Only (Socrata)
# Dataset 72hh-3qpy, sem autenticação. Dado de terça, divulgado sexta à tarde ET.
import json
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

# (codigo CFTC, prefixo serie_id, produto, nome)
CONTRATOS = [
    ("067651", "wti", "crude", "WTI-PHYSICAL (NYMEX)"),
    ("023651", "gas", "gas_natural", "NAT GAS NYME (Henry Hub, NYMEX)"),
]


def _fetch(codigo):
    campos = ("report_date_as_yyyy_mm_dd,m_money_positions_long_all,"
              "m_money_positions_short_all,open_interest_all")
    linhas, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "$select": campos,
            "$where": f"cftc_contract_market_code='{codigo}'",
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": 5000, "$offset": offset,
        })
        req = urllib.request.Request(f"{BASE}?{q}", headers=UA)
        lote = json.load(urllib.request.urlopen(req, timeout=120))
        linhas.extend(lote)
        if len(lote) < 5000:
            return linhas
        offset += 5000


def coleta(con, registra_serie, grava_dados, log=print):
    for codigo, pref, produto, nome in CONTRATOS:
        try:
            linhas = _fetch(codigo)
        except Exception as e:
            log(f"  [ERRO] cftc_{pref}: {type(e).__name__}: {e}")
            continue
        net, oi = [], []
        for r in linhas:
            d = r["report_date_as_yyyy_mm_dd"][:10]
            try:
                net.append((d, float(r["m_money_positions_long_all"])
                            - float(r["m_money_positions_short_all"])))
                oi.append((d, float(r["open_interest_all"])))
            except (KeyError, TypeError, ValueError):
                continue
        registra_serie(con, f"cftc_{pref}_mm_net", "CFTC", "US", produto,
                       f"Managed money net (long-short) — {nome}, futures only",
                       "contratos", "semanal", f"publicreporting.cftc.gov [{codigo}]")
        grava_dados(con, f"cftc_{pref}_mm_net", net)
        registra_serie(con, f"cftc_{pref}_oi", "CFTC", "US", produto,
                       f"Open interest total — {nome}, futures only",
                       "contratos", "semanal", f"publicreporting.cftc.gov [{codigo}]")
        grava_dados(con, f"cftc_{pref}_oi", oi)
        log(f"  cftc_{pref}: {len(net)} semanas | ultima {net[-1][0] if net else '-'}")
