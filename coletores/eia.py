# Coletor EIA (API v2) — petróleo e gás natural EUA
# Doc: https://www.eia.gov/opendata/documentation.php
# Atenção: desde jan/2024 a API devolve valores numéricos como STRING.
import json
import urllib.request

from config import EIA_API_KEY

# (serie_id_local, rota, id_serie_eia, freq_eia, area, produto, descricao, unidade)
SERIES = [
    # --- Bloco óleo & gás EUA: estoques semanais (WPSR, quarta 10:30 ET) ---
    ("eia_crude_estoque_us", "petroleum/stoc/wstk", "WCESTUS1", "weekly",
     "US", "crude", "Estoques de crude EUA ex-SPR (WPSR)", "mil barris"),
    ("eia_crude_estoque_cushing", "petroleum/stoc/wstk", "W_EPC0_SAX_YCUOK_MBBL", "weekly",
     "US", "crude", "Estoques de crude em Cushing, OK ex-SPR (WPSR)", "mil barris"),
    ("eia_crude_estoque_spr", "petroleum/stoc/wstk", "WCSSTUS1", "weekly",
     "US", "crude", "Estoques SPR (reserva estratégica) EUA", "mil barris"),
    ("eia_gasolina_estoque_us", "petroleum/stoc/wstk", "WGTSTUS1", "weekly",
     "US", "gasolina", "Estoques de gasolina EUA (WPSR)", "mil barris"),
    ("eia_destilados_estoque_us", "petroleum/stoc/wstk", "WDISTUS1", "weekly",
     "US", "destilados", "Estoques de destilados EUA (WPSR)", "mil barris"),
    # --- Produção semanal de crude (proxy do shale) ---
    ("eia_crude_producao_us", "petroleum/sum/sndw", "WCRFPUS2", "weekly",
     "US", "crude", "Produção de crude EUA, semanal (WPSR)", "mil barris/dia"),
    # --- Preços spot diários ---
    ("eia_wti_spot", "petroleum/pri/spt", "RWTC", "daily",
     "US", "crude", "WTI spot Cushing", "USD/barril"),
    ("eia_brent_spot", "petroleum/pri/spt", "RBRTE", "daily",
     "EU", "crude", "Brent spot Europa", "USD/barril"),
    ("eia_henryhub_spot", "natural-gas/pri/fut", "RNGWHHD", "daily",
     "US", "gas_natural", "Henry Hub spot", "USD/MMBtu"),
    # --- Gás natural: estoques semanais (quinta 10:30 ET) ---
    ("eia_gas_estoque_us", "natural-gas/stor/wkly", "NW2_EPG0_SWO_R48_BCF", "weekly",
     "US", "gas_natural", "Working gas em estoque, Lower 48", "Bcf"),
    # --- Demanda EUA por produto (product supplied, WPSR quarta 10:30 ET) ---
    ("eia_dem_us_gasolina", "petroleum/cons/wpsup", "WGFUPUS2", "weekly",
     "US", "gasolina", "Product supplied de gasolina EUA (proxy de demanda)", "mil b/d"),
    ("eia_dem_us_destilados", "petroleum/cons/wpsup", "WDIUPUS2", "weekly",
     "US", "destilados", "Product supplied de destilados EUA (diesel; proxy de demanda)", "mil b/d"),
    ("eia_dem_us_jet", "petroleum/cons/wpsup", "WKJUPUS2", "weekly",
     "US", "jet", "Product supplied de jet fuel EUA (proxy de demanda)", "mil b/d"),
    ("eia_dem_us_total", "petroleum/cons/wpsup", "WRPUPUS2", "weekly",
     "US", "derivados", "Product supplied total de derivados EUA (proxy de demanda)", "mil b/d"),
]

FREQ_MAP = {"weekly": "semanal", "daily": "diaria", "monthly": "mensal"}


def _fetch(rota, serie_eia, freq, facet="series"):
    """Baixa a série completa com paginação (5000 linhas/chamada).
    facet: 'series' nas rotas dnav; 'seriesId' no STEO."""
    linhas, offset = [], 0
    while True:
        url = (
            f"https://api.eia.gov/v2/{rota}/data/?api_key={EIA_API_KEY}"
            f"&frequency={freq}&data[]=value&facets[{facet}][]={serie_eia}"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&length=5000&offset={offset}"
        )
        with urllib.request.urlopen(url, timeout=120) as r:
            resp = json.load(r)["response"]
        lote = resp["data"]
        linhas.extend(lote)
        offset += len(lote)
        if offset >= int(resp["total"]) or not lote:
            break
    return linhas


def _normaliza_data(period, freq):
    if freq == "monthly":            # "2026-06" -> "2026-06-01"
        return period + "-01"
    return period                    # weekly/daily já vêm YYYY-MM-DD


def _fetch_int(facets, freq="monthly"):
    """Rota international (facets productId/countryRegionId/activityId)."""
    linhas, offset = [], 0
    fx = "".join(f"&facets[{k}][]={v}" for k, v in facets.items())
    while True:
        url = (f"https://api.eia.gov/v2/international/data/?api_key={EIA_API_KEY}"
               f"&frequency={freq}&data[]=value{fx}"
               f"&sort[0][column]=period&sort[0][direction]=asc"
               f"&length=5000&offset={offset}")
        with urllib.request.urlopen(url, timeout=120) as r:
            resp = json.load(r)["response"]
        linhas.extend(resp["data"])
        offset += len(resp["data"])
        if offset >= int(resp["total"]) or not resp["data"]:
            return linhas


def coleta(con, registra_serie, grava_dados, log=print):
    # --- Balanço global de líquidos (STEO, mensal, milhões b/d) ---
    # STEO projeta ~18 meses à frente: gravamos só até o mês corrente
    # (meses recentes são estimativa STEO, não realizado — rotulado).
    from datetime import date as _date
    mes_corrente = _date.today().strftime("%Y-%m")
    STEO_MUNDO = [
        ("PAPR_WORLD", "eia_mundo_liq_prod",
         "Produção mundial de líquidos (STEO; meses recentes são estimativa "
         "da EIA, projeção excluída)", "milhões b/d"),
        ("PATC_WORLD", "eia_mundo_liq_cons",
         "Consumo mundial de líquidos (STEO; meses recentes são estimativa "
         "da EIA, projeção excluída)", "milhões b/d"),
        ("PASC_OECD_T3", "eia_ocde_estoque",
         "Estoque comercial OCDE de cru e líquidos, fim de período (STEO; "
         "parte observável do balanço mundial)", "milhões de barris"),
    ]
    for serie_steo, sid, desc, unidade in STEO_MUNDO:
        try:
            linhas = _fetch("steo", serie_steo, "monthly", facet="seriesId")
            pares = [(r["period"] + "-01", float(r["value"])) for r in linhas
                     if r.get("value") not in (None, "") and r["period"] <= mes_corrente]
            registra_serie(con, sid, "EIA", "mundo" if "mundo" in sid else "OCDE",
                           "liquidos", desc,
                           unidade, "mensal", f"api.eia.gov/v2/steo [{serie_steo}]")
            grava_dados(con, sid, pares)
            log(f"  {sid}: {len(pares)} meses | ultimo {pares[-1][0] if pares else '-'}")
        except Exception as e:
            log(f"  [ERRO] eia_mundo_liq_{sufixo}: {type(e).__name__}: {e}")

    # --- Produção e consumo anuais por país (rota international, kb/d) ---
    # Produção = pid 53 (total liquids); consumo = pid 5 (petroleum & other liquids).
    # Consumo publica com ~1-2 anos de defasagem — comparações usam ano comum.
    PAISES_INT = ["USA", "SAU", "RUS", "CAN", "CHN", "IRQ", "BRA", "ARE", "IRN",
                  "KWT", "KAZ", "MEX", "NOR", "QAT", "VEN", "NGA", "GUY", "IND",
                  "JPN", "KOR", "DEU", "GBR"]
    for iso in PAISES_INT:
        for pid, act, sufixo, desc in [("53", "1", "prod", "Produção de líquidos"),
                                       ("5", "2", "cons", "Consumo de líquidos")]:
            sid = f"eia_pais_{iso.lower()}_{sufixo}"
            try:
                linhas = _fetch_int({"productId": pid, "activityId": act,
                                     "countryRegionId": iso, "unit": "TBPD"},
                                    freq="annual")
                pares = []
                for r in linhas:
                    try:
                        pares.append((r["period"] + "-01-01", float(r["value"])))
                    except (TypeError, ValueError):
                        continue
                registra_serie(con, sid, "EIA", iso, "liquidos",
                               f"{desc} — {iso} (anual)", "mil b/d", "anual",
                               f"api.eia.gov/v2/international [{pid}/{iso}]")
                grava_dados(con, sid, pares)
            except Exception as e:
                log(f"  [ERRO] {sid}: {type(e).__name__}: {e}")
    log(f"  eia_pais: {len(PAISES_INT)} paises (prod+cons anuais)")

    for sid, rota, serie_eia, freq, area, produto, desc, unidade in SERIES:
        try:
            linhas = _fetch(rota, serie_eia, freq)
        except Exception as e:
            log(f"  [ERRO] {sid}: {type(e).__name__}: {e}")
            continue
        pares = []
        for row in linhas:
            v = row.get("value")
            if v is None or v == "":
                continue
            pares.append((_normaliza_data(row["period"], freq), float(v)))
        registra_serie(con, sid, "EIA", area, produto, desc, unidade,
                       FREQ_MAP[freq], f"api.eia.gov/v2/{rota} [{serie_eia}]")
        grava_dados(con, sid, pares)
        log(f"  {sid}: {len(pares)} obs | ultima {pares[-1][0] if pares else '-'}")
