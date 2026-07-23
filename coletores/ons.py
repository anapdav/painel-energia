# Coletor ONS (dados.ons.org.br) — CKAN + S3 público, sem autenticação
# Carga diária, EAR/ENA diários, geração por fonte (balanço horário -> diário), CMO semanal
import csv
import io
import json
import urllib.request
from collections import defaultdict
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SUBS = {"N": "n", "NE": "ne", "S": "s", "SE": "se"}
NOMES = {"n": "Norte", "ne": "Nordeste", "s": "Sul", "se": "Sudeste/CO"}


def _json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.load(r)


def _csvs(dataset, ano_min=None):
    """CSVs anuais do dataset (nome, url), filtrando por ano se pedido."""
    d = _json(f"https://dados.ons.org.br/api/3/action/package_show?id={dataset}")
    out = []
    for r in d["result"]["resources"]:
        if r["format"].upper() != "CSV":
            continue
        ano = None
        for tok in r["name"].replace("-", "_").split("_"):
            if tok.isdigit() and len(tok) == 4:
                ano = int(tok)
        if ano_min and ano and ano < ano_min:
            continue
        out.append((r["name"], r["url"]))
    return out


def _linhas(url):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8-sig", errors="replace")
    return csv.DictReader(io.StringIO(raw), delimiter=";")


def _tem_historico(con, sid):
    r = con.execute("SELECT MIN(data) FROM dados WHERE serie_id=?", (sid,)).fetchone()
    return r and r[0] and r[0] < f"{date.today().year - 1}-01-01"


def coleta(con, registra_serie, grava_dados, log=print):
    # incremental: se já há histórico, baixa só ano corrente e anterior
    ano_min = date.today().year - 1 if _tem_historico(con, "ons_carga_sin") else None
    if ano_min:
        log(f"  (incremental: só arquivos de {ano_min} em diante)")

    # --- 1) Carga diária por subsistema + SIN ---
    por_sub, por_dia = defaultdict(list), defaultdict(float)
    for nome, url in _csvs("carga-energia", ano_min):
        for row in _linhas(url):
            sub = SUBS.get(row["id_subsistema"].strip())
            if not sub or not row["val_cargaenergiamwmed"]:
                continue
            d, v = row["din_instante"][:10], float(row["val_cargaenergiamwmed"])
            por_sub[sub].append((d, v))
            por_dia[d] += v
    for sub, pares in por_sub.items():
        sid = f"ons_carga_{sub}"
        registra_serie(con, sid, "ONS", "BR", "eletricidade",
                       f"Carga de energia — {NOMES[sub]}", "MWmed", "diaria",
                       "dados.ons.org.br [carga-energia]")
        grava_dados(con, sid, pares)
    registra_serie(con, "ons_carga_sin", "ONS", "BR", "eletricidade",
                   "Carga de energia — SIN (soma dos subsistemas)", "MWmed", "diaria",
                   "dados.ons.org.br [carga-energia]")
    grava_dados(con, "ons_carga_sin", sorted(por_dia.items()))
    log(f"  ons_carga: {len(por_dia)} dias | ultima {max(por_dia) if por_dia else '-'}")

    # --- 2) EAR diário: % por subsistema + SIN (soma MWmês / soma max) ---
    ear_pct, ear_num, ear_den = defaultdict(list), defaultdict(float), defaultdict(float)
    for nome, url in _csvs("ear-diario-por-subsistema", ano_min):
        for row in _linhas(url):
            sub = SUBS.get(row["id_subsistema"].strip())
            if not sub or not row["ear_verif_subsistema_percentual"]:
                continue
            d = row["ear_data"][:10]
            ear_pct[sub].append((d, float(row["ear_verif_subsistema_percentual"])))
            ear_num[d] += float(row["ear_verif_subsistema_mwmes"] or 0)
            ear_den[d] += float(row["ear_max_subsistema"] or 0)
    for sub, pares in ear_pct.items():
        sid = f"ons_ear_{sub}_pct"
        registra_serie(con, sid, "ONS", "BR", "hidrologia",
                       f"EAR — energia armazenada, % do máximo — {NOMES[sub]}", "%",
                       "diaria", "dados.ons.org.br [ear-diario-por-subsistema]")
        grava_dados(con, sid, pares)
    sin = sorted((d, 100.0 * ear_num[d] / ear_den[d]) for d in ear_num if ear_den[d] > 0)
    registra_serie(con, "ons_ear_sin_pct", "ONS", "BR", "hidrologia",
                   "EAR — energia armazenada, % do máximo — SIN (agregado calculado)",
                   "%", "diaria", "dados.ons.org.br [ear-diario-por-subsistema]")
    grava_dados(con, "ons_ear_sin_pct", sin)
    log(f"  ons_ear: {len(sin)} dias | ultima {sin[-1][0] if sin else '-'}")

    # --- 3) ENA diário: % da MLT por subsistema ---
    ena = defaultdict(list)
    for nome, url in _csvs("ena-diario-por-subsistema", ano_min):
        for row in _linhas(url):
            sub = SUBS.get(row["id_subsistema"].strip())
            if not sub or not row["ena_bruta_regiao_percentualmlt"]:
                continue
            ena[sub].append((row["ena_data"][:10], float(row["ena_bruta_regiao_percentualmlt"])))
    for sub, pares in ena.items():
        sid = f"ons_ena_{sub}_pctmlt"
        registra_serie(con, sid, "ONS", "BR", "hidrologia",
                       f"ENA bruta — % da MLT — {NOMES[sub]}", "% MLT", "diaria",
                       "dados.ons.org.br [ena-diario-por-subsistema]")
        grava_dados(con, sid, pares)
    log(f"  ons_ena: {sum(len(p) for p in ena.values())} obs")

    # --- 4) Geração por fonte, SIN diário (balanço horário -> média do dia) ---
    fontes = {"val_gerhidraulica": "hidro", "val_gertermica": "termica",
              "val_gereolica": "eolica", "val_gersolar": "solar"}
    soma_h = defaultdict(float)          # (dia, fonte, hora) -> soma entre subsistemas
    for nome, url in _csvs("balanco-energia-subsistema", ano_min):
        for row in _linhas(url):
            if not SUBS.get(row["id_subsistema"].strip()):
                continue
            dh = row["din_instante"]
            for col, fonte in fontes.items():
                if row.get(col):
                    soma_h[(dh[:10], fonte, dh[11:13])] += float(row[col])
    acum = defaultdict(lambda: [0.0, 0])  # (dia, fonte) -> [soma, n_horas]
    for (d, fonte, _h), v in soma_h.items():
        acum[(d, fonte)][0] += v
        acum[(d, fonte)][1] += 1
    ger = defaultdict(list)
    for (d, fonte), (s, n) in acum.items():
        ger[fonte].append((d, s / n))
    for fonte, pares in ger.items():
        sid = f"ons_ger_{fonte}"
        registra_serie(con, sid, "ONS", "BR", "eletricidade",
                       f"Geração {fonte} — SIN (média diária do balanço horário)",
                       "MWmed", "diaria", "dados.ons.org.br [balanco-energia-subsistema]")
        grava_dados(con, sid, sorted(pares))
    log(f"  ons_ger: {len(ger)} fontes | ultima {max(d for d, _ in ger['hidro']) if ger else '-'}")

    # --- 5) CMO semanal por subsistema ---
    cmo = defaultdict(list)
    for nome, url in _csvs("cmo-semanal", ano_min):
        for row in _linhas(url):
            sub = SUBS.get(row["id_subsistema"].strip())
            if not sub or not row["val_cmomediasemanal"]:
                continue
            cmo[sub].append((row["din_instante"][:10], float(row["val_cmomediasemanal"])))
    for sub, pares in cmo.items():
        sid = f"ons_cmo_{sub}"
        registra_serie(con, sid, "ONS", "BR", "eletricidade",
                       f"CMO médio semanal — {NOMES[sub]}", "R$/MWh", "semanal",
                       "dados.ons.org.br [cmo-semanal]")
        grava_dados(con, sid, pares)
    log(f"  ons_cmo: {sum(len(p) for p in cmo.values())} obs")
