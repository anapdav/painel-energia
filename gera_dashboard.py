# Gerador do dashboard Energia — lê energia.db e emite energia_dashboard.html
# Estilo: dark ASIF (mesma identidade dos dashboards IPCA/Atividade).
# Paleta categórica validada (CVD/contraste, modo escuro, superfície #1a1f2e):
#   verde #3aa15f | azul #4590c9 | carvão #b3673a | teal #21a38f
#   ouro #b98a2e | roxo #9673d6 | rose #e25d75
import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone

from config import DB_PATH, PASTA

SAIDA = PASTA + "\\energia_dashboard.html"

COR = {"verde": "#3aa15f", "azul": "#4590c9", "carvao": "#b3673a",
       "teal": "#21a38f", "ouro": "#b98a2e", "roxo": "#9673d6",
       "rose": "#e25d75", "cinza": "#718096"}

con = sqlite3.connect(DB_PATH)


def q(sid, desde=None):
    sql = "SELECT data, valor FROM dados WHERE serie_id=? AND valor IS NOT NULL"
    args = [sid]
    if desde:
        sql += " AND data >= ?"
        args.append(desde)
    return con.execute(sql + " ORDER BY data", args).fetchall()


def ultimo(sid):
    r = con.execute("SELECT data, valor FROM dados WHERE serie_id=? AND valor IS NOT NULL "
                    "ORDER BY data DESC LIMIT 1", (sid,)).fetchone()
    return r if r else ("-", None)


def epoch_dias(iso):
    return (date.fromisoformat(iso) - date(1970, 1, 1)).days


def compacta(pares):
    """[(iso, v)] -> {d: [dias epoch], v: [valores]} (JSON enxuto)."""
    return {"d": [epoch_dias(d) for d, _ in pares],
            "v": [round(v, 3) for _, v in pares]}


def mensal_media(pares):
    acc = defaultdict(lambda: [0.0, 0])
    for d, v in pares:
        acc[d[:7]][0] += v
        acc[d[:7]][1] += 1
    return sorted((m + "-01", s / n) for m, (s, n) in acc.items())


def serie(sid, label, cor, desde=None, mensal=False):
    pares = q(sid, desde)
    if mensal:
        pares = mensal_media(pares)
    return {"label": label, "cor": COR.get(cor, cor), "data": compacta(pares)}


# ---------------------------------------------------------------- KPIs
def kpi(sid, label, unidade, casas=2, escala=1.0):
    d, v = ultimo(sid)
    val = f"{v * escala:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") \
        if v is not None else "-"
    return {"label": label, "valor": val, "unidade": unidade, "data": d}


def kpi_yahoo(sid, label):
    d, v = ultimo(sid)
    def m(sufixo):
        r = con.execute("SELECT valor FROM meta WHERE chave=?", (f"{sid}_{sufixo}",)).fetchone()
        return r[0] if r else None
    val = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if v is not None else "-"
    contrato = m("contrato") or "contrato n/d"
    return {"label": label, "valor": val,
            "unidade": f"USD/b — {contrato} (Yahoo, ~15min)",
            "data": m("hora") or d}


KPIS = [
    kpi_yahoo("yahoo_wti_fut", "WTI futuro"),
    kpi_yahoo("yahoo_brent_fut", "Brent futuro"),
    kpi("eia_henryhub_spot", "Henry Hub", "USD/MMBtu"),
    kpi("smard_de_preco_da", "Day-ahead DE-LU", "EUR/MWh", 1),
    kpi("agsi_eu_cheio_pct", "Gás UE armazenado", "% cheio", 1),
    kpi("ccee_pld_dia_se", "PLD SE/CO", "R$/MWh", 1),
    kpi("ons_ear_sin_pct", "EAR SIN", "% máx", 1),
    kpi("bh_us_rigs_total", "Rigs EUA", "ativos", 0),
]

# ---------------------------------------------------------------- Gráficos
CH = {}

# --- Aba 0: Visão Global ---
CH["mundo_liq"] = {
    "titulo": "Petróleo no mundo — oferta × demanda", "unidade": "milhões b/d",
    "fonte": "Produção e consumo mundiais de petróleo e derivados. EIA STEO "
             "(mensal; meses recentes = estimativa EIA, projeção excluída)",
    "series": [
        serie("eia_mundo_liq_prod", "Oferta (produção)", "verde"),
        serie("eia_mundo_liq_cons", "Demanda (consumo)", "rose")]}

# Variação implícita de estoques = oferta − demanda (calculado)
_prod = dict(q("eia_mundo_liq_prod", "2015-01-01"))
_cons = dict(q("eia_mundo_liq_cons", "2015-01-01"))
CH["mundo_estoque_var"] = {
    "titulo": "O mundo está acumulando ou queimando estoque?",
    "unidade": "milhões b/d",
    "fonte": "Variação implícita de estoques = oferta − demanda (calculado do STEO; "
             "inclui discrepância estatística e estoques não observáveis, ex. China)",
    "barras": True, "zero": True, "series": [
        {"label": "Acúmulo (+) / queima (−) de estoque", "cor": COR["azul"],
         "data": compacta(sorted((d, _prod[d] - _cons[d]) for d in _prod if d in _cons))}]}
CH["mundo_estoque_ocde"] = {
    "titulo": "O estoque observável — comercial OCDE", "unidade": "milhões de barris",
    "fonte": "EIA STEO (fim de período; a parte do balanço mundial que se enxerga — "
             "China e não-OCDE não reportam)",
    "series": [serie("eia_ocde_estoque", "Estoque OCDE", "teal", "2015-01-01")]}

GRUPOS_IEA = [("eolica", "Eólica", "verde"), ("hidro", "Hídrica", "azul"),
              ("carvao", "Carvão", "carvao"), ("biomassa", "Biomassa", "teal"),
              ("solar", "Solar", "ouro"), ("nuclear", "Nuclear", "roxo"),
              ("gas", "Gás", "rose"), ("outros", "Outros (óleo, geo...)", "cinza")]
def _abs_iea_anual():
    """Soma ANUAL (GWh) por fonte, alinhada — só anos com 12 meses."""
    grupos = {g: dict(q(f"iea_ger_ieatotal_{g}")) for g, _, _ in GRUPOS_IEA}
    meses_por_ano = defaultdict(set)
    for m in set().union(*[set(g) for g in grupos.values()]):
        meses_por_ano[m[:4]].add(m[5:7])
    anos = sorted(a for a, ms in meses_por_ano.items() if len(ms) == 12)
    out = []
    for g, label, cor in GRUPOS_IEA:
        soma = defaultdict(float)
        for m, v in grupos[g].items():
            soma[m[:4]] += v
        out.append({"label": label, "cor": COR[cor],
                    "data": compacta([(f"{a}-01-01", soma.get(a, 0.0)) for a in anos])})
    return out

CH["iea_abs"] = {
    "titulo": "Geração elétrica por fonte — agregado IEA Total", "unidade": "TWh/ano",
    "fonte": "IEA MES; países-membros da IEA, não o mundo. Base ANUAL — anos completos; "
             "ano corrente parcial excluído",
    "series": _abs_iea_anual(), "stack": True, "abs": True, "escala": 0.001}
def _share_iea():
    """Share ANUAL (%) das séries mensais do IEA — só anos com 12 meses."""
    grupos = {g: dict(q(f"iea_ger_ieatotal_{g}")) for g, _, _ in GRUPOS_IEA}
    meses_por_ano = defaultdict(set)
    for m in set().union(*[set(g) for g in grupos.values()]):
        meses_por_ano[m[:4]].add(m[5:7])
    anos = sorted(a for a, ms in meses_por_ano.items() if len(ms) == 12)
    soma = {g: defaultdict(float) for g in grupos}
    for g, serie_g in grupos.items():
        for m, v in serie_g.items():
            soma[g][m[:4]] += v
    out = []
    for g, label, cor in GRUPOS_IEA:
        pares = []
        for a in anos:
            total = sum(soma[x].get(a, 0.0) for x in grupos)
            if total > 0:
                pares.append((f"{a}-01-01", 100.0 * soma[g].get(a, 0.0) / total))
        out.append({"label": label, "cor": COR[cor], "data": compacta(pares)})
    return out

CH["iea_share"] = {
    "titulo": "Participação por fonte — agregado IEA Total", "unidade": "% da geração",
    "fonte": "IEA MES, países-membros da IEA. Base ANUAL — anos completos; "
             "ano corrente parcial excluído",
    "series": _share_iea(), "stack": True}

# --- Tabelas da Visão Global ---
def _fmt_kbd(v, sinal=False):
    if v is None:
        return "—"
    s = f"{v:+,.0f}" if sinal else f"{v:,.0f}"
    return s.replace(",", ".")

def _valor_ano(sid, ano):
    r = con.execute("SELECT valor FROM dados WHERE serie_id=? AND data=?",
                    (sid, f"{ano}-01-01")).fetchone()
    return r[0] if r else None

def _media_12m(sid):
    rs = con.execute("SELECT valor FROM dados WHERE serie_id=? "
                     "ORDER BY data DESC LIMIT 12", (sid,)).fetchall()
    return sum(r[0] for r in rs) / len(rs) if rs else None

ISO3_CC2 = {"USA": "US", "SAU": "SA", "RUS": "RU", "CAN": "CA", "CHN": "CN",
            "IRQ": "IQ", "BRA": "BR", "ARE": "AE", "IRN": "IR", "KWT": "KW",
            "KAZ": "KZ", "MEX": "MX", "NOR": "NO", "QAT": "QA", "VEN": "VE",
            "NGA": "NG", "GUY": "GY", "IND": "IN", "JPN": "JP", "KOR": "KR",
            "DEU": "DE", "GBR": "GB"}
ISO3_NOME = {"USA": "EUA", "SAU": "Arábia Saudita", "RUS": "Rússia",
             "CAN": "Canadá", "CHN": "China", "IRQ": "Iraque", "BRA": "Brasil",
             "ARE": "Emirados", "IRN": "Irã", "KWT": "Kuwait", "KAZ": "Cazaquistão",
             "MEX": "México", "NOR": "Noruega", "QAT": "Catar", "VEN": "Venezuela",
             "NGA": "Nigéria", "GUY": "Guiana", "IND": "Índia", "JPN": "Japão",
             "KOR": "Coreia do Sul", "DEU": "Alemanha", "GBR": "Reino Unido"}

def _tab_balanco():
    ano = 2024  # último ano com produção E consumo publicados (consumo defasa)
    linhas = []
    for iso in ISO3_NOME:
        p = _valor_ano(f"eia_pais_{iso.lower()}_prod", ano)
        c = _valor_ano(f"eia_pais_{iso.lower()}_cons", ano)
        if p is None and c is None:
            continue
        cc2 = ISO3_CC2[iso]
        x = _media_12m(f"jodi_cru_x_{cc2}")
        m = _media_12m(f"jodi_cru_m_{cc2}")
        saldo = (p - c) if (p is not None and c is not None) else None
        linhas.append((p or 0, [ISO3_NOME[iso], _fmt_kbd(p), _fmt_kbd(c),
                                _fmt_kbd(saldo, sinal=True),
                                _fmt_kbd(x), _fmt_kbd(m)]))
    linhas.sort(key=lambda t: -t[0])
    return {"colunas": ["País", f"Produção {ano}", f"Consumo {ano}",
                        "Saldo (P−C)", "X cru (12m)", "M cru (12m)"],
            "linhas": [l for _, l in linhas], "sinal_col": 3}

def _tab_delta():
    linhas = []
    for iso in ISO3_NOME:
        v05 = _valor_ano(f"eia_pais_{iso.lower()}_prod", 2005)
        v15 = _valor_ano(f"eia_pais_{iso.lower()}_prod", 2015)
        v25 = _valor_ano(f"eia_pais_{iso.lower()}_prod", 2025)
        if None in (v05, v15, v25):
            continue
        linhas.append((v25 - v05, [ISO3_NOME[iso], _fmt_kbd(v05), _fmt_kbd(v15),
                                   _fmt_kbd(v25), _fmt_kbd(v25 - v05, True),
                                   _fmt_kbd(v25 - v15, True)]))
    linhas.sort(key=lambda t: -t[0])
    return {"colunas": ["País", "2005", "2015", "2025", "Δ 20 anos", "Δ 10 anos"],
            "linhas": [l for _, l in linhas], "sinal_col": 4}

CH["tab_balanco"] = {
    "titulo": "Balanço dos principais países — produção, consumo e comércio de petróleo",
    "unidade": "mil b/d",
    "fonte": "Produção/consumo: EIA international, anual (2024 = último ano com os dois "
             "publicados). X/M de cru: JODI, média dos últimos 12 meses reportados — "
             "Rússia para em 2023, Brasil em 2022 (fim de reporte); '—' = não reporta",
    "series": [], "tabela": _tab_balanco()}
CH["tab_delta"] = {
    "titulo": "Quem supriu o crescimento da demanda — produção de líquidos, 2005/2015/2025",
    "unidade": "mil b/d",
    "fonte": "EIA international, total liquids anual. Demanda mundial: 84,7 (2005) → "
             "95,8 (2015) → 104,0 Mb/d (2025, STEO)",
    "series": [], "tabela": _tab_delta()}

# --- Aba: Petróleo por produto (macro da cadeia) ---
PRODUTOS_JODI = [("gasolina", "Gasolina", "verde"),
                 ("diesel_gasoleo", "Diesel/gasóleo", "azul"),
                 ("oleo_combustivel", "Óleo combustível", "carvao"),
                 ("nafta", "Nafta (petroquímica)", "teal"),
                 ("glp", "GLP", "ouro"),
                 ("jet", "Jet fuel (ex-China)", "roxo"),
                 ("outros", "Querosene e outros (incl. jet China)", "rose")]

def _painel_jodi(share=False):
    grupos = {g: dict(q(f"jodi_painel_{g}", "2010-01-01")) for g, _, _ in PRODUTOS_JODI}
    meses = sorted(set.intersection(*[set(m) for m in grupos.values() if m]) or set())
    out = []
    for g, label, cor in PRODUTOS_JODI:
        pares = []
        for mes in meses:
            if share:
                total = sum(grupos[x].get(mes, 0.0) for x, _, _ in PRODUTOS_JODI)
                pares.append((mes, 100.0 * grupos[g].get(mes, 0.0) / total if total else 0.0))
            else:
                pares.append((mes, grupos[g].get(mes, 0.0)))
        out.append({"label": label, "cor": COR[cor], "data": compacta(pares)})
    return out

CH["prod_dem_abs"] = {
    "titulo": "Para que se usa o petróleo? Demanda por produto",
    "unidade": "milhões b/d",
    "fonte": "JODI, soma de 14 grandes consumidores ex-Brasil (~60% da demanda global; "
             "mês entra só com painel completo — defasagem segue o país mais lento)",
    "series": _painel_jodi(), "stack": True, "abs": True, "escala": 0.001}
def _painel_jodi_share_anual():
    """Share ANUAL da demanda por produto (kb/d ponderado por dias do mês)."""
    import calendar as _cal
    grupos = {g: dict(q(f"jodi_painel_{g}")) for g, _, _ in PRODUTOS_JODI}
    meses_por_ano = defaultdict(set)
    for m in set.intersection(*[set(g) for g in grupos.values() if g]):
        meses_por_ano[m[:4]].add(m[5:7])
    anos = sorted(a for a, ms in meses_por_ano.items() if len(ms) == 12)
    vol = {g: defaultdict(float) for g in grupos}
    for g, serie_g in grupos.items():
        for m, v in serie_g.items():
            ano, mes = int(m[:4]), int(m[5:7])
            vol[g][m[:4]] += v * _cal.monthrange(ano, mes)[1]  # kb/d * dias = kb
    out = []
    for g, label, cor in PRODUTOS_JODI:
        pares = []
        for a in anos:
            total = sum(vol[x].get(a, 0.0) for x in grupos)
            if total > 0:
                pares.append((f"{a}-01-01", 100.0 * vol[g].get(a, 0.0) / total))
        out.append({"label": label, "cor": COR[cor], "data": compacta(pares)})
    return out

CH["prod_dem_share"] = {
    "titulo": "Composição da demanda por produto", "unidade": "% da demanda do painel",
    "fonte": "JODI, mesmo painel de 14 consumidores. Base ANUAL — anos completos "
             "(gasolina no verão e diesel/aquecimento no inverno não distorcem a estrutura)",
    "series": _painel_jodi_share_anual(), "stack": True}
CH["prod_dem_us"] = {
    "titulo": "EUA em alta frequência — demanda semanal por produto",
    "unidade": "mil b/d",
    "fonte": "EIA WPSR, product supplied (proxy oficial de demanda; quarta 10:30 ET)",
    "series": [
        serie("eia_dem_us_gasolina", "Gasolina", "verde", "2018-01-01"),
        serie("eia_dem_us_destilados", "Destilados (diesel)", "azul", "2018-01-01"),
        serie("eia_dem_us_jet", "Jet fuel", "roxo", "2018-01-01")]}

# --- Aba: Refino por derivado (onde estão as refinarias) ---
REFINADORES_TODOS = ["US", "CN", "IN", "RU", "JP", "KR", "SA", "BR", "DE", "IT",
                     "ES", "FR", "GB", "MX", "ID", "TH", "NL", "SG", "AE", "CA"]
CORES_LINHAS = ["azul", "verde", "ouro", "roxo", "teal", "rose"]
NOME_PAIS = {"US": "EUA", "CN": "China", "IN": "Índia", "RU": "Rússia",
             "JP": "Japão", "KR": "Coreia do Sul", "SA": "Arábia Saudita",
             "BR": "Brasil", "DE": "Alemanha", "IT": "Itália", "ES": "Espanha",
             "FR": "França", "GB": "Reino Unido", "MX": "México",
             "ID": "Indonésia", "TH": "Tailândia", "NL": "Holanda",
             "SG": "Singapura", "AE": "Emirados", "CA": "Canadá",
             "PK": "Paquistão", "EG": "Egito", "NG": "Nigéria", "QA": "Catar"}

def _top_refino(grupo, n=6):
    """Top-n países por produção recente do derivado; cores na ordem da paleta."""
    rank = []
    for cc in REFINADORES_TODOS:
        pares = q(f"jodi_ref_{cc}_{grupo}", "2010-01-01")
        if pares:
            recentes = [v for _, v in pares[-12:]]
            rank.append((sum(recentes) / len(recentes), cc, pares))
    rank.sort(reverse=True)
    return [{"label": NOME_PAIS.get(cc, cc), "cor": COR[CORES_LINHAS[i]],
             "data": compacta(pares)}
            for i, (_m, cc, pares) in enumerate(rank[:n])]

REFINO_GRUPOS = [("total", "derivados totais"), ("gasolina", "gasolina"),
                 ("diesel_gasoleo", "diesel/gasóleo"), ("jet", "jet fuel"),
                 ("nafta", "nafta"), ("glp", "GLP"),
                 ("oleo_combustivel", "óleo combustível")]
for g, nome in REFINO_GRUPOS:
    CH[f"ref_{g}"] = {
        "titulo": f"Quem refina {nome} — top 6 produtores",
        "unidade": "mil b/d",
        "fonte": "JODI REFGROUT (produção de refinaria, mensal; Rússia para em 2023 "
                 "e Brasil em 2022 por fim de reporte)",
        "series": _top_refino(g)}

# --- Aba: Fertilizantes (o elo com o gás natural) ---
def _top_fao(elemento, n=6, obrigatorios=()):
    rank = []
    for cc in ["cn", "in", "us", "ru", "br", "id", "pk", "ca", "eg", "sa",
               "de", "fr", "ng", "qa"]:
        pares = q(f"fao_n_{elemento}_{cc}")
        if pares:
            rank.append((pares[-1][1], cc, pares))
    rank.sort(reverse=True)
    top = rank[:n]
    for ob in obrigatorios:
        if ob not in [cc for _, cc, _ in top]:
            extra = [r for r in rank if r[1] == ob]
            top = top[:n - 1] + extra
    return [{"label": NOME_PAIS.get(cc.upper(), cc.upper()),
             "cor": COR[CORES_LINHAS[i % 6]], "data": compacta(pares)}
            for i, (_v, cc, pares) in enumerate(top)]

CH["fert_prod"] = {
    "titulo": "Quem produz fertilizante nitrogenado", "unidade": "mil t N/ano",
    "fonte": "FAOSTAT (anual; produção de N — o elo com gás natural/amônia; "
             "China produz majoritariamente via carvão)",
    "series": _top_fao("prod")}
CH["fert_uso"] = {
    "titulo": "Quem usa fertilizante nitrogenado na agricultura",
    "unidade": "mil t N/ano", "fonte": "FAOSTAT (anual; uso agrícola de N)",
    "series": _top_fao("uso", obrigatorios=("br",))}
CH["fert_brasil"] = {
    "titulo": "Brasil — produção × uso de nitrogenados (a dependência de importação)",
    "unidade": "mil t N/ano", "fonte": "FAOSTAT (anual)",
    "series": [
        {"label": "Uso agrícola", "cor": COR["rose"], "data": compacta(q("fao_n_uso_br"))},
        {"label": "Produção doméstica", "cor": COR["verde"], "data": compacta(q("fao_n_prod_br"))}]}
CH["fert_gas"] = {
    "titulo": "Gás consumido pela química europeia (inclui amônia)",
    "unidade": "TWh/ano",
    "fonte": "Eurostat nrg_bal_c (anual, consumo final do setor químico/petroquímico)",
    "series": [
        serie("euro_gas_quimica_eu27", "UE-27", "ouro"),
        serie("euro_gas_quimica_de", "Alemanha", "azul"),
        serie("euro_gas_quimica_nl", "Holanda", "verde"),
        serie("euro_gas_quimica_fr", "França", "roxo"),
        serie("euro_gas_quimica_it", "Itália", "teal"),
        serie("euro_gas_quimica_pl", "Polônia", "rose")]}

# --- Aba 1: Óleo & Gás ---
CH["precos_oleo"] = {
    "titulo": "Petróleo spot — WTI e Brent", "unidade": "USD/barril",
    "fonte": "EIA (diário)", "series": [
        serie("eia_wti_spot", "WTI", "azul", "2015-01-01"),
        serie("eia_brent_spot", "Brent", "ouro", "2015-01-01")]}
CH["hh"] = {
    "titulo": "Gás natural — Henry Hub spot", "unidade": "USD/MMBtu",
    "fonte": "EIA (diário)", "series": [
        serie("eia_henryhub_spot", "Henry Hub", "rose", "2015-01-01")]}
CH["estoques_us"] = {
    "titulo": "Estoques EUA — crude ex-SPR, gasolina, destilados", "unidade": "milhões b",
    "fonte": "EIA WPSR (semanal, quarta 10:30 ET)", "series": [
        serie("eia_crude_estoque_us", "Crude ex-SPR", "azul", "2015-01-01"),
        serie("eia_gasolina_estoque_us", "Gasolina", "ouro", "2015-01-01"),
        serie("eia_destilados_estoque_us", "Destilados", "teal", "2015-01-01")],
    "escala": 0.001}
CH["cushing_spr"] = {
    "titulo": "Cushing e SPR", "unidade": "milhões b",
    "fonte": "EIA WPSR (semanal)", "series": [
        serie("eia_crude_estoque_cushing", "Cushing", "rose", "2015-01-01"),
        serie("eia_crude_estoque_spr", "SPR", "roxo", "2015-01-01")],
    "escala": 0.001}
CH["prod_us"] = {
    "titulo": "Produção de crude EUA (proxy do shale)", "unidade": "mil b/d",
    "fonte": "EIA WPSR (semanal)", "series": [
        serie("eia_crude_producao_us", "Produção", "verde", "2015-01-01")]}
CH["rigs"] = {
    "titulo": "Rigs ativos EUA — Baker Hughes", "unidade": "rigs",
    "fonte": "Baker Hughes (semanal, sexta)", "series": [
        serie("bh_us_rigs_oil", "Óleo", "verde"),
        serie("bh_us_rigs_gas", "Gás", "rose"),
        serie("bh_us_rigs_total", "Total", "cinza")]}
CH["gas_estoque_us"] = {
    "titulo": "Working gas em estoque — Lower 48", "unidade": "Bcf",
    "fonte": "EIA (semanal, quinta 10:30 ET)", "series": [
        serie("eia_gas_estoque_us", "Lower 48", "teal", "2015-01-01")]}
CH["cftc"] = {
    "titulo": "Managed money net — WTI e Henry Hub", "unidade": "mil contratos",
    "fonte": "CFTC CoT desagregado (terça, divulga sexta)", "zero": True, "series": [
        serie("cftc_wti_mm_net", "WTI net", "azul"),
        serie("cftc_gas_mm_net", "Gás net", "rose")],
    "escala": 0.001}
CH["jodi_prod"] = {
    "titulo": "Produção de crude — maiores produtores (JODI, auto-reportado)",
    "unidade": "mil b/d", "fonte": "JODI-Oil (mensal, defasagem ~2m; Rússia parou de reportar em 2023)",
    "series": [
        serie("jodi_prod_US", "EUA", "azul", "2010-01-01"),
        serie("jodi_prod_SA", "Arábia Saudita", "ouro", "2010-01-01"),
        serie("jodi_prod_RU", "Rússia (até 2023)", "cinza", "2010-01-01"),
        serie("jodi_prod_CA", "Canadá", "teal", "2010-01-01"),
        serie("jodi_prod_CN", "China", "rose", "2010-01-01")]}
CH["jodi_dem"] = {
    "titulo": "Demanda de derivados — maiores consumidores (JODI)",
    "unidade": "mil b/d", "fonte": "JODI-Oil secundário (mensal)", "series": [
        serie("jodi_dem_US", "EUA", "azul", "2010-01-01"),
        serie("jodi_dem_CN", "China", "rose", "2010-01-01"),
        serie("jodi_dem_IN", "Índia", "ouro", "2010-01-01"),
        serie("jodi_dem_JP", "Japão", "roxo", "2010-01-01"),
        serie("jodi_dem_DE", "Alemanha", "verde", "2010-01-01")]}

# --- Aba 2: Gás Europa ---
def agsi_por_ano(sid, anos, cores):
    out = []
    for ano, cor in zip(anos, cores):
        pares = [(d, v) for d, v in q(sid, f"{ano}-01-01") if d[:4] == str(ano)]
        pares_doy = [(f"2026-{d[5:]}" if d[5:] != "02-29" else None, v) for d, v in pares]
        pares_doy = [(d, v) for d, v in pares_doy if d]
        out.append({"label": str(ano), "cor": COR.get(cor, cor),
                    "data": compacta(pares_doy),
                    "grossa": ano == anos[-1]})
    return out

CH["agsi_anos"] = {
    "titulo": "Gás UE — % do armazenamento cheio, anos sobrepostos", "unidade": "%",
    "fonte": "GIE AGSI+ (diário, 19h30 CET); eixo = dia do ano",
    "series": agsi_por_ano("agsi_eu_cheio_pct", [2022, 2023, 2024, 2025, 2026],
                           ["cinza", "roxo", "teal", "azul", "ouro"]),
    "eixo_doy": True}
CH["agsi_paises"] = {
    "titulo": "Armazenamento por país — % cheio", "unidade": "%",
    "fonte": "GIE AGSI+ (diário)", "series": [
        serie("agsi_de_cheio_pct", "Alemanha", "ouro", "2023-01-01"),
        serie("agsi_it_cheio_pct", "Itália", "verde", "2023-01-01"),
        serie("agsi_nl_cheio_pct", "Holanda", "rose", "2023-01-01"),
        serie("agsi_fr_cheio_pct", "França", "azul", "2023-01-01")]}
fluxo = [(d, v) for d, v in q("agsi_eu_injecao", "2023-01-01")]
ret = dict(q("agsi_eu_retirada", "2023-01-01"))
CH["agsi_fluxo"] = {
    "titulo": "UE — injeção líquida (injeção − retirada)", "unidade": "GWh/dia",
    "fonte": "GIE AGSI+ (diário, calculado)", "zero": True, "series": [
        {"label": "Injeção líquida", "cor": COR["teal"],
         "data": compacta([(d, v - ret[d]) for d, v in fluxo if d in ret])}]}
CH["alsi"] = {
    "titulo": "GNL — send-out de regaseificação, UE", "unidade": "GWh/dia",
    "fonte": "GIE ALSI (diário)", "series": [
        serie("alsi_eu_sendout", "Send-out UE", "roxo", "2021-01-01")]}

# --- Aba 3: Matriz elétrica Alemanha ---
FONTES_DE = [  # (série(s), label, cor) — ordem de empilhamento = paleta validada
    (["smard_de_ger_eolica_on", "smard_de_ger_eolica_off"], "Eólica", "verde"),
    (["smard_de_ger_hidro"], "Hídrica", "azul"),
    (["smard_de_ger_linhita", "smard_de_ger_hulha"], "Carvão", "carvao"),
    (["smard_de_ger_biomassa"], "Biomassa", "teal"),
    (["smard_de_ger_solar"], "Solar", "ouro"),
    (["smard_de_ger_nuclear"], "Nuclear", "roxo"),
    (["smard_de_ger_gas"], "Gás", "rose"),
]

def stack_anual(fontes):
    """Share ANUAL (%) por fonte a partir de séries diárias — só anos completos
    (>=360 dias em algum grupo); evita que a sazonalidade contamine a estrutura.
    Grupo sem dado num ano completo (ex.: nuclear pós-desligamento) conta zero."""
    dados = []
    for sids, label, cor in fontes:
        soma, dias = defaultdict(float), defaultdict(set)
        for sid in sids:
            for d, v in q(sid):
                soma[d[:4]] += v
                dias[d[:4]].add(d)
        dados.append((label, cor, dict(soma), {a: len(s) for a, s in dias.items()}))
    anos = sorted({a for _, _, _, dd in dados for a, n in dd.items() if n >= 360})
    out = []
    for label, cor, m, _ in dados:
        pares = []
        for a in anos:
            total = sum(mm.get(a, 0.0) for _, _, mm, _ in dados)
            if total > 0:
                pares.append((f"{a}-01-01", 100.0 * m.get(a, 0.0) / total))
        out.append({"label": label, "cor": COR[cor], "data": compacta(pares)})
    return out


def stack_mensal(fontes):
    """Share mensal (%) por fonte, empilhado. Devolve lista de séries."""
    mensais = []
    for sids, label, cor in fontes:
        tot = defaultdict(float)
        for sid in sids:
            for d, v in mensal_media(q(sid)):
                tot[d] += v
        mensais.append((label, cor, dict(tot)))
    meses = sorted(set().union(*[set(m) for _, _, m in mensais]))
    out = []
    for label, cor, m in mensais:
        pares = []
        for mes in meses:
            total = sum(mm.get(mes, 0.0) for _, _, mm in mensais)
            if total > 0:
                pares.append((mes, 100.0 * m.get(mes, 0.0) / total))
        out.append({"label": label, "cor": COR[cor], "data": compacta(pares)})
    return out

CH["de_share"] = {
    "titulo": "Alemanha — participação na geração, por fonte",
    "unidade": "% da geração",
    "fonte": "SMARD/Bundesnetzagentur (CC BY 4.0). Base ANUAL — anos completos; "
             "ano corrente parcial excluído p/ não misturar sazonalidade com estrutura",
    "series": stack_anual(FONTES_DE), "stack": True}
CH["de_preco"] = {
    "titulo": "Preço day-ahead DE-LU (média diária das horas)", "unidade": "EUR/MWh",
    "fonte": "SMARD (zona DE-LU existe desde out/2018)", "zero": True, "series": [
        serie("smard_de_preco_da", "DE-LU", "ouro")]}
CH["de_carga"] = {
    "titulo": "Carga elétrica Alemanha (média mensal)", "unidade": "GWh/dia",
    "fonte": "SMARD", "series": [
        serie("smard_de_carga", "Carga", "azul", mensal=True)],
    "escala": 0.001}

# --- Aba 4: Matriz Europa (ENTSO-E) ---
CH["eu_precos"] = {
    "titulo": "Preços day-ahead — zonas europeias", "unidade": "EUR/MWh",
    "fonte": "ENTSO-E A44 (FR/ES/IT-N/NL/PL) + SMARD (DE-LU); média diária dos intervalos",
    "zero": True, "series": [
        serie("entsoe_preco_da_fr", "França", "azul"),
        serie("entsoe_preco_da_es", "Espanha", "verde"),
        serie("entsoe_preco_da_itn", "Itália N", "rose"),
        serie("entsoe_preco_da_nl", "Holanda", "roxo"),
        serie("entsoe_preco_da_pl", "Polônia", "carvao"),
        serie("smard_de_preco_da", "DE-LU", "ouro")]}

GRUPOS_EU = [("eolica", "Eólica", "verde"), ("hidro", "Hídrica", "azul"),
             ("carvao", "Carvão", "carvao"), ("biomassa", "Biomassa", "teal"),
             ("solar", "Solar", "ouro"), ("nuclear", "Nuclear", "roxo"),
             ("gas", "Gás", "rose"), ("outros", "Outros", "cinza")]

def stack_entsoe(pais):
    fontes = [([f"entsoe_ger_{pais}_{g}"], label, cor)
              for g, label, cor in GRUPOS_EU
              if q(f"entsoe_ger_{pais}_{g}")]
    return stack_anual(fontes)

for pais, nome in [("fr", "França"), ("es", "Espanha"), ("it", "Itália"), ("pl", "Polônia")]:
    CH[f"{pais}_share"] = {
        "titulo": f"{nome} — participação na geração, por fonte",
        "unidade": "% da geração",
        "fonte": "ENTSO-E A75. Base ANUAL — anos completos; ano corrente parcial excluído",
        "series": stack_entsoe(pais), "stack": True}

# --- Aba 5: Brasil ---
FONTES_BR = [
    (["ons_ger_eolica"], "Eólica", "verde"),
    (["ons_ger_hidro"], "Hídrica", "azul"),
    (["ons_ger_solar"], "Solar", "ouro"),
    (["ons_ger_termica"], "Térmica", "rose"),
]
CH["br_share"] = {
    "titulo": "Brasil — participação na geração do SIN, por fonte",
    "unidade": "% da geração",
    "fonte": "ONS, balanço de energia. Base ANUAL — anos completos; ano corrente "
             "parcial excluído (sazonalidade hídrica não contamina a estrutura)",
    "series": stack_anual(FONTES_BR), "stack": True}
CH["ear"] = {
    "titulo": "EAR — energia armazenada nos reservatórios", "unidade": "% do máximo",
    "fonte": "ONS (diário)", "series": [
        serie("ons_ear_sin_pct", "SIN", "ouro", "2020-01-01"),
        serie("ons_ear_se_pct", "SE/CO", "roxo", "2020-01-01"),
        serie("ons_ear_s_pct", "Sul", "azul", "2020-01-01"),
        serie("ons_ear_ne_pct", "Nordeste", "verde", "2020-01-01"),
        serie("ons_ear_n_pct", "Norte", "teal", "2020-01-01")]}
CH["pld"] = {
    "titulo": "PLD média diária por submercado", "unidade": "R$/MWh",
    "fonte": "CCEE (horário desde 2021, Dessem)", "series": [
        serie("ccee_pld_dia_se", "SE/CO", "roxo"),
        serie("ccee_pld_dia_s", "Sul", "azul"),
        serie("ccee_pld_dia_ne", "Nordeste", "verde"),
        serie("ccee_pld_dia_n", "Norte", "teal")]}
CH["carga_sin"] = {
    "titulo": "Carga do SIN (média mensal)", "unidade": "GWmed",
    "fonte": "ONS (diário agregado)", "series": [
        serie("ons_carga_sin", "SIN", "azul", mensal=True)],
    "escala": 0.001}
CH["anp"] = {
    "titulo": "Produção de petróleo — Brasil", "unidade": "mil b/d",
    "fonte": "ANP (mensal, defasagem ~2m; convertido de m³ a 6,28981 bbl/m³)",
    "series": [serie("anp_petroleo_prod_kbd", "Produção", "verde", "2005-01-01")]}
CH["epe"] = {
    "titulo": "Consumo de eletricidade na rede — Brasil", "unidade": "GWh/mês",
    "fonte": "EPE (mensal; meses recentes preliminares)", "series": [
        serie("epe_consumo_total", "Total", "azul", "2010-01-01"),
        serie("epe_consumo_industrial", "Industrial", "carvao", "2010-01-01"),
        serie("epe_consumo_residencial", "Residencial", "ouro", "2010-01-01")],
    "escala": 0.001}

ABAS = [
    ("Visão Global", ["mundo_liq", "mundo_estoque_var", "mundo_estoque_ocde",
                      "iea_abs", "iea_share", "tab_balanco", "tab_delta"]),
    ("Petróleo por produto", ["prod_dem_abs", "prod_dem_share", "prod_dem_us"]),
    ("Refino por derivado", [f"ref_{g}" for g, _ in REFINO_GRUPOS]),
    ("Fertilizantes", ["fert_prod", "fert_uso", "fert_brasil", "fert_gas"]),
    ("Óleo & Gás global", ["precos_oleo", "hh", "estoques_us", "cushing_spr",
                           "prod_us", "rigs", "gas_estoque_us", "cftc",
                           "jodi_prod", "jodi_dem"]),
    ("Gás Europa", ["agsi_anos", "agsi_paises", "agsi_fluxo", "alsi"]),
    ("Matriz Alemanha", ["de_share", "de_preco", "de_carga"]),
    ("Matriz Europa", ["eu_precos", "fr_share", "es_share", "it_share", "pl_share"]),
    ("Brasil", ["br_share", "ear", "pld", "carga_sin", "anp", "epe"]),
]

# higiene: gráfico sem nenhuma observação não entra no painel
# (ex.: fonte temporariamente fora do ar — volta sozinho na próxima carga)
def _tem_conteudo(cfg):
    if "tabela" in cfg:
        return bool(cfg["tabela"]["linhas"])
    return any(s["data"]["d"] for s in cfg["series"] if s)

_vazios = {cid for cid, cfg in CH.items() if not _tem_conteudo(cfg)}
for cid in _vazios:
    del CH[cid]
ABAS = [(nome, [c for c in charts if c not in _vazios]) for nome, charts in ABAS]
ABAS = [(nome, charts) for nome, charts in ABAS if charts]
if _vazios:
    print(f"aviso: {len(_vazios)} paineis sem dados omitidos: {sorted(_vazios)}")

# Notas de rodapé por aba (didática: siglas e por que cada painel importa)
NOTAS_ABA = {
    "Visão Global": (
        "<b>Como ler esta aba.</b> <b>STEO</b> (Short-Term Energy Outlook) é o exercício "
        "mensal da EIA que estima oferta e demanda mundiais — os meses mais recentes são "
        "estimativa, não realizado. A diferença entre as duas curvas é a <b>variação "
        "implícita de estoques</b>: mundo produzindo mais do que consome acumula barris "
        "(pressão baixista no preço); consumindo mais do que produz, queima estoque "
        "(pressão altista). Como China e boa parte do mundo emergente não publicam "
        "estoques, o que se enxerga de fato é o estoque comercial da <b>OCDE</b> (clube "
        "das economias avançadas). <b>IEA Total</b> = soma dos países-membros da Agência "
        "Internacional de Energia (~OCDE), não o mundo inteiro."),
    "Óleo & Gás global": (
        "<b>Como ler esta aba.</b> <b>WPSR</b> (Weekly Petroleum Status Report) é o "
        "relatório semanal da EIA — sai toda quarta 10:30 ET e é o dado que mais move o "
        "preço do petróleo no curto prazo. <b>SPR</b> (Strategic Petroleum Reserve) é a "
        "reserva estratégica do governo americano, em cavernas de sal — foi esvaziada pela "
        "metade em 2022–23 para segurar o preço; <b>ex-SPR</b> = estoques comerciais, sem "
        "a reserva do governo. <b>Cushing</b> (Oklahoma) é o ponto de entrega física do "
        "contrato futuro de WTI: estoque baixo ali aperta especificamente o vencimento do "
        "contrato. <b>Rigs</b> são as sondas de perfuração ativas (contagem Baker Hughes, "
        "sextas): antecedem a produção do <b>shale</b> (óleo de xisto, ciclo curto de "
        "investimento — o produtor marginal do mundo) em ~6 a 9 meses. <b>Managed money "
        "(CFTC)</b> é a posição líquida dos fundos nos futuros — o termômetro do "
        "posicionamento especulativo, publicado toda sexta com dado de terça. <b>JODI</b> "
        "compila dados auto-reportados pelos países — cobertura ampla, qualidade desigual."),
    "Petróleo por produto": (
        "<b>Como ler esta aba.</b> O barril de petróleo não é consumido — seus derivados "
        "são, e cada um conta uma história: <b>gasolina</b> = consumidor (mobilidade leve); "
        "<b>diesel/gasóleo</b> = indústria, frete e agro (o termômetro da atividade); "
        "<b>jet fuel</b> = aviação; <b>nafta</b> = matéria-prima da petroquímica "
        "(plásticos); <b>GLP</b> = cozinha e petroquímica; <b>óleo combustível</b> = navios "
        "e geração elétrica residual. <b>Product supplied</b> é a métrica da EIA que "
        "aproxima demanda: o que saiu do sistema primário para o mercado."),
    "Refino por derivado": (
        "<b>Como ler esta aba.</b> Refinaria transforma cru em derivados — e a geografia "
        "do refino define os fluxos de comércio: os países que refinam além do próprio "
        "consumo (EUA, Índia, Coreia, Golfo) exportam derivados para quem fechou "
        "refinarias (Europa, América Latina, África). Os dados são o <b>refinery gross "
        "output</b> do JODI: produção bruta das refinarias por produto, mensal, "
        "auto-reportada — Rússia parou de reportar em 2023 e Brasil em 2022, e as linhas "
        "terminam onde o reporte termina."),
    "Fertilizantes": (
        "<b>Como ler esta aba.</b> Fertilizante nitrogenado é, economicamente, um derivado "
        "do <b>gás natural</b>: a amônia (processo Haber-Bosch) usa o gás como matéria-prima "
        "e energia — na China, a rota dominante é via carvão. Por isso o preço do gás "
        "europeu define a competitividade da química da região (no choque de 2022, plantas "
        "de amônia fecharam em cascata — visível no painel do gás da química). <b>N</b> = "
        "nutriente nitrogênio contido no fertilizante (FAOSTAT/ONU, anual). O painel do "
        "Brasil mostra a distância entre o que o agro usa e o que o país produz — a "
        "dependência de importação, majoritariamente da Rússia e do Golfo."),
    "Matriz Alemanha": (
        "<b>Como ler esta aba.</b> A Alemanha é o laboratório da transição elétrica "
        "(<b>Energiewende</b>): saiu da nuclear (último reator em abril/2023), está saindo "
        "do carvão e dobrou a aposta em eólica e solar. O <b>preço day-ahead</b> é o leilão "
        "do dia seguinte na zona <b>DE-LU</b> (Alemanha+Luxemburgo): renovável entra no "
        "sistema a custo marginal ~zero, então dias de vento e sol forte derrubam o preço "
        "(às vezes para negativo) e comprimem as térmicas — a competição entre fontes "
        "acontecendo em tempo real."),
    "Matriz Europa": (
        "<b>Como ler esta aba.</b> Eletricidade não viaja bem entre continentes — cada "
        "zona tem seu preço, e as diferenças revelam a matriz de cada país: França barata "
        "quando o parque nuclear opera bem; Polônia cara e presa ao carvão; Espanha "
        "achatada pela solar; Itália atrelada ao gás. As interconexões arbitram parte da "
        "diferença, mas o gargalo físico mantém os spreads. Dados da <b>ENTSO-E</b> (a "
        "associação dos operadores de rede europeus) — geração realizada por fonte e "
        "preços day-ahead por zona."),
    "Brasil": (
        "<b>Como ler esta aba.</b> A matriz brasileira é hidro-dominante, então o "
        "\"estoque\" do sistema é água: <b>EAR</b> (Energia Armazenada) mede quanto os "
        "reservatórios guardam, em % do máximo; <b>ENA</b> (Energia Natural Afluente) é a "
        "chuva que virou vazão, medida contra a <b>MLT</b> (média de longo termo — 100% = "
        "chuva típica). <b>PLD</b> (Preço de Liquidação das Diferenças, CCEE) é o preço "
        "spot horário por submercado; <b>CMO</b> (Custo Marginal de Operação, ONS) é o "
        "custo da próxima unidade despachada — os dois sobem quando o reservatório cai e a "
        "térmica entra. <b>SIN</b> = Sistema Interligado Nacional; <b>MWmed</b> = potência "
        "média no período. Produção de petróleo: ANP (a fonte primária — o Brasil não "
        "reporta mais ao JODI); consumo de eletricidade por classe: EPE."),
    "Gás Europa": (
        "<b>Como ler esta aba.</b> O gás natural não tem preço único mundial: cada região "
        "tem seu hub de referência — <b>Henry Hub</b> (EUA, na aba Óleo &amp; Gás global), "
        "<b>TTF</b> (Holanda, referência de preço da Europa — sem fonte primária gratuita, "
        "por isso não exibido) e <b>JKM</b> (Ásia). Quem conecta os três mercados é o "
        "<b>GNL</b> (gás natural liquefeito): gás resfriado a −162 °C para viajar de navio — "
        "foi a liquefação que transformou o gás de mercado regional em commodity global. "
        "<br><b>AGSI</b> (Aggregated Gas Storage Inventory, da GIE, associação dos operadores "
        "europeus de infraestrutura) mede os estoques de gás da Europa. O <b>% cheio</b> é o "
        "seguro do inverno: a UE mira ~90% no início de novembro — abaixo da banda dos anos "
        "anteriores, o mercado precifica risco de escassez. A <b>injeção líquida</b> mostra o "
        "ritmo sazonal: no verão injeta-se (enche), no inverno retira-se; injeção fraca no "
        "verão é sinal amarelo. <b>ALSI</b> (Aggregated LNG Storage Inventory) cobre os "
        "terminais de GNL: o <b>send-out</b> é o volume regaseificado entregue à rede — mede "
        "quanto GNL importado (EUA, Catar...) está suprindo a Europa; send-out alto = Europa "
        "puxando navios e competindo com a Ásia, o elo direto com o Henry Hub."),
}

gerado_em = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

HTML = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energia Global — ASIF</title>
<style>
:root{--page:#0f1117;--card:#1a1f2e;--border:#2d3748;--ink:#e2e8f0;
  --muted:#718096;--ouro:#C9A84C;--hl:#2a4365}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1420px;margin:0 auto;padding:16px 20px 40px}
header{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:6px 0 12px;
  background:linear-gradient(135deg,#1a1f2e,#0f1117);border:1px solid var(--border);
  border-radius:12px;padding:14px 18px}
header h1{font-size:19px;margin:0;font-weight:650}
header .logo{background:var(--ouro);color:#0f1117;font-weight:800;border-radius:8px;
  padding:6px 10px;letter-spacing:.5px}
header .sub{font-size:12.5px;color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:10px;margin:12px 0}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:10px 12px}
.kpi .l{font-size:11.5px;color:var(--muted)}
.kpi .v{font-size:20px;font-weight:700;margin:2px 0}
.kpi .u{font-size:11px;color:var(--muted)}
.kpi .dt{font-size:10.5px;color:var(--muted);margin-top:2px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 10px}
.tabs button{background:var(--card);border:1px solid var(--border);color:var(--ink);
  border-radius:8px;padding:8px 14px;font-size:13.5px;cursor:pointer}
.tabs button.on{background:var(--hl);border-color:#4590c9;font-weight:650}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(560px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:12px 14px}
.card h3{margin:0 0 2px;font-size:14.5px;font-weight:650}
.card .fonte{font-size:11px;color:var(--muted);margin-bottom:6px}
.legenda{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;margin:4px 0 2px}
.legenda span{display:inline-flex;align-items:center;gap:5px;color:var(--ink)}
.legenda i{width:10px;height:10px;border-radius:3px;display:inline-block}
.tt{position:fixed;pointer-events:none;background:#0f1117f0;border:1px solid var(--border);
  border-radius:8px;padding:8px 10px;font-size:12px;z-index:10;display:none;max-width:260px}
.tt b{color:var(--ouro)}
.btn-tab{background:none;border:1px solid var(--border);color:var(--muted);
  border-radius:6px;font-size:10.5px;padding:2px 8px;cursor:pointer;float:right}
table.dados{width:100%;border-collapse:collapse;font-size:11.5px;margin-top:6px}
table.dados th,table.dados td{border-bottom:1px solid var(--border);padding:3px 6px;
  text-align:right}
table.dados th:first-child,table.dados td:first-child{text-align:left}
footer{margin-top:18px;font-size:11.5px;color:var(--muted)}
.nota-aba{margin-top:14px;background:var(--card);border:1px solid var(--border);
  border-left:3px solid var(--ouro);border-radius:10px;padding:12px 16px;
  font-size:12.5px;line-height:1.6;color:var(--ink)}
.nota-aba b{color:var(--ouro)}
.disclaimer{background:var(--card);border:1px solid var(--border);border-radius:10px;
  padding:12px 16px;line-height:1.6;font-size:11.5px;color:var(--muted)}
.disclaimer b{color:var(--ink)}
.rolagem{overflow-x:auto}
.card-tabela{grid-column:1/-1}
.card-tabela table{max-width:900px;margin:0 auto}
table.tab-g{font-size:12px}
table.tab-g th{color:var(--muted);font-weight:600;text-align:right;padding:4px 8px}
table.tab-g th:first-child{text-align:left}
table.tab-g td{padding:4px 8px}
</style></head><body><div class="wrap">
<header><span class="logo">ASIF</span>
<div><h1>Energia Global — fontes primárias</h1>
<div class="sub">EIA · GIE AGSI/ALSI · SMARD/Bundesnetzagentur · ONS · CCEE · ANP · EPE · JODI · CFTC · Baker Hughes
 &nbsp;|&nbsp; gerado em __GERADO__ &nbsp;|&nbsp; cada painel indica fonte e frequência</div></div>
</header>
<div class="kpis" id="kpis"></div>
<div class="tabs" id="tabs"></div>
<div id="conteudo"></div>
<div class="tt" id="tt"></div>
<footer>
<div class="disclaimer">
<b>Aviso legal e de uso.</b> Este painel tem caráter exclusivamente informativo e analítico.
<b>Não constitui recomendação de investimento</b>, oferta ou solicitação de compra ou venda de
qualquer ativo, nem aconselhamento financeiro de qualquer natureza.
Os dados provêm de fontes públicas oficiais, com data de referência explícita em cada painel, e
<b>estão sujeitos a revisão pelas próprias fontes</b>; convenções de cálculo, conversões e regras
de tratamento estão documentadas no manual de metodologia do projeto. Apesar do esforço de
verificação, erros de coleta ou processamento são possíveis — os valores não substituem as
publicações originais das fontes.
<br><b>Fontes e atribuições:</b> EIA (U.S. Energy Information Administration) · GIE AGSI+/ALSI
(© GIE, uso com atribuição) · SMARD/Bundesnetzagentur (CC BY 4.0) · ENTSO-E Transparency Platform ·
ONS (dados abertos) · CCEE (CC BY 4.0) · ANP · EPE · JODI (auto-reportado pelos países) ·
CFTC · Baker Hughes · IEA (Monthly Electricity Statistics) · FAOSTAT/ONU · Eurostat.
Cotações de futuros via Yahoo Finance: dados de mercado <b>com atraso (~15 min), não-oficiais,
apenas para referência</b> — não usar para fins transacionais.
As marcas e os dados pertencem às respectivas fontes.
</div>
</footer>
</div>
<script>
const KPIS=__KPIS__;
const CH=__CH__;
const ABAS=__ABAS__;
const NOTAS=__NOTAS__;
const fmt=(x,c=1)=>x==null?"-":x.toLocaleString("pt-BR",{minimumFractionDigits:c,maximumFractionDigits:c});
const dstr=t=>{const d=new Date(t*86400000);return d.toISOString().slice(0,10).split("-").reverse().join("/")};

document.getElementById("kpis").innerHTML=KPIS.map(k=>
 `<div class="kpi"><div class="l">${k.label}</div><div class="v">${k.valor}</div>`+
 `<div class="u">${k.unidade}</div><div class="dt">ref. ${k.data.split("-").reverse().join("/")}</div></div>`).join("");

const tabs=document.getElementById("tabs"),cont=document.getElementById("conteudo");
ABAS.forEach((a,i)=>{const b=document.createElement("button");b.textContent=a[0];
 b.onclick=()=>mostra(i);tabs.appendChild(b)});

function mostra(ix){
 [...tabs.children].forEach((b,i)=>b.classList.toggle("on",i===ix));
 cont.innerHTML=`<div class="grid">`+ABAS[ix][1].map(id=>{
  const c=CH[id];
  if(c.tabela){
   const t=c.tabela;
   const linhas=t.linhas.map(l=>`<tr>${l.map((v,j)=>{
    let cls="";
    if(j===t.sinal_col&&v!=="—")cls=v.startsWith("-")?' style="color:#e25d75"':' style="color:#3aa15f"';
    return `<td${cls}>${v}</td>`}).join("")}</tr>`).join("");
   return `<div class="card card-tabela"><h3>${c.titulo}</h3><div class="fonte">${c.fonte} — ${c.unidade}</div>`+
    `<div class="rolagem"><table class="dados tab-g"><tr>${t.colunas.map(x=>`<th>${x}</th>`).join("")}</tr>${linhas}</table></div></div>`;
  }
  return `<div class="card" id="c_${id}"><button class="btn-tab" onclick="tabela('${id}')">tabela</button>`+
  `<h3>${c.titulo}</h3><div class="fonte">${c.fonte} — ${c.unidade}</div>`+
  `<div class="legenda">${c.series.map(s=>`<span><i style="background:${s.cor}"></i>${s.label}</span>`).join("")}</div>`+
  `<div id="g_${id}"></div><div id="t_${id}"></div></div>`}).join("")+`</div>`+
  (NOTAS[ABAS[ix][0]]?`<div class="nota-aba">${NOTAS[ABAS[ix][0]]}</div>`:"");
 ABAS[ix][1].filter(id=>!CH[id].tabela).forEach(id=>desenha(id));
}

function pontos(s,esc){const o=[];for(let i=0;i<s.data.d.length;i++)
 o.push([s.data.d[i],s.data.v[i]*esc]);return o}

function desenha(id){
 const cfg=CH[id],el=document.getElementById("g_"+id),esc=cfg.escala||1;
 const W=el.clientWidth||620,H=260,ML=52,MR=14,MT=10,MB=26;
 const ss=cfg.series.map(s=>({...s,p:pontos(s,esc)}));
 let x0=1e12,x1=-1e12,y0=1e12,y1=-1e12;
 if(cfg.stack){
  y0=0;
  if(cfg.abs){ // empilhado absoluto: teto = maior soma das camadas
   const tot={};ss.forEach(s=>s.p.forEach(([d,v])=>{tot[d]=(tot[d]||0)+v}));
   y1=Math.max(...Object.values(tot))*1.04;
  }else{y1=100}
  ss.forEach(s=>s.p.forEach(([d])=>{x0=Math.min(x0,d);x1=Math.max(x1,d)}));
 }else{
  ss.forEach(s=>s.p.forEach(([d,v])=>{x0=Math.min(x0,d);x1=Math.max(x1,d);
   y0=Math.min(y0,v);y1=Math.max(y1,v)}));
  if(cfg.zero){y0=Math.min(y0,0);y1=Math.max(y1,0)}
  const pad=(y1-y0)*0.06||1;y0-=pad;y1+=pad;
 }
 const X=d=>ML+(d-x0)/(x1-x0)*(W-ML-MR), Y=v=>MT+(1-(v-y0)/(y1-y0))*(H-MT-MB);
 let svg=`<svg width="${W}" height="${H}" data-ch="${id}">`;
 // grade horizontal (5 ticks)
 const nt=5;for(let i=0;i<=nt;i++){const v=y0+(y1-y0)*i/nt,y=Y(v);
  svg+=`<line x1="${ML}" y1="${y}" x2="${W-MR}" y2="${y}" stroke="#2d3748" stroke-width="1"/>`;
  svg+=`<text x="${ML-6}" y="${y+4}" fill="#718096" font-size="10.5" text-anchor="end">${fmt(v,Math.abs(y1-y0)<10?1:0)}</text>`}
 // eixo x: anos (ou meses p/ dia-do-ano), com passo p/ não colidir rótulos
 const marcas=[],vistos=new Set();
 for(let d=Math.ceil(x0);d<=x1;d+=1){const dt=new Date(d*86400000);
  const chave=cfg.eixo_doy?dt.getUTCMonth():dt.getUTCFullYear();
  if(!vistos.has(chave)&&(cfg.eixo_doy?dt.getUTCDate()===1:dt.getUTCMonth()===0&&dt.getUTCDate()<=7)){
   vistos.add(chave);
   marcas.push([d,cfg.eixo_doy?dt.toLocaleString("pt-BR",{month:"short",timeZone:"UTC"}):dt.getUTCFullYear()])}}
 const passo=Math.max(1,Math.ceil(marcas.length/8));
 marcas.forEach((m,i)=>{if(i%passo===0)
  svg+=`<text x="${X(m[0])}" y="${H-8}" fill="#718096" font-size="10.5" text-anchor="middle">${m[1]}</text>`});
 if(cfg.zero&&y0<0){svg+=`<line x1="${ML}" y1="${Y(0)}" x2="${W-MR}" y2="${Y(0)}" stroke="#718096" stroke-width="1.2" stroke-dasharray="3 3"/>`}
 if(cfg.barras){
  // barras com sinal: positivo verde (acúmulo), negativo rose (queima)
  const p=ss[0].p, bw=Math.max(1,(W-ML-MR)/p.length*0.75);
  p.forEach(([d,v])=>{
   const y=Math.min(Y(v),Y(0)), h=Math.abs(Y(v)-Y(0));
   svg+=`<rect x="${X(d)-bw/2}" y="${y}" width="${bw}" height="${Math.max(h,0.5)}" fill="${v>=0?"#3aa15f":"#e25d75"}"/>`});
 }else if(cfg.stack){
  // áreas empilhadas com gap visual de 1.5px entre camadas
  const datas=ss[0].p.map(p=>p[0]);
  const acum=datas.map(()=>0);
  ss.forEach(s=>{
   const topo=s.p.map((p,i)=>acum[i]+p[1]);
   let path="M"+s.p.map((p,i)=>`${X(p[0])},${Y(topo[i])}`).join("L");
   path+="L"+s.p.map((p,i)=>`${X(p[0])},${Y(acum[i])}`).reverse().join("L")+"Z";
   svg+=`<path d="${path}" fill="${s.cor}" stroke="#1a1f2e" stroke-width="1.5" fill-opacity="0.92"/>`;
   s.p.forEach((p,i)=>acum[i]=topo[i]);
  });
 }else{
  ss.forEach(s=>{
   const path="M"+s.p.map(p=>`${X(p[0])},${Y(p[1])}`).join("L");
   const w=s.grossa?2.6:1.8, op=s.grossa===false?0.7:1;
   svg+=`<path d="${path}" fill="none" stroke="${s.cor}" stroke-width="${w}" stroke-opacity="${op}"/>`;
  });
 }
 svg+=`<line id="ch_${id}" x1="0" y1="${MT}" x2="0" y2="${H-MB}" stroke="#e2e8f0" stroke-width="0.7" opacity="0"/>`;
 svg+=`<rect x="${ML}" y="${MT}" width="${W-ML-MR}" height="${H-MT-MB}" fill="transparent" class="hover"/>`;
 svg+=`</svg>`;
 el.innerHTML=svg;
 // hover: data mais próxima
 const rect=el.querySelector(".hover"),tt=document.getElementById("tt"),
       cross=el.querySelector(`#ch_${id}`);
 rect.addEventListener("mousemove",ev=>{
  const bb=rect.getBoundingClientRect();
  const d=Math.round(x0+(ev.clientX-bb.left)/bb.width*(x1-x0));
  let html=`<b>${cfg.eixo_doy?dstr(d).slice(0,5):dstr(d)}</b>`;
  ss.forEach(s=>{let melhor=null,dist=1e12;
   for(const[dd,vv]of s.p){const dl=Math.abs(dd-d);if(dl<dist){dist=dl;melhor=vv}}
   if(melhor!=null&&dist<45)html+=`<br><span style="color:${s.cor}">●</span> ${s.label}: ${fmt(melhor,1)}`});
  tt.innerHTML=html;tt.style.display="block";
  tt.style.left=Math.min(ev.clientX+14,window.innerWidth-280)+"px";
  tt.style.top=(ev.clientY+12)+"px";
  const svgel=el.querySelector("svg"),sb=svgel.getBoundingClientRect();
  cross.setAttribute("x1",ev.clientX-sb.left);cross.setAttribute("x2",ev.clientX-sb.left);
  cross.setAttribute("opacity","0.35");
 });
 rect.addEventListener("mouseleave",()=>{tt.style.display="none";
  cross.setAttribute("opacity","0")});
}

function tabela(id){
 const el=document.getElementById("t_"+id),cfg=CH[id],esc=cfg.escala||1;
 if(el.innerHTML){el.innerHTML="";return}
 const datas=[...new Set(cfg.series.flatMap(s=>s.data.d))].sort((a,b)=>b-a).slice(0,12);
 let h=`<table class="dados"><tr><th>data</th>${cfg.series.map(s=>`<th>${s.label}</th>`).join("")}</tr>`;
 datas.forEach(d=>{h+=`<tr><td>${dstr(d)}</td>`;
  cfg.series.forEach(s=>{const i=s.data.d.indexOf(d);
   h+=`<td>${i>=0?fmt(s.data.v[i]*esc,1):"-"}</td>`});h+=`</tr>`});
 el.innerHTML=h+"</table>";
}
mostra(0);
window.addEventListener("resize",()=>{const on=[...tabs.children].findIndex(b=>b.classList.contains("on"));if(on>=0)mostra(on)});
</script></body></html>"""

html = (HTML.replace("__KPIS__", json.dumps(KPIS, ensure_ascii=False))
            .replace("__CH__", json.dumps(CH, ensure_ascii=False))
            .replace("__ABAS__", json.dumps(ABAS, ensure_ascii=False))
            .replace("__NOTAS__", json.dumps(NOTAS_ABA, ensure_ascii=False))
            .replace("__GERADO__", gerado_em))
with open(SAIDA, "w", encoding="utf-8") as f:
    f.write(html)
print(f"dashboard gerado: {SAIDA} ({len(html)//1024} KB)")
con.close()
