# Coletor ANP — produção nacional de petróleo e gás natural (mensal, desde 1997)
# CSVs estáticos em gov.br/anp (dados abertos, "produção por estado e localização").
# Atenção: meses futuros vêm preenchidos com ZERO no arquivo -> descartar meses
# cujo total nacional seja 0 (placeholder), nunca gravá-los como dado.
import calendar
import csv
import io
import urllib.request
from collections import defaultdict

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/ppgn-el"
MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
         "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
BBL_POR_M3 = 6.28981  # fator de conversão padrão barril/m³


def _totais_mensais(arquivo):
    """Soma nacional por mês; devolve {(ano, mes): total}."""
    url = f"{BASE}/{arquivo}"
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
    try:
        texto = raw.decode("utf-8-sig")   # arquivo vem em UTF-8 com BOM
    except UnicodeDecodeError:
        texto = raw.decode("latin-1")
    rd = csv.DictReader(io.StringIO(texto), delimiter=";")
    tot = defaultdict(float)
    for row in rd:
        mes = MESES.get((row.get("MÊS") or "").strip().upper())
        ano = (row.get("ANO") or "").strip()
        val = (row.get("PRODUÇÃO") or "").strip().replace(",", ".")
        if not mes or not ano.isdigit() or not val:
            continue
        tot[(int(ano), mes)] += float(val)
    # descarta placeholders: meses com total nacional exatamente 0
    return {k: v for k, v in tot.items() if v > 0}


def coleta(con, registra_serie, grava_dados, log=print):
    # --- Petróleo (m³/mês) + conversão rotulada para kb/d ---
    try:
        tot = _totais_mensais("producao-petroleo-m3.csv")
        if not tot:
            raise ValueError("nenhuma linha válida no CSV de petróleo")
        m3 = sorted((f"{a}-{m:02d}-01", v) for (a, m), v in tot.items())
        kbd = sorted((f"{a}-{m:02d}-01",
                      v * BBL_POR_M3 / calendar.monthrange(a, m)[1] / 1000)
                     for (a, m), v in tot.items())
        registra_serie(con, "anp_petroleo_prod_m3", "ANP", "BR", "crude",
                       "Produção nacional de petróleo (soma estados)", "m³/mês",
                       "mensal", f"{BASE}/producao-petroleo-m3.csv")
        grava_dados(con, "anp_petroleo_prod_m3", m3)
        registra_serie(con, "anp_petroleo_prod_kbd", "ANP", "BR", "crude",
                       "Produção nacional de petróleo — CONVERTIDA de m³/mês "
                       f"(fator {BBL_POR_M3} bbl/m³, dias do mês)", "kb/d",
                       "mensal", f"{BASE}/producao-petroleo-m3.csv")
        grava_dados(con, "anp_petroleo_prod_kbd", kbd)
        log(f"  anp_petroleo: {len(m3)} meses | ultimo {m3[-1][0]} "
            f"({kbd[-1][1]:,.0f} kb/d)")
    except Exception as e:
        log(f"  [ERRO] anp_petroleo: {type(e).__name__}: {e}")

    # --- Gás natural (mil m³/mês) ---
    try:
        tot = _totais_mensais("producao-gas-natural-1000m3.csv")
        if not tot:
            raise ValueError("nenhuma linha válida no CSV de gás")
        pares = sorted((f"{a}-{m:02d}-01", v) for (a, m), v in tot.items())
        registra_serie(con, "anp_gas_prod_mm3", "ANP", "BR", "gas_natural",
                       "Produção nacional de gás natural (soma estados)",
                       "mil m³/mês", "mensal", f"{BASE}/producao-gas-natural-1000m3.csv")
        grava_dados(con, "anp_gas_prod_mm3", pares)
        log(f"  anp_gas: {len(pares)} meses | ultimo {pares[-1][0]}")
    except Exception as e:
        log(f"  [ERRO] anp_gas: {type(e).__name__}: {e}")
