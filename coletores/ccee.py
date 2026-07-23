# Coletor CCEE (dadosabertos.ccee.org.br) — PLD média diária (2021+) e mensal (2001+)
# WAF barra clientes não-browser (fingerprint TLS) -> curl_cffi impersonate="chrome".
# URLs de download são tokenizadas: sempre descobrir via API, nunca hardcodar.
import csv
import io

from curl_cffi import requests as cfr

SUBMERCADOS = {"SUDESTE": "se", "SUDESTE/CENTRO-OESTE": "se", "SUL": "s",
               "NORDESTE": "ne", "NORTE": "n"}
NOMES = {"se": "Sudeste/CO", "s": "Sul", "ne": "Nordeste", "n": "Norte"}


def _get(url):
    r = cfr.get(url, impersonate="chrome", timeout=120)
    r.raise_for_status()
    return r


def _recursos(dataset):
    r = _get(f"https://dadosabertos.ccee.org.br/api/3/action/package_show?id={dataset}")
    return [(x["name"], x["url"]) for x in r.json()["result"]["resources"]
            if x["format"].upper() == "CSV"]


def _linhas(url):
    raw = _get(url).content
    texto = raw.decode("utf-8-sig", errors="strict") if raw[:3] == b"\xef\xbb\xbf" \
        else raw.decode("latin-1")
    return csv.DictReader(io.StringIO(texto), delimiter=";")


def _data_iso(dia_ddmmyyyy):
    d, m, a = dia_ddmmyyyy.split("/")
    return f"{a}-{m.zfill(2)}-{d.zfill(2)}"


def coleta(con, registra_serie, grava_dados, log=print):
    # --- PLD média diária por submercado (horário existe desde 2021) ---
    diario = {}
    for nome, url in _recursos("pld_media_diaria"):
        for row in _linhas(url):
            sub = SUBMERCADOS.get(row["SUBMERCADO"].strip().upper())
            if not sub or not row.get("PLD_MEDIA_DIA"):
                continue
            diario.setdefault(sub, []).append(
                (_data_iso(row["DIA"]), float(row["PLD_MEDIA_DIA"].replace(",", "."))))
    for sub, pares in diario.items():
        sid = f"ccee_pld_dia_{sub}"
        registra_serie(con, sid, "CCEE", "BR", "eletricidade",
                       f"PLD média diária — {NOMES[sub]}", "R$/MWh", "diaria",
                       "dadosabertos.ccee.org.br [pld_media_diaria]")
        grava_dados(con, sid, sorted(pares))
    ult = max(max(d for d, _ in p) for p in diario.values()) if diario else "-"
    log(f"  ccee_pld_dia: {sum(len(p) for p in diario.values())} obs | ultima {ult}")

    # --- PLD média mensal por submercado (2001+, inclui era pré-horária) ---
    mensal = {}
    for nome, url in _recursos("pld_media_mensal"):
        for row in _linhas(url):
            sub = SUBMERCADOS.get((row.get("SUBMERCADO") or "").strip().upper())
            if not sub:
                continue
            col_valor = next((c for c in row if c and c.startswith("PLD_MEDIA")), None)
            mes = (row.get("MES_REFERENCIA") or "").strip()
            if not col_valor or not row[col_valor] or len(mes) != 6:
                continue
            data = f"{mes[:4]}-{mes[4:6]}-01"
            mensal.setdefault(sub, []).append((data, float(row[col_valor].replace(",", "."))))
    for sub, pares in mensal.items():
        sid = f"ccee_pld_mes_{sub}"
        registra_serie(con, sid, "CCEE", "BR", "eletricidade",
                       f"PLD média mensal — {NOMES[sub]}", "R$/MWh", "mensal",
                       "dadosabertos.ccee.org.br [pld_media_mensal]")
        grava_dados(con, sid, sorted(pares))
    log(f"  ccee_pld_mes: {sum(len(p) for p in mensal.values())} obs")
