# Metodologia — Pipeline Energia Global

**Última revisão: 23/07/2026.** Este manual documenta as convenções, regras de cálculo e tratamentos aplicados no pipeline. Complementa o `FONTES.md` (levantamento e verificação das fontes). Regra-mãe do projeto: **nenhum número sem rótulo, nenhuma conversão implícita, nenhum fallback silencioso.**

---

## 1. Arquitetura

```
coletores/*.py  →  energia.db (SQLite)  →  gera_dashboard.py  →  energia_dashboard.html
```

- **energia.db**: formato longo. Tabela `series` (metadados: fonte, área, produto, descrição, unidade, frequência, URL de origem) + `dados` (serie_id, data ISO, valor, coletado_em) + `meta` (chave-valor p/ carimbos como hora de cotação).
- **Revisões**: `INSERT OR REPLACE` por (série, data) — a fonte revisou, o banco reflete a revisão. Dado do dia corrente pode ser parcial e é substituído na rodada seguinte.
- **Atualização**: `atualizar_energia.bat` agendado 2×/dia (08:15 e 15:30, Agendador do Windows; log em `log_atualiza.txt`). Rodada manual: `python atualiza.py [coletor...]` + `python gera_dashboard.py`.
- **Chaves** (todas gratuitas) em `.env`: `EIA_API_KEY`, `AGSI_API_KEY`, `ENTSOE_TOKEN`.

## 2. Convenções de apresentação (dashboard)

1. **Título de gráfico = a pergunta econômica em português claro** ("O mundo está acumulando ou queimando estoque?"). O termo técnico (implied stock change, product supplied) vai na linha de fonte.
2. **Abas por tema econômico**, nunca por fonte de dado; cada aba conta a história de cima (macro) para baixo (micro).
3. **Todo painel declara**: fonte, frequência, unidade e ressalvas de cobertura. Todo KPI tem data (e hora, quando intradiário) de referência.
4. **Painel sem nenhuma observação é omitido** automaticamente da geração (com aviso no log) — fonte fora do ar não produz gráfico vazio nem valor inventado; volta sozinho na próxima carga.
5. **Notas de rodapé por aba** (`NOTAS_ABA`) para didática de siglas e conceitos (ex.: aba Gás Europa).
6. **Paleta categórica validada** para daltonismo contra o fundo escuro (#1a1f2e), nos 5 checks do validador (banda de luminosidade, chroma, separação CVD, piso de visão normal, contraste): verde #3aa15f, azul #4590c9, carvão #b3673a, teal #21a38f, ouro #b98a2e, roxo #9673d6, rose #e25d75. **A ordem de empilhamento importa** — foi validada nessa sequência para evitar pares adjacentes confundíveis (ouro↔verde, verde↔teal sob protanopia). "Outros" usa cinza neutro #718096 por convenção de resíduo.
7. Rótulos de país por extenso (nunca código ISO na legenda).

## 3. Convenções de cálculo

### 3.1 Participação (share) de fontes e produtos — BASE ANUAL
Gráficos de **participação** (matriz elétrica por fonte, composição da demanda por derivado) usam **anos completos**: séries diárias exigem ≥360 dias no ano; mensais exigem 12 meses. **O ano corrente parcial é excluído** e a exclusão declarada na linha de fonte.
**Motivo:** a sazonalidade (inverno/verão do hemisfério norte, hidrologia no Brasil) contamina o share mensal — solar "cresce" todo verão sem mudança estrutural nenhuma. Grupo sem dado num ano completo conta zero (ex.: nuclear alemã pós-desligamento) — isso é realidade, não lacuna.
Os empilhados **absolutos** permanecem mensais: neles a sazonalidade é informação.

### 3.2 Anualização de taxas (kb/d)
Séries em kb/d agregadas ao ano são ponderadas pelos **dias de cada mês** (kb/d × dias = volume), nunca média simples de meses.

### 3.3 Preços de eletricidade
Preço day-ahead diário = **média simples dos intervalos do dia** (24 horas ou 96 blocos de 15 min), no **dia local do mercado** (Europe/Berlin para DE-LU; CET para as zonas ENTSO-E coletadas). Rotulado como "média diária dos intervalos".

### 3.4 Fusos e dias
- SMARD: timestamps convertidos ao dia local de Berlim (zoneinfo).
- ENTSO-E: pontos em UTC convertidos a dia CET.
- AGSI/ALSI: "gas day" da fonte, publicado 19h30 CET.
- ONS/CCEE: datas locais da fonte.

### 3.5 Balanço mundial de petróleo
- Oferta e demanda mundiais: **EIA STEO** (`PAPR_WORLD`/`PATC_WORLD`, milhões b/d). O STEO projeta ~18 meses à frente: **a projeção é excluída** (corte no mês corrente); meses recentes são estimativa da EIA e o rótulo diz isso.
- **Variação implícita de estoques = oferta − demanda** (calculado). Rotulada como implícita: contém discrepância estatística e estoques não observáveis (China à frente). O contraponto observável é o **estoque comercial OCDE** (`PASC_OECD_T3`).

### 3.6 Conversões (sempre rotuladas na descrição da série)
- ANP: produção em m³/mês → kb/d com fator **6,28981 bbl/m³** e dias do mês. A série original em m³ também é gravada.
- GWh→TWh, mil barris→milhões: só na camada de exibição, com a unidade no painel.
- Nenhuma conversão de poder calorífico (gás em TWh fica como a fonte publica).

### 3.7 Comparações entre países em tabelas
Usam o **último ano com todas as colunas publicadas** (ex.: consumo da EIA international defasa 1–2 anos vs produção → tabela de balanço usa 2024). Colunas de fontes distintas declaram cada fonte.

## 4. Regras específicas por fonte

### EIA (api.eia.gov/v2)
- Valores numéricos chegam como **string** desde jan/2024 — parser converte.
- Rotas dnav usam facet `series`; STEO usa `seriesId`; international usa `productId`/`activityId`/`countryRegionId`/`unit`.
- International: produção = productId 53 (total liquids); **consumo = productId 5** com `unit=TBPD` (o 53 não tem consumo). Erros 500 transitórios acontecem — rodada seguinte corrige.
- WPSR: quarta 10:30 ET (feriado → quinta). Estoques de gás: quinta 10:30 ET.
- **Shale**: o Drilling Productivity Report e o relatório de DUCs foram **descontinuados pela EIA** (últimas edições jun/2024 e abr/2024) — séries históricas preservadas e rotuladas como encerradas; o acompanhamento corrente usa produção mensal por estado (TX/NM/ND), produção semanal e rigs Baker Hughes. "Licenças/permits" são dado de agências estaduais, não EIA.

### CME Group (futuros — a FONTE PRIMÁRIA dos preços; substitui o Yahoo desde 23/07/2026)
- Para preço de futuros, a bolsa é a fonte primária: os contratos WTI (CL) e Brent Last Day (BZ) são formados na própria CME, e a cotação atrasada publicada no site dela é publicação oficial do originador do dado — redistribuidores (Yahoo etc.) derivam dali.
- Acesso pelo endpoint que alimenta o site (`/CmeWS/mvc/quotes/v2/{productId}`; CL = 425, BZ = 424), atraso de 10 min declarado na própria resposta (`quoteDelay`). Ressalva de **engenharia** (não de procedência): endpoint sem documentação pública, pode mudar sem aviso. A EIA permanece como fonte das séries longas oficiais de spot (WTI Cushing, Brent, Henry Hub).
- **Pareamento de vencimentos (regra crítica, aprendida no Yahoo):** contínuos de redistribuidores rolam em datas diferentes e podem inverter o spread WTI-Brent. Aqui o front month do CL define o vencimento e o Brent cotado é o contrato BZ do **mesmo mês**, casado por código (CLU6 → BZU6). KPI mostra contrato e hora.
- Mercado fechado → usa o settlement anterior, rotulado "(settle anterior)".
- A API não fornece histórico: a série diária acumula um ponto por pregão. Pontos até 23/07/2026 vieram do Yahoo (mesmos dados CME redistribuídos) — emenda documentada na descrição da série.

### JODI (petróleo, mensal, auto-reportado)
- Marcador de faltante é `"-"` → tratado como **ausente, nunca zero**.
- **Painel de demanda por produto**: 14 grandes consumidores fixos, ex-Brasil (parou de reportar em 2022; Brasil vem da ANP). Um mês só entra se **todos** reportaram — evita queda artificial na ponta; o custo é a defasagem seguir o país mais lento (Índia, ~2 meses extras).
- **Jet fuel**: exige 13 países ex-China — a China não desagrega `JETKERO`; o jet chinês vem como `KEROSENE` e fica no grupo "Querosene e outros" (rotulado nas duas pontas). **Nafta**: painel só desde 2016.
- **Refino** (`REFGROUT`): produção de refinaria por produto, 20 países; as séries **param onde o país parou de reportar** (Rússia 2023, Brasil 2022, Emirados 2018) — sem interpolação, com a lacuna no rótulo.
- **Último mês de refino descartado**: submissões preliminares produzem valores impossíveis (caso detectado em 23/07/2026: EUA mai/2026 = 23,8 Mb/d, acima da capacidade física instalada, assessment code 2; China com quedas de cobertura, code 3). O mês entra na rodada seguinte, já revisado. As demais séries JODI por país (produção, demanda, X/M) permanecem como reportadas, com a ressalva de revisão — o painel de demanda já é protegido pela regra do mês completo.
- X/M de **cru** (`TOTEXPSB`/`TOTIMPSB`); "—" nas tabelas = país não reporta.

### GIE AGSI+/ALSI (gás Europa, diário)
- Header `x-key`; o User-Agent padrão do Python leva 403 → usar `curl_cffi`/UA de navegador. ALSI sem filtro devolve vazio — usar `type=eu` ou `country=`. Atribuição CC obrigatória.

### SMARD/Bundesnetzagentur (Alemanha)
- API JSON sem chave; IDs de filtro do openapi oficial (bundesAPI). CC BY 4.0.
- Preço DE-LU **existe desde out/2018** (separação da zona DE-AT) — a série começa aí por definição, não por lacuna. Nuclear zera no phase-out (abr/2023; últimas observações jan/2024).

### ENTSO-E (API R3)
- 400 req/min por **token**; máx **1 ano por request** (guia oficial); geração por usina = 1 dia/request (não usar). Timeout 300 s.
- Mercado em **PT15M** desde 2025. **Curva A03 omite valores repetidos** → o parser preenche posições faltantes com o último valor (curva A01 não preenche).
- XMLs anuais de geração dão **504** esporádico → a janela é dividida ao meio recursivamente (mín. ~46 dias).
- Incremental: últimos 45 dias — o dia corrente parcial é substituído.

### ONS
- CKAN + S3 público; preferir Parquet/CSV anuais. `id_subsistema` vem com espaços — strip.
- Carga SIN = soma dos 4 subsistemas. **EAR SIN = Σ(MWmês verificado)/Σ(EAR máx)** — agregado calculado, rotulado.
- Geração por fonte SIN: balanço horário somado entre subsistemas e convertido em média diária (MWmed).
- Incremental: após o backfill, só arquivos do ano corrente e anterior.

### CCEE
- WAF por **fingerprint TLS**: exige `curl_cffi` com `impersonate="chrome"` (User-Agent não basta). URLs de download tokenizadas — **sempre descobrir via API**, nunca fixar.
- PLD diário (2021+, Dessem/horário) e PLD mensal (2001+, inclui era semanal) ficam em **séries separadas** — metodologias distintas não se emendam.
- Datas em `d/m/yyyy` sem zero à esquerda — normalizadas com zfill.

### ANP
- CSV em **UTF-8 com BOM** (não latin-1). **Meses futuros vêm preenchidos com zero** → mês só entra se o total nacional > 0. Defasagem ~2 meses.

### EPE
- XLSX com blocos verticais por ano; linha-total é "TOTAL {CLASSE}" (só a aba TOTAL usa "TOTAL BRASIL"). Anos com `*` = preliminares (rotulado).

### Baker Hughes
- Links `/static-files/{uuid}` **mudam toda semana** → o coletor lê a página, nunca fixa URL. Arquivo atual (2024+) tem precedência; o histórico (2013+) preenche apenas datas que o atual não cobre (evita dupla contagem na sobreposição).

### CFTC
- Socrata sem chave; WTI = `067651` (WTI-PHYSICAL), Henry Hub = `023651` (NAT GAS NYME), Disaggregated Futures Only. Managed money net = long − short.

### IEA MES
- Via `api.iea.org` — **API do site, não documentada** (o site bloqueia scripts; a API não). "IEA Total" = **países-membros, não o mundo** — rotulado. Defasagem ~3 meses. Atenção: CSV oficial migra para SDMX após ago/2026.

### FAOSTAT
- Bulk CSV (a API REST estava instável); `curl_cffi`. Toneladas → mil t. Anual, defasagem ~2 anos.
- Fertilizante é economicamente um capítulo do **gás natural** (amônia via Haber-Bosch; China via carvão) — por isso a aba referencia a demanda de gás, não de petróleo.

### Eurostat
- API de disseminação sem chave. Gás da química: `nrg_bal_c`, `nrg_bal=FC_IND_CPC_E`, `siec=G3000`, `unit=GWH` (o TJ_GCV não retorna valores). Inclui amônia sem desagregar fertilizante.

## 5. Gaps conhecidos (decisões, não esquecimentos)

| Gap | Situação |
|---|---|
| China (energia) | NBS bloqueia acesso programático; sem fonte primária estruturada. Petróleo da China entra via JODI (ela reporta). Qualquer proxy (Ember) deve ser rotulado como não-primário. |
| TTF diário | ICE Endex, pago. Sem fonte primária gratuita — não exibido (dito na nota da aba de gás). |
| Reservas estratégicas | Série oficial aberta só EUA (SPR/EIA semanal). IEA publica estoques de membros só em gráfico no site (sem API — sondado 23/07/2026). China opaca; Índia divulga capacidade, não série. |
| Grid-India | Bloqueia conexões (TLS reset) — Índia elétrica viria de CEA/NPP (pendente de construção). |
| Rússia pós-2023 | Parou de reportar ao JODI; produção segue visível via EIA international (estimativa da agência). |

## 6. Histórico de decisões relevantes

- **22/07/2026** — levantamento de fontes (4 agentes, tudo verificado ao vivo); núcleo do pipeline (EIA, AGSI, SMARD, ONS, CCEE, JODI, CFTC, ANP, Baker Hughes, EPE); dashboard v1.
- **23/07/2026** — ENTSO-E integrado (token ativo); reestruturação do dashboard por pergunta econômica (feedback Ana: sem jargão, macro→micro); barras de variação implícita de estoques; painel por produto; refino; fertilizantes; tabelas de balanço e de crescimento da produção; **bug do spread WTI-Brent pego pela Ana** → regra de pareamento de vencimentos; **shares em base anual** (decisão Ana: sazonalidade não contamina estrutura).
