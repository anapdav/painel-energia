# Coletor IEA — Monthly Electricity Statistics, agregado "IEA Total" (GWh)
# ATENÇÃO: usa a API que alimenta o site (api.iea.org), NÃO documentada
# oficialmente — pode mudar sem aviso (o CSV oficial migra p/ SDMX em ago/2026).
# Cobertura: países-membros da IEA (não é o mundo inteiro — rotulado).
import json
import urllib.request
from collections import defaultdict

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
URL = "https://api.iea.org/mes?COUNTRY=IEA%20Total"

# produto IEA -> grupo (mesma taxonomia dos painéis SMARD/ENTSO-E)
PRODUTO_GRUPO = {
    "Coal": "carvao", "Natural gas": "gas", "Nuclear": "nuclear",
    "Hydro": "hidro", "Wind": "eolica", "Solar": "solar",
    "Combustible renewables": "biomassa",
    "Oil": "outros", "Geothermal": "outros", "Other renewables": "outros",
    "Other combustible non-renewables": "outros", "Not specified": "outros",
}


def coleta(con, registra_serie, grava_dados, log=print):
    try:
        linhas = json.load(urllib.request.urlopen(
            urllib.request.Request(URL, headers=UA), timeout=120))
    except Exception as e:
        log(f"  [ERRO] iea: {type(e).__name__}: {e}")
        return
    acum = defaultdict(float)
    for r in linhas:
        grupo = PRODUTO_GRUPO.get(r.get("PRODUCT"))
        ano, mes, v = r.get("YEAR"), r.get("MONTH"), r.get("VALUE")
        if grupo and ano and mes and v is not None:
            acum[(f"{ano}-{mes:02d}-01", grupo)] += float(v)
    por_grupo = defaultdict(list)
    for (data, grupo), v in acum.items():
        por_grupo[grupo].append((data, v))
    for grupo, pares in por_grupo.items():
        sid = f"iea_ger_ieatotal_{grupo}"
        registra_serie(con, sid, "IEA", "IEA", "eletricidade",
                       f"Geração elétrica {grupo} — agregado IEA Total (países-membros; "
                       "MES via api do site, não documentada)", "GWh/mês", "mensal", URL)
        grava_dados(con, sid, sorted(pares))
    ult = max((d for d, _ in acum), default="-")
    n = sum(len(p) for p in por_grupo.values())
    log(f"  iea_ger_ieatotal: {len(por_grupo)} grupos, {n} obs | ultimo mes {ult}")
