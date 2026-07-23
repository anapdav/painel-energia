# Coletor GIE AGSI+ (estoques de gás UE) e ALSI (GNL) — granularidade diária
# Manual: GIE_API_documentation_v007.pdf. Chave no header x-key (vale p/ os dois).
# Obs: o WAF barra o User-Agent do urllib -> usar curl_cffi com impersonate.
import time

from curl_cffi import requests as cfr

from config import AGSI_API_KEY

AREAS_AGSI = [
    ("eu", "EU", "UE agregado"),
    ("de", "DE", "Alemanha"),
    ("it", "IT", "Itália"),
    ("nl", "NL", "Holanda"),
    ("fr", "FR", "França"),
]

# campo da API -> (sufixo do serie_id, descricao, unidade)
CAMPOS_AGSI = {
    "gasInStorage": ("estoque_twh", "Gás em estoque", "TWh"),
    "full": ("cheio_pct", "Estoque % do volume útil", "%"),
    "injection": ("injecao", "Injeção", "GWh/dia"),
    "withdrawal": ("retirada", "Retirada", "GWh/dia"),
}


def _pagina(base, params, pagina):
    q = "&".join(f"{k}={v}" for k, v in {**params, "page": pagina, "size": 300}.items())
    r = cfr.get(f"{base}?{q}", headers={"x-key": AGSI_API_KEY},
                impersonate="chrome", timeout=60)
    r.raise_for_status()
    return r.json()


def _serie_completa(base, params):
    """Itera todas as páginas; devolve lista de dicts (um por gas day)."""
    j = _pagina(base, params, 1)
    dados = list(j["data"])
    for p in range(2, int(j["last_page"]) + 1):
        dados.extend(_pagina(base, params, p)["data"])
        time.sleep(1.1)  # rate limit oficial: 60 chamadas/min
    return dados


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def coleta(con, registra_serie, grava_dados, log=print):
    # --- AGSI: estoques por área ---
    for codigo, area, nome in AREAS_AGSI:
        params = {"country": codigo} if codigo != "eu" else {"type": "eu"}
        try:
            dados = _serie_completa("https://agsi.gie.eu/api", params)
        except Exception as e:
            log(f"  [ERRO] agsi_{codigo}: {type(e).__name__}: {e}")
            continue
        for campo, (sufixo, desc, unidade) in CAMPOS_AGSI.items():
            sid = f"agsi_{codigo}_{sufixo}"
            pares = [(d["gasDayStart"], _f(d.get(campo))) for d in dados
                     if _f(d.get(campo)) is not None]
            registra_serie(con, sid, "AGSI", area, "gas_natural",
                           f"{desc} — {nome}", unidade, "diaria", "agsi.gie.eu/api")
            grava_dados(con, sid, pares)
        log(f"  agsi_{codigo}: {len(dados)} gas days | ultimo "
            f"{dados[0]['gasDayStart'] if dados else '-'}")

    # --- ALSI: regaseificação de GNL, agregado UE ---
    try:
        dados = _serie_completa("https://alsi.gie.eu/api", {"type": "eu"})
        sid = "alsi_eu_sendout"
        pares = [(d["gasDayStart"], _f(d.get("sendOut"))) for d in dados
                 if _f(d.get("sendOut")) is not None]
        registra_serie(con, sid, "ALSI", "EU", "gnl",
                       "Send-out (regaseificação) de GNL — UE agregado",
                       "GWh/dia", "diaria", "alsi.gie.eu/api")
        grava_dados(con, sid, pares)
        log(f"  alsi_eu: {len(pares)} gas days | ultimo {dados[0]['gasDayStart'] if dados else '-'}")
    except Exception as e:
        log(f"  [ERRO] alsi_eu: {type(e).__name__}: {e}")
