# Orquestrador do pipeline Energia
# Uso: python atualiza.py [eia] [agsi] [smard] | (sem argumento = todos)
import sys
import time

import db
from coletores import (eia, agsi, smard, ons, ccee, jodi, cftc, anp,
                       bakerhughes, epe, entsoe, iea, yahoo, fao, eurostat)

COLETORES = {"eia": eia, "agsi": agsi, "smard": smard,
             "ons": ons, "ccee": ccee, "jodi": jodi, "cftc": cftc,
             "anp": anp, "bakerhughes": bakerhughes, "epe": epe,
             "entsoe": entsoe, "iea": iea, "yahoo": yahoo,
             "fao": fao, "eurostat": eurostat}


def main():
    pedidos = [a for a in sys.argv[1:] if a in COLETORES] or list(COLETORES)
    con = db.conecta()
    for nome in pedidos:
        print(f"[{nome.upper()}] coletando...")
        t0 = time.time()
        COLETORES[nome].coleta(con, db.registra_serie, db.grava_dados)
        con.commit()
        print(f"[{nome.upper()}] ok em {time.time() - t0:.0f}s\n")

    print("=" * 100)
    print(f"{'serie_id':<28} {'n':>6} {'primeira':>10} {'ultima':>10} {'ultimo valor':>14}  unidade")
    print("-" * 100)
    for sid, desc, unid, n, ini, fim, ult in db.resumo(con):
        ult_fmt = f"{ult:,.2f}" if ult is not None else "-"
        print(f"{sid:<28} {n:>6} {ini or '-':>10} {fim or '-':>10} {ult_fmt:>14}  {unid}")
    con.close()


if __name__ == "__main__":
    main()
