# Coletor SMARD (Bundesnetzagentur, Alemanha) — sem autenticação, CC BY 4.0
# API: https://www.smard.de/app/chart_data/{filtro}/{regiao}/..._{resolucao}_{ts}.json
# IDs de filtro conforme openapi.yaml oficial (github.com/bundesAPI/smard-api).
import json
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BERLIM = ZoneInfo("Europe/Berlin")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# (filtro, serie_id, produto, descricao, unidade)  — resolução diária: MWh/dia
GERACAO = [
    (1223, "smard_de_ger_linhita",     "Geração a linhita (Braunkohle) — DE"),
    (4069, "smard_de_ger_hulha",       "Geração a hulha (Steinkohle) — DE"),
    (4071, "smard_de_ger_gas",         "Geração a gás natural — DE"),
    (1224, "smard_de_ger_nuclear",     "Geração nuclear — DE (encerrada abr/2023)"),
    (1226, "smard_de_ger_hidro",       "Geração hidrelétrica — DE"),
    (4067, "smard_de_ger_eolica_on",   "Geração eólica onshore — DE"),
    (1225, "smard_de_ger_eolica_off",  "Geração eólica offshore — DE"),
    (4068, "smard_de_ger_solar",       "Geração solar FV — DE"),
    (4066, "smard_de_ger_biomassa",    "Geração biomassa — DE"),
]
CARGA = (410, "smard_de_carga", "Carga total — DE")
PRECO = (4169, "smard_de_preco_da", "Preço day-ahead DE-LU (média diária das horas)")


def _json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.load(r)


def _serie(filtro, regiao, resolucao):
    """Baixa todos os blocos da série; devolve [(ts_ms, valor), ...]."""
    idx = _json(f"https://www.smard.de/app/chart_data/{filtro}/{regiao}/index_{resolucao}.json")
    pontos = []
    for ts in idx["timestamps"]:
        url = (f"https://www.smard.de/app/chart_data/{filtro}/{regiao}/"
               f"{filtro}_{regiao}_{resolucao}_{ts}.json")
        pontos.extend(_json(url)["series"])
    return pontos


def _data_local(ts_ms):
    """Data local de Berlim do timestamp (blocos começam à meia-noite local)."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(BERLIM).date().isoformat()


def coleta(con, registra_serie, grava_dados, log=print):
    # --- Geração por fonte + carga, resolução diária (MWh/dia) ---
    for filtro, sid, desc in GERACAO + [CARGA]:
        try:
            pontos = _serie(filtro, "DE", "day")
        except Exception as e:
            log(f"  [ERRO] {sid}: {type(e).__name__}: {e}")
            continue
        pares = [(_data_local(ts), float(v)) for ts, v in pontos if v is not None]
        produto = "eletricidade"
        registra_serie(con, sid, "SMARD", "DE", produto, desc, "MWh/dia",
                       "diaria", f"smard.de filtro {filtro}")
        grava_dados(con, sid, pares)
        log(f"  {sid}: {len(pares)} dias | ultima {pares[-1][0] if pares else '-'}")

    # --- Preço day-ahead DE-LU: horário -> média diária simples ---
    filtro, sid, desc = PRECO
    try:
        pontos = _serie(filtro, "DE-LU", "hour")
        por_dia = {}
        for ts, v in pontos:
            if v is None:
                continue
            por_dia.setdefault(_data_local(ts), []).append(float(v))
        pares = sorted((d, sum(vs) / len(vs)) for d, vs in por_dia.items())
        registra_serie(con, sid, "SMARD", "DE", "eletricidade", desc, "EUR/MWh",
                       "diaria", f"smard.de filtro {filtro} (DE-LU, horario)")
        grava_dados(con, sid, pares)
        log(f"  {sid}: {len(pares)} dias | ultima {pares[-1][0] if pares else '-'}")
    except Exception as e:
        log(f"  [ERRO] {sid}: {type(e).__name__}: {e}")
