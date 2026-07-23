# Coletor Baker Hughes — North America Rig Count (semanal, sexta-feira)
# Links /static-files/{uuid} mudam a cada semana -> sempre descobrir na página.
# Arquivo semanal atual ("New Report") traz microdado 2024+; o histórico
# ("New Report (2013-...)") cobre 2013 em diante. Ambos: aba "NAM Weekly".
import io
import re
from collections import defaultdict

import openpyxl
from curl_cffi import requests as cfr

PAGINA = "https://rigcount.bakerhughes.com/na-rig-count"


def _links():
    r = cfr.get(PAGINA, impersonate="chrome", timeout=120)
    r.raise_for_status()
    achados = re.findall(r'href="(/static-files/[^"]+)"[^>]*>\s*([^<]{0,120})', r.text)
    atual = hist = None
    for href, txt in achados:
        t = txt.strip()
        if atual is None and re.search(r"Rig Count Report - New Report", t):
            atual = href
        if hist is None and re.search(r"Rig Count New Report \(2013", t):
            hist = href
    return atual, hist


def _somas_semanais(xlsx_bytes):
    """Soma 'Rig Count Value' dos EUA por (data, DrillFor) na aba NAM Weekly."""
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True)
    ws = wb["NAM Weekly"]
    somas = defaultdict(float)
    cols = None
    for row in ws.iter_rows(values_only=True):
        if cols is None:
            if row and row[0] == "Country":
                cols = {nome: i for i, nome in enumerate(row) if nome}
            continue
        try:
            if row[cols["Country"]] != "UNITED STATES":
                continue
            data = row[cols["US_PublishDate"]]
            alvo = row[cols["DrillFor"]]
            val = row[cols["Rig Count Value"]]
        except (KeyError, IndexError, TypeError):
            continue
        if data is None or val is None:
            continue
        d = str(data)[:10]
        somas[(d, str(alvo))] += float(val)
    return somas


def _tem_historico(con, sid):
    r = con.execute("SELECT MIN(data) FROM dados WHERE serie_id=?", (sid,)).fetchone()
    return r and r[0] and r[0] < "2020-01-01"


def coleta(con, registra_serie, grava_dados, log=print):
    atual, hist = _links()
    if not atual:
        log("  [ERRO] bakerhughes: link do relatório semanal não encontrado na página")
        return
    # arquivo atual (2024+) tem precedência; o histórico (2013+) só entra nas
    # datas que o atual não cobre (os dois se sobrepõem em 2024-2025)
    arquivos = [("atual", atual)]
    if hist and not _tem_historico(con, "bh_us_rigs_oil"):
        arquivos.append(("historico", hist))
    somas, datas_vistas = {}, set()
    for nome, href in arquivos:
        try:
            r = cfr.get(f"https://rigcount.bakerhughes.com{href}",
                        impersonate="chrome", timeout=300)
            r.raise_for_status()
            parcial = _somas_semanais(r.content)
            novas = {d for d, _ in parcial} - datas_vistas
            for (d, alvo), v in parcial.items():
                if d in novas:
                    somas[(d, alvo)] = somas.get((d, alvo), 0.0) + v
            datas_vistas |= novas
            log(f"  bakerhughes {nome}: {len(r.content)//1024} KB, "
                f"{len(novas)} datas novas")
        except Exception as e:
            log(f"  [ERRO] bakerhughes {nome}: {type(e).__name__}: {e}")

    oil = sorted((d, v) for (d, alvo), v in somas.items() if alvo == "Oil")
    gas = sorted((d, v) for (d, alvo), v in somas.items() if alvo == "Gas")
    tot = defaultdict(float)
    for (d, _alvo), v in somas.items():
        tot[d] += v
    total = sorted(tot.items())
    for sid, pares, desc in [
        ("bh_us_rigs_oil", oil, "Rigs ativos EUA — óleo"),
        ("bh_us_rigs_gas", gas, "Rigs ativos EUA — gás"),
        ("bh_us_rigs_total", total, "Rigs ativos EUA — total (óleo+gás+misc)"),
    ]:
        registra_serie(con, sid, "BakerHughes", "US", "upstream", desc,
                       "rigs", "semanal", PAGINA)
        grava_dados(con, sid, pares)
    log(f"  bh_us_rigs: {len(total)} semanas | ultima {total[-1][0] if total else '-'} "
        f"(oil {oil[-1][1]:.0f} / gas {gas[-1][1]:.0f})" if total else "  bh: vazio")
