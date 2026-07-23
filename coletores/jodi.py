# Coletor JODI-Oil (jodidata.org) — CSVs anuais grátis, sem autenticação
# primary = petróleo cru (produção INDPROD, estoques CLOSTLV)
# secondary = derivados (demanda TOTDEMO de TOTPRODS)
# Defasagem ~2 meses. China e Índia reportam — cobre parte do gap asiático.
import csv
import io
import urllib.request
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv"

# países acompanhados (código ISO-2 do REF_AREA)
PRODUTORES = ["SA", "US", "RU", "CN", "IQ", "AE", "KW", "BR", "CA", "MX",
              "NO", "NG", "LY", "VE", "KZ", "IN"]
CONSUMIDORES = ["US", "CN", "IN", "BR", "JP", "DE", "KR", "SA", "FR", "IT",
                "GB", "MX", "ES", "ID", "TH"]

# Painel fixo p/ demanda por produto: 14 grandes consumidores com reporte ativo
# (Brasil excluído: parou de reportar ao JODI em 2022 — coberto pela ANP).
# Regra: um mês só entra na soma se TODOS os 14 reportaram o produto.
PAINEL = ["US", "CN", "IN", "JP", "DE", "KR", "SA", "FR", "IT", "GB",
          "MX", "ES", "ID", "TH"]

# Países acompanhados no drilldown de refino (REFGROUT = produção de refinaria
# por produto). Inclui reportadores irregulares (RU até 2023, BR até 2022) —
# as séries simplesmente param onde o país parou de reportar.
REFINADORES = ["US", "CN", "IN", "RU", "JP", "KR", "SA", "BR", "DE", "IT",
               "ES", "FR", "GB", "MX", "ID", "TH", "NL", "SG", "AE", "CA"]

# Exportação/importação de CRU (TOTEXPSB/TOTIMPSB) acompanhadas p/ estes países
XM_PAISES = sorted(set(PRODUTORES) | {"CN", "IN", "US", "JP", "KR", "NL", "DE"})
PRODUTO_GRUPO = {
    "GASOLINE": "gasolina", "GASDIES": "diesel_gasoleo", "JETKERO": "jet",
    "LPG": "glp", "NAPHTHA": "nafta", "RESFUEL": "oleo_combustivel",
    "KEROSENE": "outros", "ONONSPEC": "outros",
}
PRODUTO_NOME = {
    "gasolina": "Gasolina", "diesel_gasoleo": "Diesel/gasóleo", "jet": "Jet fuel",
    "glp": "GLP", "nafta": "Nafta (petroquímica)", "oleo_combustivel": "Óleo combustível",
    "outros": "Querosene e outros",
}


def _csv_ano(tipo, ano):
    """Tenta {ano}.csv e depois {tipo}year{ano}.csv (padrão do ano corrente)."""
    for nome in (f"{ano}.csv", f"{tipo}year{ano}.csv"):
        url = f"{BASE}/{tipo}/{nome}"
        try:
            req = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(req, timeout=300).read()
            return csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    return None


def _num(v):
    """OBS_VALUE numérico; JODI marca faltante com '-' ou vazio -> None (nunca zero)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _tem_historico(con, sid):
    r = con.execute("SELECT MIN(data) FROM dados WHERE serie_id=?", (sid,)).fetchone()
    return r and r[0] and r[0] < f"{date.today().year - 1}-01-01"


def coleta(con, registra_serie, grava_dados, log=print):
    ano_atual = date.today().year
    completo = not (_tem_historico(con, "jodi_prod_SA")
                    and _tem_historico(con, "jodi_painel_gasolina")
                    and _tem_historico(con, "jodi_ref_US_total")
                    and _tem_historico(con, "jodi_cru_x_SA"))
    anos = range(2002, ano_atual + 1) if completo else range(ano_atual - 1, ano_atual + 1)

    prod = {c: [] for c in PRODUTORES}
    dem = {c: [] for c in CONSUMIDORES}
    painel = {}   # (mes, grupo) -> {pais: valor}
    refino = {}   # (pais, grupo) -> {mes: valor somado}
    xm = {}       # (pais, "x"|"m") -> [(mes, valor)]
    for ano in anos:
        # primário: produção de crude + exportação/importação de cru, kb/d
        rd = _csv_ano("primary", ano)
        if rd is None:
            log(f"  [AVISO] primary {ano}: nenhum arquivo (404)")
        else:
            for row in rd:
                if (row["ENERGY_PRODUCT"] != "CRUDEOIL"
                        or row["UNIT_MEASURE"] != "KBD"):
                    continue
                v = _num(row["OBS_VALUE"])
                if v is None:
                    continue
                mes, area, fluxo = row["TIME_PERIOD"] + "-01", row["REF_AREA"], row["FLOW_BREAKDOWN"]
                if fluxo == "INDPROD" and area in prod:
                    prod[area].append((mes, v))
                elif fluxo in ("TOTEXPSB", "TOTIMPSB") and area in XM_PAISES:
                    lado = "x" if fluxo == "TOTEXPSB" else "m"
                    xm.setdefault((area, lado), []).append((mes, v))
        # secundário: demanda de derivados totais, kb/d
        rd = _csv_ano("secondary", ano)
        if rd is None:
            log(f"  [AVISO] secondary {ano}: nenhum arquivo (404)")
        else:
            for row in rd:
                if row["UNIT_MEASURE"] != "KBD":
                    continue
                v = _num(row["OBS_VALUE"])
                if v is None:
                    continue
                mes = row["TIME_PERIOD"] + "-01"
                fluxo, area = row["FLOW_BREAKDOWN"], row["REF_AREA"]
                grupo = PRODUTO_GRUPO.get(row["ENERGY_PRODUCT"])
                if fluxo == "TOTDEMO":
                    if row["ENERGY_PRODUCT"] == "TOTPRODS" and area in dem:
                        dem[area].append((mes, v))
                    if grupo and area in PAINEL:
                        painel.setdefault((mes, grupo), {})
                        painel[(mes, grupo)][area] = \
                            painel[(mes, grupo)].get(area, 0.0) + v
                elif fluxo == "REFGROUT" and area in REFINADORES:
                    g = "total" if row["ENERGY_PRODUCT"] == "TOTPRODS" else grupo
                    if g:
                        refino.setdefault((area, g), {})
                        refino[(area, g)][mes] = refino[(area, g)].get(mes, 0.0) + v

    for cc, pares in prod.items():
        if not pares:
            log(f"  [AVISO] jodi_prod_{cc}: zero observações")
            continue
        sid = f"jodi_prod_{cc}"
        registra_serie(con, sid, "JODI", cc, "crude",
                       f"Produção de petróleo cru — {cc} (JODI primary, INDPROD)",
                       "kb/d", "mensal", f"{BASE}/primary/")
        grava_dados(con, sid, sorted(pares))
    for cc, pares in dem.items():
        if not pares:
            log(f"  [AVISO] jodi_dem_{cc}: zero observações")
            continue
        sid = f"jodi_dem_{cc}"
        registra_serie(con, sid, "JODI", cc, "derivados",
                       f"Demanda total de derivados — {cc} (JODI secondary, TOTDEMO)",
                       "kb/d", "mensal", f"{BASE}/secondary/")
        grava_dados(con, sid, sorted(pares))
    # painel por produto: mês entra só com o painel completo do grupo.
    # Exceção documentada: jet exige 13 países (ex-China) — a China não
    # desagrega JETKERO; o jet chinês vem como KEROSENE, dentro de "outros".
    por_grupo = {}
    for (mes, grupo), paises in painel.items():
        exigidos = [p for p in PAINEL if p != "CN"] if grupo == "jet" else PAINEL
        if all(p in paises for p in exigidos):
            por_grupo.setdefault(grupo, []).append((mes, sum(paises.values())))
    NOTAS = {"jet": " — 13 países ex-China (China não desagrega jet)",
             "outros": " — inclui o jet da China (reportado como querosene)"}
    for grupo, pares in por_grupo.items():
        sid = f"jodi_painel_{grupo}"
        registra_serie(con, sid, "JODI", "painel14", "derivados",
                       f"Demanda de {PRODUTO_NOME[grupo]} — soma de 14 grandes "
                       f"consumidores (ex-Brasil; mês entra só com painel completo"
                       f"{NOTAS.get(grupo, '')})",
                       "kb/d", "mensal", f"{BASE}/secondary/")
        grava_dados(con, sid, sorted(pares))
    ult_p = max((max(d for d, _ in p) for p in por_grupo.values()), default="-")
    log(f"  jodi_painel: {len(por_grupo)} produtos | ultimo mes completo {ult_p}")

    # exportação/importação de cru por país
    for (cc, lado), pares in xm.items():
        sid = f"jodi_cru_{lado}_{cc}"
        nome_lado = "Exportação" if lado == "x" else "Importação"
        registra_serie(con, sid, "JODI", cc, "crude",
                       f"{nome_lado} de petróleo cru — {cc} (JODI, auto-reportado)",
                       "kb/d", "mensal", f"{BASE}/primary/")
        grava_dados(con, sid, sorted(pares))
    log(f"  jodi_cru_xm: {len(xm)} series")

    # refino: produção de refinaria por produto e país.
    # O mês mais recente reportado é DESCARTADO: submissões preliminares do
    # JODI produzem valores impossíveis (ex.: EUA mai/2026 = 23,8 Mb/d, acima
    # da capacidade física, assessment code 2) — entra na rodada seguinte já
    # revisado. Detectado pela Ana em 23/07/2026.
    NOME_TOT = dict(PRODUTO_NOME, total="derivados totais")
    for (cc, grupo), meses in refino.items():
        if meses:
            del meses[max(meses)]
        if not meses:
            continue
        sid = f"jodi_ref_{cc}_{grupo}"
        registra_serie(con, sid, "JODI", cc, "refino",
                       f"Produção de refinaria de {NOME_TOT.get(grupo, grupo)} — {cc} "
                       "(JODI REFGROUT; último mês reportado omitido por ser "
                       "preliminar; série para onde o país parou de reportar)",
                       "kb/d", "mensal", f"{BASE}/secondary/")
        grava_dados(con, sid, sorted(meses.items()))
    log(f"  jodi_ref: {len(refino)} series (pais x produto)")

    n = sum(len(p) for p in prod.values()) + sum(len(p) for p in dem.values())
    ult = max((p[-1][0] for p in list(prod.values()) + list(dem.values()) if p), default="-")
    log(f"  jodi: {n} obs | ultimo mes {ult}")
