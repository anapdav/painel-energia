# Coletor FAOSTAT (ONU/FAO) — fertilizantes por nutriente, anual
# Bulk CSV oficial (a API REST estava instável na verificação de 23/07/2026).
# Foco: nitrogenados (N) — o elo fertilizante <-> gás natural (amônia).
import csv
import io
import zipfile

from curl_cffi import requests as cfr
URL = ("https://bulks-faostat.fao.org/production/"
       "Inputs_FertilizersNutrient_E_All_Data_(Normalized).zip")

PAISES = {
    "China": "cn", "India": "in", "United States of America": "us",
    "Russian Federation": "ru", "Brazil": "br", "Indonesia": "id",
    "Pakistan": "pk", "Canada": "ca", "Egypt": "eg", "Saudi Arabia": "sa",
    "Germany": "de", "France": "fr", "Nigeria": "ng", "Qatar": "qa",
}
ELEMENTOS = {"Production": ("prod", "Produção"),
             "Agricultural Use": ("uso", "Uso agrícola")}


def coleta(con, registra_serie, grava_dados, log=print):
    try:
        r = cfr.get(URL, impersonate="chrome", timeout=300)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        nome_csv = [n for n in zf.namelist() if n.endswith(".csv") and "Flag" not in n][0]
        texto = zf.read(nome_csv).decode("latin-1")
    except Exception as e:
        log(f"  [ERRO] fao: {type(e).__name__}: {e}")
        return
    series = {}
    for row in csv.DictReader(io.StringIO(texto)):
        if "nitrogen" not in row.get("Item", "").lower():
            continue
        cc = PAISES.get(row.get("Area", ""))
        el = ELEMENTOS.get(row.get("Element", ""))
        v = row.get("Value", "")
        if not cc or not el or not v:
            continue
        try:
            series.setdefault((cc, el[0]), []).append(
                (row["Year"] + "-01-01", float(v) / 1000.0))  # t -> mil t
        except ValueError:
            continue
    for (cc, el), pares in series.items():
        nome_el = dict(prod="Produção", uso="Uso agrícola")[el]
        sid = f"fao_n_{el}_{cc}"
        registra_serie(con, sid, "FAOSTAT", cc.upper(), "fertilizantes",
                       f"{nome_el} de fertilizantes nitrogenados (N) — {cc.upper()}",
                       "mil t N/ano", "anual", URL)
        grava_dados(con, sid, sorted(pares))
    ult = max((p[-1][0][:4] for p in series.values() if p), default="-")
    log(f"  fao_n: {len(series)} series | ultimo ano {ult}")
