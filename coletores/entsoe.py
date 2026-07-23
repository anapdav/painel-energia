# Coletor ENTSO-E Transparency Platform (API RESTful R3)
# Endpoint: https://web-api.tp.entsoe.eu/api | token no .env (ENTSOE_TOKEN)
# Limites (guia oficial 23/07/2026): 400 req/min por token; máx 1 ano por request
# p/ A44 (preços day-ahead) e A75/16.1.B-C (geração agregada por tipo); timeout 300s.
# XML: resolução PT15M (mercado migrou p/ 15 min em 2025) e curveType A03
# (posições repetidas são OMITIDAS -> preencher com o último valor).
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import ENTSOE_TOKEN

API = "https://web-api.tp.entsoe.eu/api"
CET = ZoneInfo("Europe/Paris")  # todas as zonas coletadas são CET/CEST

ZONAS_PRECO = [  # (sufixo, EIC, nome)
    ("fr", "10YFR-RTE------C", "França"),
    ("es", "10YES-REE------0", "Espanha"),
    ("itn", "10Y1001A1001A73I", "Itália Norte"),
    ("nl", "10YNL----------L", "Holanda"),
    ("pl", "10YPL-AREA-----S", "Polônia"),
]
PAISES_GERACAO = [
    ("fr", "10YFR-RTE------C", "França"),
    ("es", "10YES-REE------0", "Espanha"),
    ("it", "10YIT-GRTN-----B", "Itália"),
    ("pl", "10YPL-AREA-----S", "Polônia"),
]
# psrType -> grupo de fonte (mesma taxonomia do painel SMARD)
PSR_GRUPO = {
    "B01": "biomassa", "B02": "carvao", "B03": "carvao", "B04": "gas",
    "B05": "carvao", "B06": "outros", "B07": "outros", "B08": "outros",
    "B09": "outros", "B10": "hidro", "B11": "hidro", "B12": "hidro",
    "B13": "outros", "B14": "nuclear", "B15": "outros", "B16": "solar",
    "B17": "outros", "B18": "eolica", "B19": "eolica", "B20": "outros",
}
ANO_INI_PRECO, ANO_INI_GER = 2015, 2018


def _consulta(params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API}?securityToken={ENTSOE_TOKEN}&{q}"
    raw = urllib.request.urlopen(url, timeout=300).read()
    time.sleep(0.3)  # folga ampla sob o limite de 400 req/min
    root = ET.fromstring(raw)
    if "Acknowledgement" in root.tag:
        ns = {"n": root.tag.split("}")[0].strip("{")}
        raise RuntimeError(root.findtext(".//n:Reason/n:text", namespaces=ns)
                           or "request rejeitado")
    return root


def _pontos(root, campo):
    """Expande TimeSeries/Period em (dt_utc, valor, horas_do_intervalo, psr).
    Trata curveType A03 preenchendo posições omitidas com o último valor."""
    ns = {"n": root.tag.split("}")[0].strip("{")}
    for ts in root.findall("n:TimeSeries", ns):
        if ts.find("n:outBiddingZone_Domain.mRID", ns) is not None:
            continue  # A75: série de consumo (bombeamento), não geração
        psr = ts.findtext(".//n:MktPSRType/n:psrType", namespaces=ns)
        curva = ts.findtext("n:curveType", namespaces=ns) or "A01"
        for per in ts.findall("n:Period", ns):
            ini = datetime.fromisoformat(
                per.findtext("n:timeInterval/n:start", namespaces=ns)
                .replace("Z", "+00:00"))
            fim = datetime.fromisoformat(
                per.findtext("n:timeInterval/n:end", namespaces=ns)
                .replace("Z", "+00:00"))
            res = per.findtext("n:resolution", namespaces=ns)
            minutos = {"PT15M": 15, "PT30M": 30, "PT60M": 60, "P1D": 1440}.get(res)
            if not minutos:
                continue
            n_pos = int((fim - ini).total_seconds() // (minutos * 60))
            vals = {}
            for p in per.findall("n:Point", ns):
                pos = int(p.findtext("n:position", namespaces=ns))
                v = p.findtext(f"n:{campo}", namespaces=ns)
                if v is not None:
                    vals[pos] = float(v)
            ultimo = None
            for pos in range(1, n_pos + 1):
                if pos in vals:
                    ultimo = vals[pos]
                elif curva != "A03":
                    continue  # A01: ponto faltante é faltante, não repete
                if ultimo is None:
                    continue
                yield (ini + timedelta(minutes=minutos * (pos - 1)),
                       ultimo, minutos / 60.0, psr)


def _consulta_robusta(params, ini, fim, log, rotulo):
    """Consulta a janela; em erro 5xx/timeout divide ao meio (mín. ~46 dias).
    Devolve lista de roots XML (um por subjanela que respondeu)."""
    try:
        return [_consulta({**params, "periodStart": _fmt(ini),
                           "periodEnd": _fmt(fim)})]
    except Exception as e:
        if (fim - ini).days <= 46:
            log(f"  [AVISO] {rotulo} {ini}..{fim}: {type(e).__name__}: {e}")
            return []
        meio = ini + (fim - ini) / 2
        return (_consulta_robusta(params, ini, meio, log, rotulo)
                + _consulta_robusta(params, meio, fim, log, rotulo))


def _janelas(con, sid_sentinela, ano_ini):
    """Backfill anual completo na 1ª carga; depois só últimos 45 dias."""
    r = con.execute("SELECT MIN(data) FROM dados WHERE serie_id=?",
                    (sid_sentinela,)).fetchone()
    hoje = date.today()
    if r and r[0] and r[0] <= f"{ano_ini + 1}-12-31":
        return [(hoje - timedelta(days=45), hoje + timedelta(days=2))]
    return [(date(a, 1, 1), date(a + 1, 1, 1))
            for a in range(ano_ini, hoje.year + 1)]


def _fmt(d):
    return d.strftime("%Y%m%d") + "0000"


def coleta(con, registra_serie, grava_dados, log=print):
    if not ENTSOE_TOKEN:
        log("  [ERRO] entsoe: ENTSOE_TOKEN ausente no .env")
        return

    # --- 1) Preços day-ahead (A44), média diária simples dos intervalos ---
    for suf, eic, nome in ZONAS_PRECO:
        sid = f"entsoe_preco_da_{suf}"
        acum = defaultdict(list)
        for ini, fim in _janelas(con, sid, ANO_INI_PRECO):
            for root in _consulta_robusta(
                    {"documentType": "A44", "in_Domain": eic, "out_Domain": eic},
                    ini, fim, log, sid):
                for dt, v, _h, _psr in _pontos(root, "price.amount"):
                    acum[dt.astimezone(CET).date().isoformat()].append(v)
        pares = sorted((d, sum(vs) / len(vs)) for d, vs in acum.items())
        registra_serie(con, sid, "ENTSOE", suf.upper(), "eletricidade",
                       f"Preço day-ahead — {nome} (média diária dos intervalos, dia CET)",
                       "EUR/MWh", "diaria", f"web-api.tp.entsoe.eu A44 [{eic}]")
        grava_dados(con, sid, pares)
        log(f"  {sid}: {len(pares)} dias | ultima {pares[-1][0] if pares else '-'}")

    # --- 2) Geração agregada por tipo (A75, processType A16 = realizado) ---
    for suf, eic, nome in PAISES_GERACAO:
        sentinela = f"entsoe_ger_{suf}_hidro"
        energia = defaultdict(float)   # (dia, grupo) -> MWh
        for ini, fim in _janelas(con, sentinela, ANO_INI_GER):
            for root in _consulta_robusta(
                    {"documentType": "A75", "processType": "A16", "in_Domain": eic},
                    ini, fim, log, f"entsoe_ger_{suf}"):
                for dt, mw, horas, psr in _pontos(root, "quantity"):
                    grupo = PSR_GRUPO.get(psr)
                    if grupo:
                        dia = dt.astimezone(CET).date().isoformat()
                        energia[(dia, grupo)] += mw * horas
        por_grupo = defaultdict(list)
        for (dia, grupo), mwh in energia.items():
            por_grupo[grupo].append((dia, mwh))
        for grupo, pares in por_grupo.items():
            sid = f"entsoe_ger_{suf}_{grupo}"
            registra_serie(con, sid, "ENTSOE", suf.upper(), "eletricidade",
                           f"Geração {grupo} — {nome} (soma diária, dia CET)",
                           "MWh/dia", "diaria", f"web-api.tp.entsoe.eu A75 [{eic}]")
            grava_dados(con, sid, sorted(pares))
        ult = max((d for d, _ in energia), default="-")
        log(f"  entsoe_ger_{suf}: {len(por_grupo)} grupos | ultima {ult}")
