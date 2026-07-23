# Configuração central do pipeline Energia
import os

PASTA = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PASTA, "energia.db")

def carrega_env():
    """Lê o .env da pasta do projeto e devolve dict (não polui os.environ)."""
    env = {}
    caminho = os.path.join(PASTA, ".env")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV = carrega_env()
EIA_API_KEY = ENV.get("EIA_API_KEY", "")
AGSI_API_KEY = ENV.get("AGSI_API_KEY", "")
ENTSOE_TOKEN = ENV.get("ENTSOE_TOKEN", "")
