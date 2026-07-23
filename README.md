# Painel Energia Global

Acompanhamento do mercado global de energia — petróleo, gás natural, eletricidade e fertilizantes — construído exclusivamente sobre **fontes primárias oficiais**, com toda convenção de cálculo documentada.

**➜ Painel:** [anapdav.github.io/painel-energia](https://anapdav.github.io/painel-energia/)

## O que tem

9 abas, ~470 séries, 16 fontes: EIA, ENTSO-E, SMARD/Bundesnetzagentur, GIE AGSI+/ALSI, ONS, CCEE, ANP, EPE, JODI, CFTC, Baker Hughes, IEA, FAOSTAT, Eurostat — do balanço mundial de petróleo à matriz elétrica por país, do refino por derivado aos fertilizantes nitrogenados.

## Princípios

- **Nenhum número sem rótulo**: todo painel declara fonte, frequência, unidade, data de referência e ressalvas de cobertura.
- **Nenhum fallback silencioso**: dado faltante é faltante (nunca vira zero); fonte fora do ar omite o painel em vez de mostrar dado velho.
- **Participação de fontes em base anual** (anos completos) — a sazonalidade não contamina a leitura estrutural.
- Lacunas conhecidas são decisões documentadas, não esquecimentos (China, TTF, Rússia pós-2023).

## Documentação

- [`METODOLOGIA.md`](METODOLOGIA.md) — convenções de cálculo, regras por fonte e histórico de decisões.
- [`FONTES.md`](FONTES.md) — levantamento verificado de cada fonte (acesso, formato, defasagem, riscos de automação).

## Como rodar

```
python atualiza.py            # coleta todas as fontes (incremental) -> energia.db
python gera_dashboard.py      # gera energia_dashboard.html
```

Requer Python 3.12+, `curl_cffi`, `openpyxl` e chaves gratuitas em `.env` (EIA, GIE AGSI, ENTSO-E — instruções no FONTES.md).

## Aviso

Painel exclusivamente informativo e analítico — **não constitui recomendação de investimento**. Dados sujeitos a revisão pelas fontes originais; cotações de futuros (Yahoo Finance) com atraso e apenas para referência. Marcas e dados pertencem às respectivas fontes.
