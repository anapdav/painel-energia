# Coletor Eurostat — gás natural consumido pelo setor químico/petroquímico
# (nrg_bal_c, anual; inclui amônia/fertilizantes, sem desagregação além disso).
# API de disseminação, sem chave.
import json
import urllib.request

GEOS = ["DE", "NL", "FR", "IT", "ES", "PL", "BE", "EU27_2020"]
NOMES = {"DE": "Alemanha", "NL": "Holanda", "FR": "França", "IT": "Itália",
         "ES": "Espanha", "PL": "Polônia", "BE": "Bélgica", "EU27_2020": "UE-27"}


def coleta(con, registra_serie, grava_dados, log=print):
    for geo in GEOS:
        url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
               "data/nrg_bal_c?format=JSON&nrg_bal=FC_IND_CPC_E&siec=G3000"
               f"&unit=GWH&geo={geo}")
        try:
            d = json.load(urllib.request.urlopen(url, timeout=120))
            anos = list(d["dimension"]["time"]["category"]["index"].keys())
            pares = [(f"{anos[int(i)]}-01-01", float(v) / 1000.0)  # GWh -> TWh
                     for i, v in d["value"].items()]
        except Exception as e:
            log(f"  [ERRO] euro_gas_quimica_{geo.lower()}: {type(e).__name__}: {e}")
            continue
        sid = f"euro_gas_quimica_{geo.lower().replace('27_2020', '27')}"
        registra_serie(con, sid, "Eurostat", geo, "gas_natural",
                       f"Gás natural no setor químico/petroquímico — {NOMES[geo]} "
                       "(consumo final; inclui amônia/fertilizantes)",
                       "TWh/ano", "anual", "nrg_bal_c [FC_IND_CPC_E/G3000]")
        grava_dados(con, sid, sorted(pares))
        log(f"  {sid}: {len(pares)} anos | ultimo {max(p[0][:4] for p in pares) if pares else '-'}")
