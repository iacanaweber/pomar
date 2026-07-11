# 🌳 Pomar — Auditoria v4 (estado pós-v3): funções, UX e o caminho da bola de neve

> **O que é este documento.** Auditoria do Pomar **como ele está hoje** (HEAD `8e41822`, pós-entrega da v3),
> sob a ótica de quem quer **viver de dividendos** com uma carteira previdenciária Barsi/Bazin. Produzida por
> uma auditoria multi-agente (**78 agentes**: 5 mapeadores de subsistema, 4 críticos especializados —
> motor financeiro, renda/projeções, UX/design, estrategista previdenciário — e ~65 verificadores
> adversariais). Dos **51 achados reportados, 50 sobreviveram** à verificação; 1 foi refutado com teste
> empírico contra o endpoint real do StatusInvest (Apêndice B).
>
> **Escopo.** Correção financeira, funcionalidades e UX. Segurança da informação está **fora do escopo**
> (app pessoal, nunca exposto, acesso via VPN). Integridade dos dados locais está **dentro** do escopo.
>
> **Garantia de dados.** Nenhum item do plano exige redigitar dados. Dos 50 achados, apenas 2 pedem
> mudança de schema — ambas **migrações aditivas** (tabelas novas), sem tocar em linha existente do
> `pomar.db`. O primeiro item do roadmap é justamente backup automático.
>
> Severidades **verificadas** (não as alegadas): 🔴 crítico · 🟠 alto · 🟡 médio · ⚪ baixo.

---

## Parte I — Veredito

**A v3 entregou o que a auditoria anterior pediu — e entregou bem.** O placar (Parte II) mostra ~20 dos
~24 itens do roadmap v3 concluídos: o volume do SQLite (o 🔴 operacional) está no `docker-compose.yml`,
a reserva/renda fixa existe com rendimento por dias úteis B3 e % do CDI real (SGS/BCB), o preço-teto
apareceu na UI (CeilingBadge), o DY virou trailing-365d, o JCP líquido (×0,85) é calculado, o Bazin é
configurável (inclusive dinâmico pela Selic), o BESST ficou graduado, a normalização por setor existe,
YoC, calendário, meta de renda com Aportador, watchlist na UI, perfil BESST da carteira, onboarding e
dark mode — tudo verificado no código com file:line.

**O problema agora não é o que falta fazer; é que os números que o app mostra têm viés otimista
sistemático — e todos na mesma direção.** Quatro vieses independentes se **compõem**:

1. 🔴 A projeção da bola de neve modela "crescimento dos proventos" como **expansão perpétua do yield**
   sobre um patrimônio que nunca valoriza — no cenário default (DY 8%, growth 5%), a renda projetada em
   20 anos sai **~3× maior** do que num modelo consistente.
2. 🟠 Não há **inflação** em lugar nenhum: a meta é digitada em reais de hoje e comparada com renda
   nominal de daqui a 20 anos (a 4% de IPCA, R$ 10.000 nominais valem ~R$ 4.500 de hoje).
3. 🟠 Renda atual, meta e calendário usam **DY bruto** — o `dividend_yield_net` (JCP ×0,85) é calculado
   e jogado fora. Numa carteira BESST cheia de bancos, a renda "que cai na conta" é até ~15% menor.
4. 🟡 Amortização de FII conta como renda; sazonalidade divide só pelos anos pagos; teto de Bazin ignora
   anos sem pagamento — três vieses menores, todos para cima.

Para um app cuja função é planejar a aposentadoria, **viés otimista composto é o pior defeito possível**:
o usuário aporta menos do que precisa acreditando que chega. A Fase 0 do plano ataca exatamente isso.

**A segunda descoberta central: a bola de neve real é invisível.** O Pomar projeta a bola de neve
hipotética, mas nunca lê os **dividendos efetivamente recebidos** que já estão no Ghostfolio
(`/api/v1/portfolio/dividends`), não grava nenhum snapshot histórico (patrimônio/renda/YoC ao longo dos
meses), descarta os **proventos já anunciados** que chegam no payload do StatusInvest, e não tem UI para
registrar aportes executados (a API `/orders` existe, os hooks existem — falta o botão). Resultado: o
app responde "quanto eu teria em 2046?" mas não responde **"quanto caiu na conta este mês?"**, "quando
paga o próximo?", "meu YoC subiu?" — que são as perguntas que sustentam a disciplina por décadas.
Tudo isso é implementável **sem digitar um dado sequer**: as fontes já estão conectadas.

**E o motor, que a v2/v3 acertaram no desenho, tem calibrações que traem o método em casos reais:**
qualquer banco fora dos 5 curados (BRSR6, ABCB4, BPAC11…) cai para afinidade BESST 0,3 e fica
**inelegível na estratégia Barsi** — o "B" do BESST quebra exatamente onde Barsi mais compra; um
ETF/BDR sem dados herda 100% do peso na única métrica que tem (gap de rebalanceamento) e pode virar
**rank nº 1 com score 100**; e a margem Bazin — a métrica-símbolo do método — é normalizada por
percentil, então um ativo **acima do teto** pontua alto se os pares estiverem piores.

> **Resumo de uma linha:** a v3 completou as funcionalidades; a v4 precisa **devolver a verdade aos
> números** (Fase 0), **mostrar a bola de neve real** com dados que já existem (Fase 1) e **fechar o
> ciclo do aporte** (Fase 2).

---

## Parte II — Placar: roadmap v3 × código atual

Conferido item a item no HEAD (`git log 783d81b..HEAD` + leitura dos arquivos citados).

| Item do roadmap v3 | Status | Evidência |
|---|---|---|
| 🔴 Volume SQLite no Docker | ✅ | `docker-compose.yml:14-16` + volume `pomar-data` |
| 🟠 Renda fixa / reserva (P0) | ✅ | `services/fixed_income.py` (dias úteis B3, % CDI via SGS), `reserve.py`, `ReservePage.tsx`, split do aporte em `routes_plan.py:83-126` |
| 🟡 Preço-teto na UI | ✅ | `_bazin_ceiling_price` (`scoring.py:139-150`), `CeilingBadge.tsx`, `AssetPage.tsx:78` |
| 🟡 DY trailing-365d | ✅ | `statusinvest.py:64-69` + fallback Fundamentus (`market_data.py:62-68`) |
| 🟡 JCP ×0,85 | ✅ (calculado) | `statusinvest.py:60`, `dividend_yield_net` em `market_data.py:67` — **mas nunca usado no planejamento** (Parte IV) |
| 🟡 Bazin 6% fixo → configurável | ✅ | `resolve_bazin_target_yield` (`scoring.py:50-57`), modo `dynamic_selic` |
| 🟡 BESST graduado | ✅ | `SECTOR_AFFINITY_MAP` (`config.py:160-177`) — com furo nos bancos (Parte III) |
| 🟡 Normalização por setor | ✅ | `scoring.py:329-338` — inoperante para 3 dos 5 setores BESST (Parte III) |
| 🟡 Janela Bazin 5 anos, piso 3 | ✅ | `scoring.py:35-36,133-137` |
| 🟡 Liquidez R$ 5 mi (Barsi) | ✅ | `strategies.py:27,37-39` |
| 🟡 Payout médio 5 anos, FII isento | ✅ | `scoring.py:240-253,273-280` |
| 🟡 Yield on Cost | ✅ | `analytics.py:31-51`, `YocCell` na `PortfolioPage.tsx:234` |
| 🟡 Calendário de proventos | ✅ | `services/calendar.py`, `CalendarPage.tsx` — só sazonalidade (Parte IV) |
| 🟡 Meta de renda + Aportador | ✅ | `/income/goal`, `GoalProgress` |
| 🟡 Watchlist na UI | ✅ | `WatchlistPage.tsx` — sem dados de decisão (Parte VI) |
| 🟡 Perfil BESST da carteira | ✅ | `PortfolioPage.tsx:52,100` |
| 🟡 Onboarding · dark mode · toasts | ✅ | `Onboarding.tsx`, `ThemeToggle`, `SavedToast` |
| ⚪ ROE pontuado | 🟡 Parcial | só green flag (`scoring.py:483`), não entra no score |
| 🟡 Histórico "já comprei" | 🟡 Parcial | API `/orders` viva; **sem UI**; `plan_history` sem INSERT |
| 🟡 Teto por classe | 🟡 Parcial | backend aceita, UI não envia |
| Lote real (100 ações) | ❌ | `market_data.py:103` hardcoda `lot_size=1` |
| Rentabilidade vs CDI/IBOV | ❌ | `net_performance_pct` capturado (`ghostfolio.py:87`) e descartado |
| Consistência com CAGR/cortes | ❌ | `_dividend_consistency` segue `anos_pagos/anos` |
| Golden test parser Fundamentus | ❌ | só o log `parser_suspect` |

---

## Parte III — O motor de score

### 🟠 M1. O "B" do BESST quebra fora dos 5 bancos curados `banco-afinidade-financ`
`config.py:175` mapeia `"financ" → 0.3`; só `"banco"/"bank"` valem 1,0. Mas o Fundamentus classifica
bancos como **"Intermediários Financeiros"** (`fundamentus.py:53`) — casa com `"financ"` → 0,3. Os 5
curados (BBAS3/ITUB4/BBDC4/SANB11/ITSA4, `watchlist.py:52`) têm setor sobrescrito; **qualquer outro
banco** (BRSR6, ABCB4, BMGB4, BPAC11…) vira "não-banco": afinidade 0,3 e **inelegível na estratégia
Barsi** (`strategies.py:32-33`).
**Correção:** mapear `"intermediários financeiros" → 1.0` (ou extrair o Subsetor do Fundamentus, que
traz "Bancos"), mantendo corretora/fintech em 0,3. Teste com o setor real.

### 🟠 M2. Ativo com 1 métrica herda 100% do peso `redistribuicao-peso-total`
`scoring.py:381-391`: o peso das famílias sem dado é redistribuído para as que têm. Um ETF/BDR sem
DY/valuation (brapi só dá preço/setor, `market_data.py:53-59`) fica só com `rebalance_gap` — que vale
então 100% do peso. Se a classe estiver sub-alocada, **BOVA11 sai rank nº 1 com score ~100**, acima de
ITUB4 com 8 métricas.
**Correção:** renormalizar só **dentro** da família; família sem dado contribui 0 (score máximo do
ativo = fração de peso coberta por dados). Exibir a completude no rank.

### 🟡 M3. Margem Bazin normalizada por percentil, não por âncora `bazin-margem-percentil`
`scoring.py:89-90` usa `norm: "pct"` — contradizendo a racionalização do próprio arquivo (`:11-12`),
que justifica âncoras "ao contrário de um percentil que premiaria a 'menos cara' de um grupo todo
caro". Ativo **acima do teto** pontua alto se os pares estiverem piores; a magnitude da margem (+50%
vs +2%) é descartada. **Correção:** `norm: "anchor"` com clamp em [0,1], como a Margem Graham.

### 🟡 M4. Preço-teto ignora anos sem pagamento `teto-media-anos-pagos`
`scoring.py:135-136,149`: a média usa só anos **pagos**. Quem pagou R$ 2 em 2021-23 e zero em 2024-25
mantém teto de R$ 33 e chip "🟢 abaixo do teto" — a armadilha exata que o teto quer evitar.
**Correção:** dividir pela janela completa (zeros incluídos), mantendo o piso de 3 anos pagos.

### 🟡 M5. Amortização de FII conta como renda `amortizacao-conta-como-renda`
`statusinvest.py:29-35,70-77`: todo tipo (`et`) entra no DY, no teto e na sazonalidade. Amortização é
devolução de principal, não renda — FII amortizando sobe no ranking de dividendos.
**Correção:** filtrar `"amortiza"`/`"subscri"` em `_windowed`, `_trailing_365` e `monthly_seasonality`.

### 🟡 M6. Dívida/EBIT penalizada com limiar de EBITDA `divida-ebit-como-ebitda`
`fundamentus.py:56-60` calcula Dív.Líq÷**EBIT** (proxy admitido), mas `scoring.py:268-271` pune >3
(limiar de EBITDA) e a UI rotula "Dív. líq./EBITDA" (`AssetPage.tsx:125`). Como EBIT < EBITDA, o corte
pega mais forte justamente as utilities de capital intensivo — **energia e saneamento, o coração do
BESST**. **Correção:** recalibrar limiar para o proxy (~4/5) ou buscar EBITDA real; corrigir o rótulo.

### 🟡 M7. Barsi/Graham zeram FIIs/ETFs silenciosamente `barsi-graham-zeram-classes`
`strategies.py:31-33,45-46` + `allocation.py:74-87`: com estratégia Barsi, FIIs ficam inelegíveis e o
orçamento da classe é realocado para ações **sem aviso** — a meta de 30% FII que você configurou é
ignorada sem explicação. **Correção:** aplicar filtros só à classe STOCK, ou warning explícito no plano.

### 🟡 M8. Glossário ensina um modelo mental errado `glossario-promessas-divergem`
`glossary.py:111-127` promete "estratégia só muda os pesos" e score = "média ponderada" — mas
estratégias **filtram/zeram** e o score é `composite × Q`. A soma do ScoreBreakdown não reproduz a nota.
Para um app cuja tese é transparência, o tooltip mente na hora da decisão. **Correção:** sincronizar
os textos com o motor (citar qualidade, elegibilidade e as três normas).

### 🟡 M9. "Dividend Growth" não mede crescimento `dividend-growth-sem-crescimento`
Único filtro: consistência ≥ 0,6 (`strategies.py:65-68`); nenhum CAGR no scoring; um corte de 90% no
provento mantém consistência 1,0 (`scoring.py:181`). **Correção:** métrica de crescimento real (CAGR
5a de `dividends_by_year`) com subweight próprio + filtro >0 no preset; penalizar quedas >50% a/a.

### ⚪ M10. Percentil por setor só funciona para bancos e energia `peer-setor-so-bancos-energia`
`SECTOR_PEER_MIN = 4` (`scoring.py:39`) vs universo curado com Saneamento=3, Seguros=3, Telecom=2
(`watchlist.py:56-61`) — 3 dos 5 setores BESST caem no fallback por classe (SBSP3 percentilada contra
VALE3). **Correção:** macro-setores curados ("utilities reguladas") ou `SECTOR_PEER_MIN=3`; mostrar o
`peer_group` na UI.

---

## Parte IV — Renda, projeções e a matemática da bola de neve

### 🔴 R1. A projeção da bola de neve é ~3× otimista com growth > 0 `snowball-growth-yield`
`analytics.py:77-83`: `cur_yield = annual_yield × (1+growth)^anos` sobre um `value` que **nunca
valoriza** (só cresce por aporte e reinvestimento). O yield expande perpetuamente — 8% vira 21% em 20
anos com growth 5% — algo que não existe: quando o dividendo cresce, o preço acompanha e o yield fica
~estável. Simulação verificada: 100k iniciais + R$ 1.000/mês, DY 8%, growth 5% (default da UI,
`IncomePage.tsx:39`), 20 anos → Pomar projeta **R$ 47.080/mês**; um modelo consistente dá ~R$ 15-16 mil.
`required_monthly_contribution` (`analytics.py:117`) e `estimated_years_to_goal` (`:151`) herdam o viés:
**você aportaria menos do que precisa**.
**Correção:** separar preço e yield — a cada mês `value = value×(1+g)^(1/12) + value×dy/12 + aporte`,
renda = `value × dy` com **DY constante** (growth passa a valer para preço+dividendo juntos). Verificado:
com g=0 os dois modelos coincidem, então a mudança não altera projeções sem crescimento. Ajustar
`test_analytics.py`.

### 🟠 R2. Nenhum ajuste de inflação em lugar nenhum `sem-inflacao`
`analytics.py:104-154` e `routes_income.py:94-100` comparam renda **nominal** futura com meta em reais
de hoje; grep por inflação/IPCA no repo: vazio. A 4% a.a., o "meta atingida em ~20 anos" entrega metade
do poder de compra. **Correção:** premissa de inflação no simulador e no goal, reportando em reais de
hoje; alternativa mínima: rotular "valores nominais" e documentar `annual_growth` como crescimento
**real**.

### 🟠 R3. Todo o planejamento usa DY bruto; o líquido é calculado e descartado `renda-dy-bruto` + `renda-bruta-jcp` + `renda-liquida`
Três críticos independentes acharam o mesmo problema (sinal forte). `routes_income.py:30` alimenta
renda atual, meta e simulador com `dividend_yield` bruto; `market_data.py:64-68` calcula
`dividend_yield_net` (JCP ×0,85) que só a AssetPage mostra; a sazonalidade do calendário soma `v` bruto
sem `_net_factor` (`statusinvest.py:175`). Carteira BESST = bancos/seguradoras = JCP pesado: a renda
"para viver" sai até ~15% inflada — e o glossário (`glossary.py:42-44`) manda "usar o líquido para
planejar", que é exatamente o que o app não faz.
**Correção:** `dividend_yield_net` (fallback bruto) em `_portfolio_income_now`, `/income/goal` e na
semente do simulador; `_net_factor` na sazonalidade; IncomePage exibe "R$ 1.870 líquidos · R$ 2.000
brutos".

### 🟡 R4. Sazonalidade divide pelos anos COM pagamento `seasonality-anos-pagos`
`statusinvest.py:169-177`: pagador de 2 em 5 anos tem a média dividida por 2 — viés para cima nos
irregulares, justamente quem merece desconto. **Correção:** dividir pela janela (convenção do
`_windowed`, que já preenche zeros).

### 🟡 R5. UI aceita growth negativo; backend rejeita com 422; simulador some mudo `growth-negativo-422`
`IncomePage.tsx:60-174` envia até −10%; `models/analytics.py:71` exige `ge=0`; o erro não é renderizado
— o painel só desaparece. O **único cenário pessimista** é impossível de rodar. **Correção:** `ge=-0.5`
no backend + exibir `proj.error`.

### ⚪ R6. Dois vieses menores, ambos para cima `capitalizacao-fim-de-ano`
`analytics.py:90` (renda anual sobre patrimônio de dezembro) e `:78` (y/12 mensal composto = taxa
efetiva maior). Frações de ponto que compõem por 20-30 anos. **Correção:** acumular dividendos
creditados e usar `(1+y)^(1/12)−1`.

### ⚪ R7. DY 0% + meta → "aporte necessário: R$ 0,00/mês" `required-yield-zero`
`analytics.py:113-114` retorna 0.0 (sucesso) em vez de None (impossível). Mina a confiança no teste de
sanidade mais básico. **Correção:** retornar None (a UI já oculta).

### ⚪ R8. Goal ignora a reserva `goal-ignora-reserva`
`/income/goal` usa o aporte integral, mas o plano desvia parte para a reserva enquanto ela não enche
(`routes_plan.py:95-98`) — e a renda da RF tampouco conta. Módulos lado a lado contam histórias
diferentes sobre o mesmo aporte. **Correção:** usar o `aporte_rv` esperado do split; ver E4.

---

## Parte V — Reserva / renda fixa

### 🟡 F1. Resgate no meio do período infla a taxa (e o % do CDI) `dietz-fluxos`
`fixed_income.py:108-129` não pondera fluxos pelo tempo: depósito 10k em jan, resgate 5k em nov, saldo
5.600 em dez → ~13% a.a. exibido quando a taxa real é ~7,6%. O "aporte como base" do commit `8e41822`
está certo para o caso simples; falta ponderação temporal nos demais. **Correção:** Modified Dietz
(denominador = principal + Σ fluxo × fração de dias úteis restantes, reusando `business_days_between`)
+ teste com resgate no meio.

### 🟠 F2. A página Reserva não mostra meta, gap nem progresso `reserva-sem-meta-na-pagina`
`ReservePage.tsx:315-323` exibe só total + CDI; a barra alvo/gap vive **dentro do plano** e só se
`reserve_target > 0` — campo enterrado em "Ajustes avançados" com default 0 (`PlanControls.tsx:38,197`).
A jornada "como está minha reserva vs meta?" não tem tela; a prioridade "reserva antes de tudo" (pilar
Barsi) fica invisível. **Correção:** barra alvo/atual/gap na própria ReservePage (incluir
`reserve_status` no `/fixed-income/summary`) com edição do alvo ali; definir reserva-alvo no Onboarding.

### 🟡 F3. Arquivar conta é sem volta na UI (e parece exclusão) `arquivar-sem-volta-na-ui`
`ReservePage.tsx:295` filtra `!archived` sem visão de arquivadas; botão "🗑" com `confirm()` nativo; o
PATCH de desarquivar existe (`client.ts:119-120`) e não é usado. Para o usuário, anos de histórico
"somem" — exatamente o medo de quem não aceita perder dados. **Correção:** "📦 Arquivar (pode
desfazer)" + toggle "mostrar arquivadas" + desarquivar/renomear via PATCH existente.

### ⚪ F4. Feriados B3 só até 2027 `feriados-b3-2028`
`holidays_b3.py` termina em 2027; em 2028 a anualização degrada silenciosamente (<1%, mas sem aviso).
**Correção:** gerar feriados móveis pelo algoritmo de Gauss (Páscoa) ou logar warning para anos não
cobertos.

---

## Parte VI — UX: as quatro jornadas

**J1 — "Chegou o salário": gerar plano → executar → registrar.**
- 🟠 **U1. A jornada morre depois do plano** `j1-registro-execucao` + `ordens-sem-ui-streak`: a API
  `/orders` (POST/GET/DELETE, `total_invested`) e os hooks `useOrders/useCreateOrder` existem
  (`queries.ts:137-153`) — **nenhum componente os usa** (grep vazio). Não há onde marcar "já comprei",
  nem histórico de aportes, nem streak de disciplina. **Correção:** botão "Registrei a compra" em cada
  card do RankedList (pré-preenchido com `shares × price` do `suggested`) + seção "Histórico de
  aportes" com total investido e "N meses seguidos aportando".
- 🟠 **U2. O plano evapora ao trocar de aba** `plano-volatil` + `plan-history-morto`: `usePlan` é
  mutation com estado local (`queries.ts:81`); navegar (ou ir à corretora e voltar) perde o plano e
  força re-gerar (POST de até 60s). `plan_history` existe no schema (`db.py:59`) com **zero INSERT**.
  **Correção:** gravar request/response no POST `/plan` (devolvendo `plan_id`), cachear no queryClient,
  e "último plano gerado em <data>" ao montar a PlanPage.

**J2 — "Quanto minha renda cresceu? Quando cai o próximo provento?"**
- 🟠 **U3. Só existe o instante presente** `renda-sem-historico` (ver E1/E2 na Parte VII): sem série
  histórica, se o DY de mercado cai a "renda estimada" **diminui** mesmo com mais cotas — o app passa
  sensação de regressão em plena acumulação.
- 🟡 **U4. "Próximo provento" não tem resposta** `proximo-provento-descartado` (ver E3): o calendário é
  média sazonal; os pagamentos **anunciados** com data são baixados e descartados.

**J3 — "Está abaixo do teto? É hora de comprar?"**
- 🟠 **U5. Chip mente nos "Outros candidatos"** `chip-teto-falso-negativo`: `RankedList.tsx:51` passa
  `price = suggested?.price ?? null` — não sugeridos exibem "teto não calculado" **mesmo com teto e
  margem calculados** pelo backend (`CeilingBadge.tsx:24-25` ignora `margin`/`belowCeiling`; a prop
  `belowCeiling` nem é usada). A tela esconde oportunidades Bazin da maioria do ranking. **Correção:**
  classificar pela `margin` quando `price == null`; remover a prop morta.
- 🟠 **U6. Watchlist sem dado de decisão** `watchlist-sem-dados-decisao`: `WatchlistPage.tsx:31-55`
  mostra ticker, classe e chip de validação — nem preço, nem DY, nem teto, nem score. A aba "Descobrir"
  promete radar e entrega lista inerte. **Correção:** enriquecer cada linha (preço, DY, CeilingBadge),
  ordenar por margem sobre o teto — transformar em radar de zona de compra.
- 🟡 **U7. Sinal da margem invertido** `margem-sinal-invertido` + `ceiling-badge-sinal-invertido`:
  `CeilingBadge.tsx:50` usa `m >= 0 ? "−" : "+"` — margem +12% (desconto, "bom" segundo o glossário)
  vira "−12%" no chip, enquanto o breakdown do MESMO card mostra "12%". **Correção:** unificar a
  convenção (positiva = desconto): "abaixo do teto (+12%)" ou "desconto de 12%".
- 🟡 **U8. "Próximo melhor aporte" ignora sua estratégia** `nextbuy-ignora-estrategia` (2 críticos):
  `GoalProgress.tsx:13` hardcoda `strategy: "equilibrado"` e parâmetros default — um barsista recebe
  conselho de outra filosofia no card mais acionável da aba Renda, e paga um POST /plan de 60s a cada
  mount. **Correção:** usar `prefs.data` + cachear com staleTime; exibir "segundo sua estratégia Barsi".

**J4 — "Como está minha reserva?"** → ver F2.

**Transversais:**
- 🟡 **U9. Tooltips das metas não existem e a Reserva usa a explicação errada**
  `glossario-lacunas-e-tooltip-errado`: `reserve_target`/`income_target` não existem no glossário
  (Tooltip silencia); o ⓘ de "Último rendimento" da Reserva usa `net_yield` — texto sobre JCP de ações
  para um CDB. **Correção:** entradas próprias no `glossary.py`.
- ⚪ **U10. Zoom forçado no iOS** `ios-zoom-inputs`: inputs com 14-15px (`index.css:312,115,420`)
  disparam zoom do Safari — atrito recorrente no uso mobile via VPN. **Correção:** `font-size: 16px`
  (ou `max(16px, 1em)`).
- ⚪ **U11. Tags da reserva quebram no dark mode** `dark-mode-tags-reserva`: `.tag-balance/deposit/
  withdrawal` com pastéis hardcoded (`index.css:375-377`) fora dos tokens. **Correção:** tokens com
  variante `[data-theme="dark"]`.
- ⚪ **U12. Erro aponta para tela "Ajustes" que não existe** `mensagem-ajustes-inexistente`:
  `client.ts:47` vs navegação real (`App.tsx:24-31`). **Correção:** instrução real + botão "tentar de
  novo".

---

## Parte VII — Lacunas estratégicas: o que falta para magnificar a bola de neve

O padrão: **cada motor da bola de neve tem a infraestrutura pronta e falta a última milha.**

### 🟠 E1. O Pomar nunca lê os dividendos RECEBIDOS `renda-realizada` (o achado mais transformador)
`ghostfolio.py` consome exatamente 2 endpoints: `/portfolio/holdings` e `/health`. Os proventos que
efetivamente caíram na conta — que **já estão no Ghostfolio** (`/api/v1/portfolio/dividends?groupBy=month`)
— nunca são lidos. Toda a "renda" exibida é estimativa `valor × DY`. Sem renda realizada não há: série
mês a mês da bola de neve real, validação do DY estimado, base para sugerir reinvestimento.
**Correção:** método novo no `GhostfolioClient` + rota `GET /income/realized` + seção "Renda recebida"
na IncomePage (barras mensais 24m, total 12m, estimado vs recebido). **Zero redigitação.**

### 🟠 E2. Sem snapshot mensal — impossível VER a bola crescendo `snapshot-mensal-yoc`
YoC é calculado ao vivo e descartado (`analytics.py:31`); nenhuma tabela de histórico. O YoC subindo
ano após ano é a prova visual do método. **Correção:** migração **aditiva** v4 — tabela
`portfolio_snapshots (date, total_value, annual_income, portfolio_yield, yield_on_cost, snapshot_json)`
gravada oportunisticamente no primeiro acesso do mês (sem cron); gráfico "sua bola de neve real"
sobreposto à projeção; YoC atual vs 12 meses atrás na AssetPage.

### 🟠 E3. Proventos anunciados são descartados `proventos-anunciados`
`statusinvest.py:74` filtra `cutoff < d <= today` — pagamentos com data futura, que **já vêm no JSON
cacheado**, são jogados fora. "BBAS3 paga R$ 0,45 dia 12/08 → você recebe R$ 213" é planejamento de
reinvestimento com valor certo (e anunciado-que-some é sinal de corte). **Correção:** função
`announced_payments()` no provedor + bloco "Proventos anunciados" no topo da CalendarPage. Sem fonte
nova.

### 🟠 E4. Reinvestimento não é assistido `reinvestir-proventos`
O campo aporte só conhece `aporte_default` (`PlanControls.tsx:29,58`); somar os proventos do mês é
trabalho de memória do usuário. O gesto que define o método não tem botão. **Correção (após E1):**
banner na PlanPage "Você recebeu R$ X em proventos nos últimos 30 dias → [somar ao aporte]"; marcar a
parcela de reinvestimento no plano.

### 🟡 E5. Renda da reserva fora da renda total `renda-fixa-fora-da-meta`
`/income/goal` só vê RV; `/fixed-income/summary` já expõe `last_yield_annual` por conta. R$ 50k a 12%
são ~R$ 500/mês invisíveis no progresso. **Correção:** linha separada opt-in — "R$ 1.400 de dividendos
+ R$ 480 da reserva = 62% da meta".

### 🟡 E6. Nenhum alerta de preço-teto `alerta-preco-teto`
Tabela `alerts` criada na v1, zero uso; teto só aparece no plano e na AssetPage. O gatilho de compra do
método pode passar despercebido entre aportes. **Correção:** card "Abaixo do teto agora" no topo da
Watchlist/PlanPage, computado on-the-fly com `bazin_margin` que o score já expõe (coerente com app
pull-based; sem cron).

### 🟡 E7. Rentabilidade vs CDI invisível `benchmark-cdi-ibov`
`net_performance_pct` extraído por posição (`ghostfolio.py:87,128`) e nunca exibido; CDI já integrado
via SGS. "Não era melhor deixar no CDI?" é a pergunta que derruba o método nos anos ruins — o app
deveria ajudar a responder. **Correção:** coluna "Retorno" na PortfolioPage + card "CDI X% a.a. · seu
yield Y%"; fase 2: `/portfolio/performance` agregado vs CDI acumulado.

### 🟡 E8. Meta única e distante, sem marcos `marcos-de-renda`
Entre R$ 300/mês e R$ 5.000/mês há 15 anos de deserto motivacional (`GoalProgress.tsx:150-176`).
**Correção:** próximo marco (múltiplo de R$ 100/250) + capital necessário: "Próximo marco: R$ 400/mês —
faltam ~R$ 8.000 investidos"; celebrar marcos (registrados via snapshots de E2).

### ⚪ E9. Sem "e se eu aportar +R$ X" `e-se-aporte-extra`
Chips "+R$ 100/500/1.000" no simulador mostrando o delta: "meta em ~14 anos (−4 anos)". Só orquestração
no frontend, reusa `/income/projection`.

---

## Parte VIII — Pontos cegos (crítico de completude)

Seis riscos que os 50 achados não cobriram, verificados no código:

1. 🟠 **Backup automático inexistente** — tudo que você não aceita redigitar vive num único `pomar.db`;
   a única proteção é uma linha manual no README. Sem rotina de `.backup`, sem teste de restauração.
2. 🟠 **Migração de schema não-atômica** — `db.py:161-168`: `executescript` comita antes do INSERT em
   `schema_migrations`; um crash entre os dois re-executa a migração no próximo boot e os `ALTER TABLE`
   da v3 estouram "duplicate column" dentro de `ensure_ready()` — **derrubando todas as rotas** até
   intervenção manual. Nenhum teste de re-execução/interrupção.
3. 🟠 **`parseBRL("1500.00") = 150000`** — `format.ts:14` trata qualquer ponto como separador de milhar.
   Um aporte digitado "1500.00" gera plano para **R$ 150.000**. Frontend tem **zero testes** (sem runner
   no package.json) justamente na camada que recebe dinheiro digitado.
4. 🟡 **Plano fail-open com Ghostfolio fora** — `routes_plan.py:35-45` degrada para `total_value=0` e
   segue: caps calculados só sobre o aporte, posições existentes ignoradas — plano materialmente errado
   protegido por um warning textual. Decisão de compra deveria ser fail-closed (ou exigir confirmação).
5. 🟡 **Datas da renda fixa sem validação no backend** — `entry_date` é string livre; typo "2062" entra
   no SQLite e corrompe a taxa anualizada silenciosamente. Default é data UTC: lançamento após ~21h
   ganha a data de amanhã.
6. 🟡 **Carteira sem fallback stale** — Fundamentus/StatusInvest/brapi têm `get_stale`; o Ghostfolio
   (fonte de metade das telas) não tem cache nenhum: container reiniciou → Carteira, Renda, Meta e
   Calendário morrem juntos, mesmo com dados conhecidos um minuto antes.

---

## Parte IX — Plano de melhoria v4 (roadmap priorizado)

Critério de ordenação: **(1) parar de decidir com números errados, (2) proteger os dados, (3) mostrar a
bola de neve real, (4) fechar o ciclo do aporte, (5) refinar.** Nenhum item exige redigitar dados;
"schema" indica migração **aditiva** (tabela/coluna nova, dados existentes intocados).

### Fase 0 — Verdade nos números + blindagem dos dados (fazer antes de qualquer feature)
| # | Item | Achados | Schema? |
|---|---|---|---|
| 0.1 | **Backup automático do `pomar.db`** (rotina `.backup` diária no container + retenção) e **migração atômica** (INSERT em `schema_migrations` na mesma transação; teste de re-execução) | Pontos cegos 1-2 | não |
| 0.2 | **Corrigir o modelo da projeção** (yield constante, growth no patrimônio), inflação (reais de hoje), vieses menores, growth negativo, DY 0% | R1, R2, R5, R6, R7 | não |
| 0.3 | **Renda líquida em todo o planejamento** (JCP ×0,85 em renda/meta/simulador/calendário, com bruto ao lado) | R3 | não |
| 0.4 | **`parseBRL` correto + primeiro teste de frontend** (runner + casos de dinheiro/data) | Ponto cego 3 | não |
| 0.5 | **Motor:** bancos "Intermediários Financeiros" → BESST 1,0; sem herança de 100% de peso; margem Bazin por âncora; teto com anos-zero; amortização fora do DY; limiar do proxy EBIT; aviso quando estratégia zera classes | M1-M7 | não |
| 0.6 | **Plano fail-closed** quando Ghostfolio indisponível (+ cache stale da carteira) | Pontos cegos 4, 6 | não |
| 0.7 | Sinal da margem unificado + chip do teto correto nos "Outros candidatos" | U5, U7 | não |

### Fase 1 — A bola de neve real (dados que já existem, zero digitação)
| # | Item | Achados | Schema? |
|---|---|---|---|
| 1.1 | **Dividendos recebidos do Ghostfolio** → `/income/realized` + "Renda recebida" mês a mês na IncomePage (estimado vs recebido) | E1 | não |
| 1.2 | **Snapshot mensal** (patrimônio, renda, YoC) + gráfico "bola de neve real vs projetada" + evolução do YoC | E2, U3 | **aditiva** (tabela `portfolio_snapshots`) |
| 1.3 | **Proventos anunciados** no topo do Calendário (data, ticker, R$ a receber) | E3, U4 | não |
| 1.4 | **Reinvestimento assistido**: "Você recebeu R$ X → somar ao aporte" | E4 | não |
| 1.5 | Sazonalidade dividida pela janela completa | R4 | não |

### Fase 2 — Fechar o ciclo do aporte
| # | Item | Achados | Schema? |
|---|---|---|---|
| 2.1 | **Botão "Registrei a compra"** + histórico de aportes + streak de disciplina (API já pronta) | U1 | não |
| 2.2 | **Persistir planos** (`plan_history` + cache no queryClient + "último plano em <data>") | U2 | não (tabela já existe) |
| 2.3 | **Watchlist como radar**: preço, DY, CeilingBadge, ordenar por margem; card "Abaixo do teto agora" | U6, E6 | não |
| 2.4 | NextBuy respeita a estratégia salva (+ cache) | U8 | não |
| 2.5 | **Reserva com meta na própria página** + desarquivar/renomear + validação de datas no backend | F2, F3, ponto cego 5 | não |

### Fase 3 — Refinamentos
| # | Item | Achados |
|---|---|---|
| 3.1 | Renda da reserva na meta (opt-in) + goal usando o aporte pós-split | E5, R8 |
| 3.2 | Marcos de renda ("próximos R$ 100/mês") + chips "e se aportar +R$ X" | E8, E9 |
| 3.3 | Rentabilidade vs CDI (coluna Retorno + card de referência) | E7 |
| 3.4 | Dividend Growth de verdade (CAGR + penalizar cortes) e Modified Dietz na reserva | M9, F1 |
| 3.5 | Glossário sincronizado com o motor + tooltips das metas + texto da reserva | M8, U9 |
| 3.6 | Mobile/polimento: fonte 16px (iOS), tags dark mode, mensagem de erro real | U10-U12 |
| 3.7 | Manutenção: feriados B3 por algoritmo, percentil por macro-setor, testes (sazonalidade, migração, golden Fundamentus), lote real | F4, M10, pendências do placar |

---

## Apêndice A — Nota de verificação
Cada achado 🔴/🟠 recebeu **dois** verificadores adversariais independentes (lentes: correção técnica e
materialidade), 🟡 recebeu um; instrução default era refutar na dúvida. As severidades acima são as
**corrigidas** pelos verificadores — em particular, `renda-realizada` foi reportado como 🔴 e rebaixado
para 🟠 (é lacuna de feature, não erro), e vários 🟠 de UX receberam ressalvas de materialidade
(anotadas nos dados brutos). Três críticos acharam independentemente o problema do DY bruto/JCP — o
sinal mais forte da auditoria.

## Apêndice B — Achado refutado
`trailing-pd-ou-ed` ("fallback `pd or ed` anteciparia provento anunciado no DY"): a citação de código
existe, mas o verificador **testou o endpoint real do StatusInvest** (10 tickers, ~1.150 registros) e
provou que `pd` indefinido vem como a string `'-'` (truthy) — o fallback nunca dispara; o comportamento
real é o oposto (conservador). Registrado aqui como exemplo de por que verificação adversarial importa
em alegações financeiras.
