# Fontes de dados — Mercado Global de Energia

**Levantamento verificado em 22/07/2026.** Método: cada fonte foi acessada de fato (fetch das páginas oficiais, chamadas HTTP reais, download de amostras). O que não pôde ser confirmado diretamente está marcado **[NÃO VERIFICADO]** — nada aqui é "de memória".

Legenda de viabilidade: 🟢 plugável hoje, verificado ponta a ponta · 🟡 funciona, mas com fricção (chave, WAF, formato) · 🔴 sem via programática confiável.

---

## 1. Global / EUA

### 1.1 EIA — US Energy Information Administration 🟢 (chave ativa, testada 22/07/2026)
- **API v2:** `https://api.eia.gov/v2/{rota}?api_key=XXXX` — JSON (ou XML), 5.000 linhas/chamada, paginação `offset`/`length`.
- **Chave:** registrada e ativa, guardada em `.env` (`EIA_API_KEY`). **Teste real (22/07/2026):** Cushing ex-SPR semana de 17/07 = 19.370 MBBL, 1.163 registros na série; rotas de topo confirmadas: coal, crude-oil-imports, electricity, international, natural-gas, nuclear-outages, petroleum, seds, steo, densified-biomass, total-energy, aeo, ieo, co2-emissions.
- **Atenção de parser:** desde jan/2024 os valores numéricos vêm como **strings** no JSON.
- **Rotas:** `petroleum`, `natural-gas`, `electricity` (inclui horário por RTO), `total-energy`, `international`, `steo`, `aeo`, `coal`. Navegador de rotas: https://www.eia.gov/opendata/browser/
- **Estrutura:** filtros `facets[series][]=...`, colunas `data[]=value`, `frequency=weekly`, `start`/`end`, `sort[0][column]=period`. Metadados: rota sem `/data`; valores de facet em `/facet/{nome}/`.
- **Exemplo real (estoques semanais de crude em Cushing, ex-SPR):**
  `https://api.eia.gov/v2/petroleum/stoc/wstk/data?api_key=XXXX&frequency=weekly&data[]=value&facets[series][]=W_EPC0_SAX_YCUOK_MBBL&sort[0][column]=period&sort[0][direction]=desc`
  (ID `W_EPC0_SAX_YCUOK_MBBL` confirmado na página dnav da EIA.)
- **Calendário WPSR (verificado):** quarta-feira **10:30 ET** (sumário e tabelas 1–14; demais 13:00 ET); semanas com feriado → quinta 11:00/12:00, lista de exceções em https://www.eia.gov/petroleum/supply/weekly/schedule.php
- **Rate limit:** existe suspensão temporária por excesso; valor numérico não publicado **[NÃO VERIFICADO]**.
- **Custo:** tudo grátis.

### 1.2 IEA — International Energy Agency 🟡
- **www.iea.org bloqueia scripts (403)** — mesmo padrão do USDA. Mas o backend **`api.iea.org` responde sem autenticação** (verificado ao vivo):
  - `https://api.iea.org/mes/latest/month?COUNTRY=BRAZIL` → JSON real (abril/2026, geração por produto em GWh) → **defasagem ~3 meses**.
  - `https://api.iea.org/mes/list/COUNTRY` → ~50 países (OECD + Brasil, Índia, Argentina, agregados).
  - ⚠️ API **não documentada** (alimenta o site) — pode mudar sem aviso. Para produção, preferir o CSV oficial.
- **Monthly Electricity Statistics (MES):** grátis, CSV no site. **Migração em curso:** o CSV legado será descontinuado após a edição de **ago/2026**, substituído por CSV formato SDMX via .Stat Data Explorer — monitorar no pipeline.
- **Real-Time Electricity Tracker:** grátis no site (demanda/geração/preço, 50+ países); endpoint `api.iea.org/rte/...` existe mas parâmetros não mapeados **[PARCIAL]**.
- **Pago:** Monthly Oil Data Service (MODS), World Energy Balances completos. O Oil Market Report mensal tem só sumário grátis. Não existe MOS gratuito (`api.iea.org/mos` → 404, testado).

### 1.3 JODI — jodidata.org 🟢 (petróleo) / 🔴 (gás)
- **JODI-Oil:** CSVs anuais grátis, sem autenticação, **amostra baixada e verificada**:
  `https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv/primary/2025.csv` (ano corrente: `primaryyear2026.csv`; série `secondary` para derivados).
  Colunas SDMX: `REF_AREA, TIME_PERIOD, ENERGY_PRODUCT, FLOW_BREAKDOWN, UNIT_MEASURE, OBS_VALUE, ASSESSMENT_CODE`. Cobertura 2002–presente, ~100+ países. **Defasagem ~2 meses** (maio/2026 publicado em julho/2026, confirmado).
- **JODI-Gas:** zip público com Last-Modified de **out/2018** — estagnado; dado corrente só no jodidb.org (export manual). Sem via programática confiável.
- **API:** não existe.

### 1.4 OPEC MOMR 🟡
- PDF grátis em https://momr.opec.org/pdf-download/, publicação ~dia 11–14 do mês. Tabelas do apêndice em Excel desde fev/2019 **[NÃO VERIFICADO — opec.org bloqueou acesso (HTTP 402)]**.

### 1.5 Baker Hughes rig count 🟢
- Verificado ao vivo: https://rigcount.bakerhughes.com/na-rig-count — XLSX semanal (último: 17/07/2026), históricos .xlsb com rigs por estado desde 2000, médias anuais desde 1987.
- **Atenção:** links via `/static-files/{uuid}`, UUID muda a cada semana → o coletor lê a página, não fixa URL. Divulgação sexta-feira (~meio-dia CT **[horário não verificado]**).

### 1.5-b CME Group — futuros de petróleo (adicionada 23/07/2026) 🟢
- **Fonte primária dos preços de futuros**: WTI (CL, productId 425) e Brent Last Day Financial (BZ, 424) são contratos da própria CME. Cotações com atraso de 10 min (declarado no campo `quoteDelay`) via endpoint do site: `https://www.cmegroup.com/CmeWS/mvc/quotes/v2/{productId}` — JSON com todos os vencimentos, `isFrontMonth`, `quoteCode` (ex. CLU6), settlement anterior.
- **Verificado ao vivo em 23/07/2026** com `curl_cffi` (o endpoint v1 antigo morreu; o v2 responde sem token). Ressalva: endpoint não documentado — monitorar quebras. ICE (Brent físico): dado pago, sem via gratuita.
- **API Socrata pública, sem autenticação, verificada ao vivo** (retornou dado de 14/07/2026):
  `https://publicreporting.cftc.gov/resource/72hh-3qpy.json?$limit=1&$where=commodity_name='CRUDE OIL'&$order=report_date_as_yyyy_mm_dd DESC`
  Dataset `72hh-3qpy` = Disaggregated Futures Only (managed money, producers, swap dealers, OI); `kh3c-gbw2` = Combined. Parâmetros SoQL `$where/$select/$limit`; CSV/JSON/XML.
- Dado de terça, divulgado sexta à tarde ET **[horário exato não re-verificado]**.

---

## 2. Europa

### 2.1 SMARD — Bundesnetzagentur (Alemanha) 🟢
- **API JSON sem autenticação nenhuma:** `https://www.smard.de/app/chart_data/` (o proxy `smard.api.proxy.bund.dev` não resolve mais — usar smard.de direto; DNS testado).
- **Estrutura (verificada no openapi.yaml oficial do repo bundesAPI/smard-api):**
  - índice: `/app/chart_data/{filter}/{region}/index_{resolution}.json`
  - série: `/app/chart_data/{filter}/{region}/{filter}_{region}_{resolution}_{timestamp}.json`
- **IDs de filtro:** geração — 1223 linhita, 1224 nuclear, 1225 eólica offshore, 1226 hídrica, 4066 biomassa, 4067 eólica onshore, 4068 solar FV, 4069 hulha, 4070 bombeamento, 4071 gás; carga — 410 total, 4359 residual; **preços atacado** — 4169 DE/LU, 4170 AT, 4996 BE, 252–262 (DK1/DK2/FR/IT-N/NL/PL/CH/SI/CZ/HU); previsões — 122/123/126/3791/5097.
- **Regiões:** DE, AT, LU, DE-LU e zonas de controle (50Hertz, Amprion, TenneT, TransnetBW). **Resoluções:** quarterhour/hour/day/week/month/year. **Histórico desde 2015. Near real-time. CC BY 4.0** (atribuição obrigatória).
- **Exemplo:** `https://www.smard.de/app/chart_data/1223/DE/1223_DE_hour_1627855200000.json`
- ⚠️ Fluxos transfronteiriços: IDs não documentados no openapi — usar Download Center (CSV/XLSX) ou ENTSO-E.
- **Bundesnetzagentur além do SMARD:** Monitoringbericht anual (estrutura de mercado eletricidade+gás, desde 2006; edição 2025 publicada 26/11/2025) — PDF, majoritariamente em alemão.

### 2.2 ENTSO-E Transparency Platform 🟢 (token ativo, coletor rodando — 23/07/2026)
- **API:** `https://web-api.tp.entsoe.eu/api` — XML. Token no `.env` (`ENTSOE_TOKEN`), backfill completo em 23/07/2026: preços A44 (FR/ES/IT-N/NL/PL desde 2015) e geração A75 por tipo (FR/ES/IT/PL desde 2018).
- **Notas de implementação (aprendidas no backfill):** resolução migrou para **PT15M** (mercado de 15 min, 2025); curveType **A03 omite valores repetidos** — preencher posições com o último valor; XMLs anuais de A75 podem dar **504** — o coletor divide a janela ao meio e tenta de novo; dia corrente vem parcial (substituído na rodada seguinte pela janela de 45 dias).
- **Cobertura:** Europa inteira — carga (A65), geração por fonte (A75/A73), **preços day-ahead (A44)**, fluxos físicos e comerciais, NTC, indisponibilidades. Granularidade 15/30/60 min por zona. Histórico desde 05/01/2015.
- **Rate limit (guia oficial lido em 23/07/2026, API R3):** 400 req/min **por token** (não mais por IP); exceder = ban temporário do token ~10 min; timeout de request = 300 s. Throttling recomendado: 6–7 req/s.
- **Limite de tamanho por consulta (tabela oficial, 23/07/2026):** preços day-ahead (12.1.D), carga real (6.1.A), geração agregada por tipo (16.1.B/C), fluxos físicos (12.1.G) e reservatórios (16.1.D) = **máx. 1 ano por request**; geração por usina (16.1.A) = **1 dia** (evitar em backfill); capacidade instalada = sem limite. Exceder → negative acknowledgement.
- **Documentação migrou:** o Guide.html antigo morreu (400); guia oficial agora em transparencyplatform.zendesk.com ("Sitemap for Restful API Integration", artigo 15692855254548).
- **Cliente Python de referência:** `entsoe-py` (EnergieID).
- **Exemplo:** `https://web-api.tp.entsoe.eu/api?securityToken={token}&documentType=A44&in_Domain=10Y1001A1001A46L&periodStart=202208020000&periodEnd=202208022300`
- **Importante:** os preços day-ahead da ENTSO-E **cobrem de graça** o que EPEX/Nord Pool cobram.

### 2.3 GIE — AGSI+ (estoques de gás) e ALSI (GNL) 🟢 (chave ativa, testada 22/07/2026)
- Fonte mais bem documentada do levantamento — **manual oficial da API (v007) lido na íntegra.**
- **URLs:** `https://agsi.gie.eu/api` e `https://alsi.gie.eu/api`. Chave registrada e ativa, guardada em `.env` (`AGSI_API_KEY`), header **`x-key`**, vale para AGSI e ALSI.
- **Teste real (22/07/2026):** gas day 20/07 — UE 612,95 TWh (54,23% cheio, injeção 2.746 GWh/d); Alemanha 112,22 TWh (45,53%); ALSI sendOut UE 2.419 GWh/d.
- **Notas de implementação:** (1) o User-Agent padrão do `urllib` leva 403 — usar `curl_cffi` ou UA de navegador; (2) ALSI sem filtro retorna lista vazia — usar `type=eu` ou `country=`; (3) mapear nomes exatos dos campos de inventário GNL no primeiro coletor.
- **Granularidade diária** (gas day), publicação **19h30 CET** (2ª rodada 23h00). Histórico: AGSI desde 01/01/2011, ALSI desde 01/01/2012.
- **Campos:** gasInStorage (TWh), injection/withdrawal (GWh/d), **full (%)**, workingGasVolume; ALSI: inventory GNL, sendOut. Agregações UE/país/empresa/instalação (`country`, `company`, `facility`, `from`, `to`, `type=eu`). Paginação `size` máx 300 + `last_page`.
- **Rate limit:** 60 chamadas/min. Atribuição "GIE / AGSI" obrigatória.
- **Exemplo:** `https://agsi.gie.eu/api?country=de&date=2022-03-31` com header `x-key`.
- ⚠️ ENTSOG (fluxos físicos de gás por ponto, transparency.entsog.eu) não coberto nesta sessão — complemento a validar.

### 2.4 Eurostat 🟢
- API de disseminação **sem chave**; SDMX 2.1 e JSON-stat; base atualizada 2×/dia.
- Mensais: `nrg_cb_em` (eletricidade, confirmado no databrowser), `nrg_cb_pem` (geração por fonte — confirmado via espelho); `nrg_cb_gasm`/`nrg_cb_oilm` **[códigos não confirmados]**.
- **Defasagem (metadata oficial): ~2,5 meses** — papel: consolidação mensal comparável entre países, não alta frequência.
- Padrão: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_cb_em?format=JSON` **[chamada não executada]**.

### 2.5 Nacionais
- **Reino Unido — NESO Data Portal 🟢:** API CKAN aberta sem chave — `https://api.neso.energy/api/3/action/datastore_search` (+ variante SQL). Demanda, previsões, carbon intensity. Site bloqueia bots (403), API não. Recomendação oficial ~1 req/s.
- **Espanha — REData 🟢:** `https://apidatos.ree.es` aberta sem chave — `GET /{idioma}/datos/{categoria}/{widget}` (balance, demanda, generacion, intercambios, mercados), `time_trunc` hora→ano. **ESIOS** (preços finos, PVPC): token grátis por e-mail a consultasios@ree.es **[processo via fontes terceiras]**.
- **França — RTE 🟡:** data.rte-france.com com registro grátis (OAuth2 **[NÃO VERIFICADO]**); ODRÉ (odre.opendatasoft.com) para éCO2mix **[dataset não confirmado nesta sessão]**.
- **Itália — Terna 🟡:** dati.terna.it verificado (carga/geração intradia); API do developer.terna.it **[NÃO VERIFICADO]**.
- **EPEX SPOT / Nord Pool 🔴 (pago):** day-ahead visível de graça só na interface; API/feed = contrato pago. Desnecessário: ENTSO-E A44 + SMARD cobrem day-ahead.

---

## 3. Brasil

### 3.1 ONS 🟢
- **Portal CKAN + bucket S3 público** (`ons-aws-prod-opendata`), sem autenticação. API verificada: `https://dados.ons.org.br/api/3/action/package_list` e `package_show?id={dataset}` → URLs diretas dos recursos.
- **Datasets confirmados:** carga (`carga-energia`, `carga-energia-verificada`, `carga-mensal`, `curva-carga` horária 2000–2026, atualização diária 12h/19h), geração (`geracao-usina-2` horária por usina, `geracao-termica-despacho-2`, `capacidade-geracao`), **EAR/ENA diários** (por bacia, REE, reservatório, subsistema), **CMO** (`cmo-semanal` 2005–2026 por patamar/subsistema; semi-horário anunciado), intercâmbios (nacional e internacional).
- **Formato:** CSV (UTF-8, `;`), XLSX e **Parquet** por ano.
- **Exemplo real:** `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cmo_se/CMO_SEMANAL_2026.csv`
- **Padrão de ingestão:** `package_show` → iterar `resources[].url` filtrando `format == "PARQUET"`.

### 3.2 CCEE 🟢 (via curl_cffi — testado 22/07/2026)
- **dadosabertos.ccee.org.br** (CKAN, CC-BY-4.0). WAF com **fingerprinting TLS**: 403 para curl e Python `requests` mesmo com headers completos de navegador. **Solução testada e funcionando: `curl_cffi` com `impersonate="chrome"`** — API (200, success) e download do CSV ponta a ponta.
- **Teste real (22/07/2026):** PLD horário 2026 baixado — 19.489 linhas, dado até o próprio dia 22/07. Formato: separador `;`, encoding declarado ISO-8859-2, colunas `MES_REFERENCIA;SUBMERCADO;PERIODO_COMERCIALIZACAO;DIA;HORA;PLD_HORA`.
- **PLD:** `pld_historico_semanal_2001_2020` + `pld_horario_2021`…`pld_horario_2026` (horário, por submercado, Dessem); também `pld_media_diaria`/`pld_media_mensal`. Atualização diária (última vista: 21/07/2026 17:14).
- **Download:** URLs tokenizadas `https://pda-download.ccee.org.br/{token}/content` — tokens estáveis nos metadados, **obter sempre via API, não hardcodar**.
- **InfoMercado:** desagregado em ~137 datasets CSV (consumo por ramo/CNAE, geração, contratos, MCP).

### 3.3 ANEEL 🟢
- CKAN pleno sem autenticação (dadosabertos.aneel.gov.br), `package_search` verificado.
- **Bandeiras tarifárias** (desde jan/2015, mensal); **tarifas homologadas TE/TUSD** (CSV 84 MB desde 2010, semanal); **MMGD** (micro/mini GD por fonte, CSV/Parquet); **SIGA** (empreendimentos de geração, versão diária):
  `https://dadosabertos.aneel.gov.br/dataset/6d90b77c-c5f5-4d81-bdec-7bc619494bb9/resource/11ec447d-698d-4ab8-977f-b424d5deee6a/download/siga-empreendimentos-geracao.csv`

### 3.4 ANP 🟢
- Arquivos estáticos sob gov.br/anp (não CKAN), sem autenticação. Índice: https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos
- **Produção de petróleo/gás por poço:** ZIPs mensais (terra/mar/pré-sal), desde 2005, **defasagem ~2 meses** (regra explícita no site). Ex.: `.../arquivos-producao-de-petroleo-e-gas-natural-por-poco/2022/producao-2022-01.zip`. Há agregado por estado (mais leve).
- **Preços de combustíveis (SHPC):** semestral por posto desde 2004 (`.../shpc/dsas/ca/ca-2026-01.zip`); resumo "últimas 4 semanas" agregado por município/UF (atualizado 17/07/2026 — defasagem de dias).
- Importações/exportações e vendas de derivados: páginas existem **[CSVs não verificados individualmente]**.

### 3.5 EPE 🟢
- **Consumo mensal de eletricidade por classe:** XLSX único, série desde 2004, residencial/industrial/comercial/outros, por região/subsistema, cativo vs livre. Defasagem não declarada **[verificar no arquivo — na prática ~1–2 meses]**.
- **BEN:** anual, Séries Históricas Completas desde 1970 **[URL exata do XLSX não verificada]**.

### 3.6 MME / Petrobras
- **MME:** BME migrou de PDF para "Catálogo de Dados Energéticos"/SIE Brasil (painéis) — fonte secundária, preferir ONS/ANP/EPE.
- **Petrobras:** precos.petrobras.com.br (preço de venda às distribuidoras) — só consulta visual, **download estruturado não confirmado**; complemento: SHPC/ANP.

---

## 4. Índia e Ásia

### 4.1 CEA / NPP (Índia) 🟢
- **CEA:** relatórios mensais em PDF **e Excel** com **URL previsível**: `https://cea.nic.in/wp-content/uploads/installed/{YYYY}/{MM}/Website_{Mês}.xlsx` (junho/2026 publicado 15/07 → defasagem ~2 semanas). Capacidade instalada por fonte/estado; geração por usina/combustível. Sem API.
- **NPP (npp.gov.in/publishedReports):** relatórios **diários D-1** de geração e carvão em PDF/XLS (verificado: diário de 21/07/2026), mensais em ~2-4 semanas.

### 4.2 Grid-India / POSOCO 🟡
- PSP diário (demanda atendida, pico, déficit por estado, geração por fonte), D+1, **PDF**, padrão:
  `https://report.grid-india.in/ReportData/Daily Report/PSP Report/{ano-fiscal}/{Mês Ano}/{DD.MM.YY}_NLDC_PSP.pdf`
- ⚠️ Site bloqueou acesso do ambiente de teste (possível geo-block) — **testar da máquina da Ana**; alternativa: Power Supply Report mensal da CEA.

### 4.3 IEX (bolsa de energia da Índia) 🟢
- Página pública verificada com MCP (Rs/MWh) e volumes em blocos de **15 min** do próprio dia (22/07/2026): https://www.iexindia.com/market-data/day-ahead-market/market-snapshot — SPA React, dado vem de API interna JSON não documentada (funcional, mas frágil).

### 4.4 PPAC (petróleo, Índia) 🟢
- Consumo mensal de derivados ('000 t, ano fiscal abr–mar) — **atualizado 22/07/2026, junho/2026 já disponível** (defasagem ~3 semanas): https://ppac.gov.in/consumption/products-wise
- Produção, importação/exportação (incl. GNL) em `/production/petroleum-products`, `/import-export`, `/natural-gas/import`. Relatórios em PDF com nome timestampado — **descobrir o link na página, não construir**.

### 4.5 Ministry of Coal 🟡
- Monthly Coal Statistics baixa sem autenticação (`https://coal.gov.in/sites/default/files/{YYYY-MM}/msg-{mêsYY}.pdf`, verificado 200 OK), **mas o PDF é imagem** → exigiria OCR. Alternativa estruturada: relatório diário de carvão da CEA/NPP em XLS (estoque nas usinas).

### 4.6 data.gov.in 🟡
- Web bloqueia scripts (403, confirmado); **API oficial** `https://api.data.gov.in/resource/{id}` com **chave grátis** (registro no portal), JSON/XML/CSV, 80k+ resources (inclui dados PPAC/CEA). Ressalva: defasagem maior que a fonte primária. **Pendência: registrar chave se for usar.**

### 4.7 China 🔴
- **NBS** (data.stats.gov.cn): 403 a acesso programático (confirmado). Produção mensal de energia existe (release ~dia 15–17; jan+fev sempre acumulado), mas sem via estável fora da China.
- **NEA:** consumo mensal de eletricidade só como press release HTML em chinês.
- **Alternativa honesta:** Ember (CSV aberto, rastreável ao NBS/CEC) — **não é primária**; se usar, rotular explicitamente.

### 4.8 Japão e Coreia 🟡
- **Japão:** ANRE/METI bloqueia scripts (403), mas os dados (geração mensal por fonte/utility, pesquisa nº 00551120) estão no **e-Stat**, que tem **API oficial gratuita** (registro → appId, JSON/XML/CSV): https://www.e-stat.go.jp/api/en. Defasagem ~2 meses. OCCTO: CSV 30-min via portal de formulários (não REST).
- **Coreia:** EPSIS/KPX (epsis.kpx.or.kr, interface em inglês verificada) — geração por combustível, SMP diário/horário; export via endpoints internos do portal (não oficiais).

---

## 5. Cadastros necessários (ação da Ana — contas/chaves)

| # | Fonte | O que | Onde | Custo |
|---|-------|-------|------|-------|
| 1 | EIA | API key | https://www.eia.gov/opendata/register.php | grátis |
| 2 | ENTSO-E | conta + e-mail p/ transparency@entsoe.eu ("RESTful API access") | transparency.entsoe.eu | grátis |
| 3 | GIE AGSI | conta → chave `x-key` | https://agsi.gie.eu/account | grátis |
| 4 | ESIOS (Espanha, opcional) | e-mail p/ consultasios@ree.es | — | grátis |
| 5 | e-Stat (Japão, opcional) | registro → appId | https://www.e-stat.go.jp/api/en | grátis |
| 6 | data.gov.in (opcional) | registro → api-key | https://www.data.gov.in | grátis |

Sem cadastro nenhum já funcionam: SMARD, ONS, ANEEL, ANP, EPE, JODI-Oil, CFTC, Baker Hughes, NESO, REData, Eurostat, CEA/NPP, PPAC.

## 6. Pendências de verificação — atualizado 22/07/2026 após testes em código

**Resolvidas (testadas da máquina local em 22/07/2026):**
1. ~~CCEE~~ → **funciona com `curl_cffi` + `impersonate="chrome"`** (curl e requests puros levam 403 por fingerprint TLS). PLD 2026 baixado ponta a ponta, dado até 22/07. Falta só observar a estabilidade dos tokens de download entre atualizações diárias.
2. ~~Grid-India~~ → **bloqueio confirmado também da máquina local** (reset no handshake TLS, curl e requests). Decisão: usar CEA/NPP como fonte da Índia elétrica; PSP do Grid-India descartado por ora.
3. ~~Eurostat~~ → **códigos confirmados por execução real da API**: `nrg_cb_em` (eletricidade), `nrg_cb_gasm` (gás), `nrg_cb_oilm` (petróleo), todos mensais, último período **2026-06** no agregado EU27 (defasagem efetiva ~1 mês, melhor que os 2,5 meses da metadata — pode haver revisão dos meses recentes).
4. ~~SMARD~~ → **série real executada**: preço day-ahead DE-LU (filtro 4169), último valor 23/07/2026 21h UTC = 170,42 EUR/MWh. API viva e sem chave.

**Ainda pendentes:**
5. ENTSO-E: limite de intervalo por request (~1 ano?) — verificar quando o token chegar.
6. IEA: migração do CSV do MES para formato SDMX (após edição de ago/2026).
7. EPE: defasagem efetiva do XLSX de consumo mensal (checar no primeiro download).
8. SMARD: IDs de filtro para fluxos transfronteiriços (não documentados; ENTSO-E cobre).
9. OPEC: existência real do Excel do apêndice do MOMR (site bloqueou verificação).
10. CCEE: dependência nova do pipeline = pacote `curl_cffi` (já instalado no Python local).

## 7. Riscos de automação mapeados

- **WAF/bloqueio de scripts:** CCEE (403), IEA site (403), data.gov.in web (403), NBS China (403), ANRE Japão (403), NESO site (403 — mas API aberta), Grid-India (reset). Mitigação: UA de navegador onde permitido; APIs alternativas oficiais onde existam.
- **URLs instáveis:** Baker Hughes (UUID semanal), PPAC (timestamp no nome), CCEE (token no path) → sempre descobrir via página/API, nunca hardcodar.
- **Formatos hostis:** Grid-India (PDF), Ministry of Coal (PDF imagem), OPEC (PDF). 
- **Sem fonte primária estruturada:** China (gap conhecido e aceito — rotular qualquer proxy).
