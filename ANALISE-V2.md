# 🌳 Pomar — Análise crítica e documento de input para a v2.0

> **O que é este documento.** Uma análise crítica, estética e — principalmente — de **investimentos** do
> repositório atual, pensada para ser o **input do redesenho da versão 2.0**. Foi produzida a partir de uma
> leitura integral do código (backend FastAPI + frontend React/Vite + infra Docker) e de uma auditoria
> multi‑agente por dimensão, com **verificação adversarial** das alegações factuais e financeiras. Onde a
> verificação corrigiu uma hipótese, este texto usa a **versão corrigida** — nenhuma afirmação aqui foi
> deixada na forma imprecisa original.
>
> **Como ler.** A Parte I é o veredito e a priorização. As Partes II–VII são o detalhamento por área (com
> peso para investimentos). A Parte VIII é o roadmap proposto. O **Apêndice** traz o catálogo completo dos
> 160 achados (id, severidade, categoria, status de verificação) para rastreabilidade.
>
> **Convenções.** 🔴 crítico · 🟠 alto · 🟡 médio · ⚪ baixo. Categorias: `bug`, `correção‑financeira`,
> `melhoria`, `falta‑feature`, `removível`, `design`, `segurança`.

---

## Parte I — Veredito e priorização

### 1.1 Tese geral

O Pomar acerta no **conceito** e na **postura**: um planejador de aportes na B3 que é *transparente por
construção* (todo número tem fonte e tooltip; dado faltante nunca é inventado, vira `available=False` e o peso
é redistribuído). O código é pequeno, legível e bem comentado; os modelos Pydantic materializam bem o
"contrato de transparência"; o donut interativo é um ponto alto. Como **MVP didático**, é coerente e honesto.

Mas, julgado pelo critério que ele mesmo se impõe — **recomendar aportes com qualidade e transparência** — o
Pomar v1 tem três classes de problema que a v2.0 precisa enfrentar de frente:

1. **A inteligência de investimentos é rasa e, em pontos, financeiramente incorreta.** O motor de score é
   elegante na engenharia, mas (a) **normaliza tudo por ranque/percentil**, descartando magnitude e tornando
   os números clássicos que ele invoca — teto 22,5 de Graham, teto de 6% de Bazin — **decorativos** (aparecem
   nas explicações, não entram no score); (b) **não tem nenhum eixo de risco/qualidade** (dívida, payout,
   liquidez, lucro negativo), o que o expõe a **armadilhas de valor** — justamente o ativo "barato que paga
   muito" tende a ir ao topo; (c) as estratégias "Barsi/Bazin/Graham" **só mudam pesos**, sem filtros nem
   universo próprio, então capturam o *espírito*, não o *método*; (d) a alocação tem desperdício sistemático
   de aporte e vieses estruturais; (e) **ignora renda fixa** — lacuna grave para o investidor brasileiro.

2. **O produto é uma calculadora de uso único, sem ciclo de vida.** Não há persistência, onboarding,
   acompanhamento de rentabilidade, projeção de renda passiva, calendário de proventos, histórico de aportes
   nem edição da watchlist/alvos pela UI. E — o achado de maior **valor/esforço** — o **backend já aceita**
   `targets`, `weights`, `max_assets`, `max_weight_per_asset` e `min_ticket`, mas o **frontend só envia
   `aporte` + `strategy`**: metade do motor é inacessível por desperdício de integração.

3. **A segurança é o ponto mais fraco e é um risco real.** **Não há autenticação alguma** — qualquer
   dispositivo que alcance a porta web lê todo o patrimônio e a carteira via `GET /api/portfolio`. O README
   ainda instrui a expor isso na LAN e pelo celular, com CORS `*`, sem HTTPS, com `/docs` e `/api/debug/brapi`
   abertos. Para um app que lida com dados financeiros pessoais, isso é bloqueador.

> **Resumo de uma linha:** a v2.0 precisa transformar o Pomar de *"calculadora transparente de ranking
> barato+dividendos"* em *"copiloto de aportes consciente de risco, com ciclo de vida e seguro"* — preservando
> o pilar de transparência que é o seu maior trunfo.

### 1.2 O que preservar (não jogue fora na v2.0)

- O **contrato de transparência**: `source` por métrica, glossário como fonte única, `data_completeness`,
  redistribuição de peso por dado faltante. É o diferencial do produto.
- O **motor de famílias + pesos** como *camada de ordenação fina* — é uma boa abstração; o problema é o que
  está (e o que não está) dentro dele, não a ideia.
- A **decomposição do score** na UI (ScoreBreakdown) e o tom de microcopy (jardinagem/pomar).
- O **donut interativo** e a aba "Minha carteira".
- O **multi‑provedor com fallback** (a arquitetura está certa; faltam robustez e fontes).

### 1.3 Priorização (valor × esforço)

| Prio | Tema | Por quê | Esforço |
|---|---|---|---|
| **P0** | **Autenticação + bind local + HTTPS** | Vazamento de carteira/patrimônio sem login | Médio |
| **P0** | **Expor controles avançados na UI** (`targets`/`weights`/`max_assets`/`max_weight`/`min_ticket`) | Capacidade já existe no backend; maior valor/esforço do projeto | Baixo |
| **P0** | **Eixo de risco/qualidade no score** (dívida, payout, liquidez, lucro negativo) | Evita recomendar *value traps*; correção financeira central | Médio‑alto |
| **P0** | **Renda fixa / reserva na alocação** | Asset allocation sem RF é incorreto p/ o Brasil (Selic alta) | Médio |
| **P1** | **Corrigir cálculos financeiros** (DY 12m real, média de Bazin sem zeros, P/L negativo, Graham por distância ao teto, JCP×0,85) | Distorcem ranking e recomendação | Médio |
| **P1** | **Normalização híbrida** (percentil + distância ao "justo", por setor) | Recupera magnitude e fidelidade aos métodos | Médio |
| **P1** | **Alocação v2** (rateio need‑based, redistribuição de sobra, slots por classe, lote real) | Reduz desperdício e viés | Médio |
| **P1** | **Persistência + onboarding** | Destrava quase todas as features de ciclo de vida | Médio |
| **P1** | **Robustez de dados** (logging, exceções específicas, parser resiliente, encadear fallback de proventos, liquidez) | Hoje falhas são invisíveis | Médio‑alto |
| **P2** | **Projeção de renda passiva + calendário de proventos** | Promessa "colha dividendos"; dados já coletados | Médio |
| **P2** | **Acompanhamento de rentabilidade vs CDI/IBOV** | Fecha o loop planejar→resultado | Médio |
| **P2** | **Página de detalhe do ativo + red flags** | Decisão responsável; reaproveita LPA/VPA já coletados | Médio |
| **P2** | **Estratégias com filtros de elegibilidade + novas estratégias** | Fidelidade ao método; baixo custo marginal | Médio |
| **P3** | **Sistema de design** (semântica de cor, dark mode, fonte de marca, tokens, microinterações, favicon) | Sai de "template" para "fintech" | Médio |
| **P3** | **Qualidade de engenharia** (testes de parser/rota, CI, lint/mypy, react‑query, openapi‑typescript, lockfile, não‑root) | Permite evoluir com segurança | Médio |

---

## Parte II — Investimentos: o motor de SCORE (foco principal)

### 2.1 O problema‑raiz: normalização por ranque descarta magnitude

`_percentile` (`scoring.py:127‑135`) não é percentil de magnitude — é **ranque**: conta `value <= p` (ou `>=`)
sobre os pares **incluindo o próprio ativo** e divide por `len`. Consequências:

- **Perde a informação que mais importa.** Num universo de ~12 ações por classe, cada posição vale ~0,08. Um
  P/VP 0,80 e um 1,20 (50% de diferença de "desconto") podem receber `normalized` quase igual se forem
  adjacentes no ranque; e um P/L 4,0 vs 4,1 pode ficar tão "distante" quanto 4,0 vs 40,0, porque **só a ordem
  conta**. Para valuation, isso é fatal — o score perde o "quão barato".
- **Os números clássicos viram decoração.** Graham (`P/L×P/VP ≤ 22,5`) é normalizado por percentil, então o
  teto 22,5 só aparece nas *reasons* (`scoring.py:274`), **não no score**. Num universo todo caro, a "menos
  cara" ainda recebe 1.0 (Graham a rejeitaria); num universo todo barato, a "mais cara" (mas < 22,5) é punida.
  Idem para o teto de Bazin de 6%. **O app diz Graham/Bazin mas pontua "relativo aos pares".**
- **Viés de auto‑inclusão e empates** (`percentile-self-inclusion-vies`, *confirmado*): o pior de 3 ativos
  recebe 1/3 ≈ 0,33 em vez de 0; a escala efetiva é `[1/N, 1]`, comprimida — pior em classes pequenas
  (ETF/BDR). Empates por arredondamento do Fundamentus inflam vários `1.0` no topo.

**Recomendação v2.0:** normalização **híbrida**. Para métricas com "preço justo" conhecido (Graham vs 22,5;
P/VP vs ~1; Bazin vs teto), pontuar por **distância ao justo** (ex.: `clamp((22.5 − pl·pvp)/22.5, 0, 1)`,
zerando acima do teto); combinar com percentil winsorizado para desempate. Excluir o próprio ativo do
denominador (`(rank−1)/(N−1)`) ou usar mid‑rank em empates. **Normalizar valuation por SETOR**, não só por
classe (`graham-pl-pvp-aplica-a-bancos-distorcido`, *parcial*): hoje os pares são chaveados só por
`asset_class`, então P/VP de banco é comparado a P/VP de mineradora/indústria — leituras incomparáveis (o
modelo já prevê `peer_group`; basta estendê‑lo ao setor).

### 2.2 A lacuna mais perigosa: zero eixo de risco/qualidade (`score-sem-eixo-risco-qualidade`, 🔴)

As 4 famílias são `valuation`, `dividend`, `rebalance`, `sector`. **Nenhuma** olha dívida (dív.líq/EBITDA),
**payout** (o dividendo é coberto pelo lucro?), **liquidez/volume**, ROE/margens, ou **lucro negativo**. O
score premia "barato + paga dividendo" sem checar se isso é *sustentável* ou se o preço caiu por um motivo.
Pior, o mecanismo de redistribuição de peso **agrava**: uma empresa com prejuízo tem `pl=None` e `graham=None`
→ perde justamente as métricas que a penalizariam, e o peso migra para `div_yield`/`pvp` que podem estar
"ótimos" *porque o preço está caindo* (`score-completude-infla-rank`). E o **P/L negativo não é filtrado**
(`fundamentus-num-pl-negativo-nao-tratado`, *parcial — confirmado o núcleo*): com `higher_better=False`, um
P/L de −5 recebe percentil ~1.0 (tratado como "o maior desconto"), incoerente com `_graham_value` que
corretamente exclui `pl<=0`.

**Recomendação v2.0 (P0):** introduzir um **eixo de QUALIDADE/RISCO separado** (não diluído nas 4 famílias):
dív.líq/EBITDA, payout, ROE/margem, **liquidez média diária** e flag de lucro negativo. Usá‑lo como
**filtro de elegibilidade** e/ou **multiplicador/penalidade** do score (não como mais uma média), com um
"selo de risco" transparente. Sem isso, o app recomenda *value traps* com cara de barganha.

### 2.3 Família de dividendos: vários erros financeiros concretos

Esta é a família mais problemática e a de maior peso nos presets (0,35–0,50).

- **DY mistura períodos e fica defasado** (`dy-mistura-periodos-e-defasagem`, 🟠 *confirmado*).
  `market_data.py:56‑61` calcula `dy = (proventos do último ano‑calendário FECHADO) / preço de hoje` — porque
  `_windowed` exclui o ano corrente. Em jun/2026 isso usa proventos de **2025 inteiro** (centro de massa
  ~12–18 meses no passado) sobre o preço atual. **Não é o "12 meses" que o glossário afirma**
  (`glossary.py:30`) — é um yield de ano‑calendário defasado, e a defasagem **cresce ao longo do ano**. Pior:
  esse valor **sobrescreve** o DY *trailing‑12m* do Fundamentus (troca um número melhor por um pior).
  → **v2.0:** DY trailing‑12m real (somar proventos dos últimos 365 dias a partir das **datas individuais**),
  e corrigir o glossário; cair para o DY do Fundamentus quando faltar histórico, em vez de sobrescrevê‑lo.

- **Média de Bazin deflacionada por zeros** (`bazin-media-deflacionada-por-zeros`, 🟠 *confirmado*).
  `_windowed` preenche com `0.0` anos sem pagamento dentro da janela; `_bazin_margin` filtra só `None` (não
  zero), então os zeros entram em `sum/len`, derrubando o `avg_div` e o teto (`avg/0,06`). Com 2 de 5 anos
  zerados, o teto cai ~40%, e a margem pode virar negativa para um bom pagador recente.
  **Correção importante da hipótese inicial:** isso **só** afeta **pagadores irregulares já estabelecidos** que
  *pularam um ano no meio* do histórico — **não** IPOs/novatos, porque `start = max(first, current_year−5)`
  protege anos anteriores ao primeiro pagamento. E só ocorre no caminho **StatusInvest** (o fallback brapi não
  preenche zeros).
  → **v2.0:** média de Bazin **só sobre anos com pagamento > 0** (ou mediana); manter os zeros apenas para a
  métrica de consistência. Exigir um piso de anos pagos antes de atribuir teto.

- **Fallback de Bazin é circular** (`score-bazin-fallback-circular`, 🟡 *confirmado*). Sem histórico,
  `avg_div = dy × price` ⇒ a margem colapsa para `1 − 0,06/dy` — **função pura do yield**, com o preço
  cancelando. Como `div_yield` e `bazin_ceiling` estão na **mesma família** e ambos viram percentil, o yield
  entra **duas vezes** (duplo‑peso do mesmo sinal). → **v2.0:** quando não há histórico, marcar
  `bazin_ceiling` como `available=False` (o `div_yield` já captura o sinal), em vez de derivá‑lo do yield.

- **Consistência ignora valor/crescimento e infla com histórico curto**
  (`score-consistencia-ignora-valor-e-crescimento` + `dividend-consistency-janela-curta-infla`, *confirmado*).
  `paid/len(years)` dá 1.0 tanto para quem paga R$0,01 quanto R$3,00 crescentes; e como a janela encolhe ao
  primeiro ano pago, **1–2 anos de histórico = 100%**, empatando/superando uma pagadora de 5 anos com um pulo
  (80%) — o oposto de "premiar perenidade". → **v2.0:** denominador fixo (sempre 5) ou `available=False` se
  < 3 anos; adicionar **CAGR do dividendo** (crescimento) e **penalizar cortes recentes**.

- **DY e Bazin contam parcialmente em dobro** (`dy-e-bazin-mesma-familia-double-counting`, 🟡 *parcial*):
  correlacionados mas **não idênticos** (DY usa último ano; Bazin usa média plurianual); a `dividend_consistency`
  na mesma família dilui e contrabalança. Ainda assim, vale combinar DY+Bazin num único eixo "renda/preço‑justo"
  e usar DY médio (winsorizado) para reduzir picos não recorrentes.

- **JCP × dividendo sem ajuste de IR** (`jcp-vs-dividendo-sem-ajuste-ir`, 🟠 *parcial — núcleo confirmado*).
  O StatusInvest soma `dividendos + JCP` brutos; JCP sofre 15% de IR na fonte e dividendo de ação é isento
  hoje. O yield bruto **superestima a renda líquida de pagadoras de JCP** (bancos BESST como ITUB4/BBDC4) e
  infla o teto de Bazin. → **v2.0:** capturar o tipo do provento e expor um **yield líquido** (JCP × 0,85) ao
  lado do bruto.

### 2.4 Setor BESST e número de Graham

- **BESST é um flag binário por substring** (`score-sector-besst-binario-substring` /
  `barsi-besst-binario-proxy-pobre`, *parcial*). `_besst_affinity` retorna 0/1 conforme o setor contenha uma
  keyword; `"financ"` arrasta qualquer "serviços financeiros" (corretoras, fintechs) para dentro do conceito
  que Barsi reserva a **Bancos** (`besst-keyword-financ-amplo-demais`, *confirmado*). Sem gradação, sem
  distinguir líder de laggard, sem qualidade/payout. → **v2.0:** mapa explícito setor→afinidade (0..1) com
  taxonomia curada; estender afinidade a FIIs de segmentos defensivos.

- **LPA/VPA são coletados e descartados** (`lpa-vpa-coletados-mas-descartados`, *confirmado*). O Fundamentus já
  extrai LPA e VPA, mas `market_data` não os persiste e `Fundamentals` nem tem os campos — e eles são
  exatamente os insumos do **Número de Graham clássico** `√(22,5 · LPA · VPA)`. → **v2.0:** persistir LPA/VPA e
  calcular valor intrínseco + margem de segurança real; ou parar de coletá‑los.

---

## Parte III — Investimentos: estratégias, alocação e fidelidade

### 3.1 As estratégias capturam o espírito, não o método (`estrategias-so-mudam-pesos-sem-universo-nem-filtro`, 🟠)

"Mudar de estratégia só muda pesos" é elegante e transparente — e **insuficiente**. Os métodos reais são, em
grande parte, sobre **universo** e **filtros de elegibilidade**, não pesos:

- **Barsi** restringe a líderes de setores perenes, com preço‑teto por DY‑alvo, concentração em poucas e
  horizonte de décadas. Hoje vira "dividend 0,40 + sector 0,25" sobre o mesmo universo.
- **Graham** (`graham-so-multiplo-sem-solidez`, *confirmado*) exigia 7 critérios (porte, liquidez corrente > 2,
  lucros positivos por 10 anos, dividendos por 20 anos, crescimento de LPA, P/L ≤ 15, P/L×P/VP ≤ 22,5). O app
  captura **só o último** — e ainda por percentil, não como teto. Margem de segurança em Graham é desconto
  sobre **valor intrínseco**, não múltiplo barato.
- **Bazin** usava média de 5 anos de pagadoras recorrentes **e lucrativas**, e o **DY‑alvo de 6% é constante
  hardcoded** (`bazin-teto-6pct-hardcoded-desatualizado`, *confirmado*), não parametrizável e desacoplado da
  taxa livre de risco — sob Selic alta, 6% pode sinalizar como "barata" boa parte do mercado.

→ **v2.0:** por estratégia, introduzir **filtros de elegibilidade** (ex.: Barsi → BESST + consistência ≥ 0,8 +
porte mínimo; Graham → lucro positivo + liquidez corrente > 2 + P/L×P/VP ≤ 22,5; Bazin → consistência alta +
lucro positivo) e passar a *estratégia* (não só os pesos) para `scoring`/`universe`. Tornar o **DY‑alvo de
Bazin parametrizável** e oferecer modo "atrelado à Selic" (API do BCB, série SGS). Adicionar estratégias úteis:
**Dividend Growth**, **Magic Formula** (earnings yield + ROIC), **Valor + Qualidade**.

### 3.2 Alocação default sem renda fixa (`alocacao-default-sem-renda-fixa`, 🟠)

`default_targets = {STOCK 0,50; FII 0,30; ETF 0,15; BDR 0,05}` — **100% renda variável**. Para um brasileiro
com Selic elevada, ignorar RF/reserva é uma omissão séria e enfraquece as próprias estratégias (Bazin/Graham
exigem prêmio **sobre a renda fixa**, que o app nem modela). → **v2.0:** adicionar classe `RENDA_FIXA`/`CAIXA`
aos alvos; parâmetro de **reserva‑alvo** priorizada antes da RV; usar CDI/Selic como benchmark explícito nas
margens.

### 3.3 O motor de alocação tem falhas estruturais

- **Orçamento por classe só pelo gap** (`alloc-orcamento-so-por-gap-ignora-score`, 🟠). Classes no/acima do
  alvo recebem **zero**; o **score do ativo não influencia a divisão entre classes**. Um STOCK excelente e
  barato numa carteira "cheia" de STOCK recebe R$0 enquanto um FII medíocre leva tudo. E o rebalance já é uma
  família do score — aqui é aplicado de novo como filtro binário (peso categórico duplo).
  → **v2.0:** `orçamento_classe = α·(gap normalizado) + (1−α)·(massa de score dos candidatos)`, com piso por
  classe presente.

- **Rateio sobre pesos pré‑aporte distorce com aporte grande** (`alloc-gap-usa-pesos-sem-caixa-distorce-meta`,
  🟡 *confirmado*). O gap é medido **antes** do aporte; com aporte ≈ carteira, sobre‑corrige. *Exemplo
  verificado:* carteira R$1.000 (STOCK 90%/FII 10%), aporte R$1.000, alvos 50/50 → FII recebe os R$1.000 e
  termina em **55%** (alvo 50%). → **v2.0:** trabalhar em **valores need‑based**:
  `need = max(0, alvo·(total+aporte) − valor_atual_da_classe)`; ratear para zerar os needs.

- **Contador global `chosen` enviesa para a primeira classe** (`alloc-chosen-global-vies-primeira-classe`, 🟠).
  O loop por classe ordenada por orçamento + `in_class[:max(1, max_assets−chosen)]` faz a classe de maior gap
  **consumir todos os slots**; classes seguintes ficam zeradas mesmo com orçamento positivo. O app pode
  prometer diversificar e comprar 5 ativos da mesma classe. → **v2.0:** distribuir os `max_assets` **slots por
  classe** (maior‑resto/Hamilton), ≥1 por classe com orçamento, ou seleção gulosa global por valor marginal.

- **Vazamento sistemático de aporte** (`alloc-sobra-nao-redistribuida-tres-fontes`, 🟠). Três fontes de sobra
  **não redistribuídas**: arredondamento de lote **sempre para baixo**; ativo pulado por `min_ticket`/cap; e
  orçamento de classe sub‑gasto. Em aportes pequenos (o caso de uso central!), o `unallocated` fica alto sem
  explicação. → **v2.0:** **segunda passada** (varredura gulosa) comprando +1 lote enquanto couber e o teto
  permitir; reportar a **decomposição da sobra** (lote vs ticket vs teto).

- **`lot_size` sempre 1** (`be-lot-size-sempre-1`, 🟡 *confirmado*). Ações no mercado integral negociam em lote
  de **100**; o app sugere "7 ações de BBAS3" assumindo fracionário sem dizer — planos podem ser não
  executáveis. → **v2.0:** lote real por classe (100 STOCK/BDR integral, 1 FII/ETF) e modo fracionário
  explícito.

- **Sem venda/rebalanceamento real** (`alloc-sem-rebalance-real-so-compra`, 🟡). Para carteiras muito
  desbalanceadas, só comprar não fecha o gap. → **v2.0:** ao menos exibir "tempo estimado para atingir o alvo"
  no ritmo de aporte; opcionalmente um modo "rebalancear com venda" bem sinalizado (com aviso de IR).

- **Custos/tributos ignorados** (`alloc-ignora-custos-e-tributacao`, ⚪ *confirmado*): `invested = shares ·
  price`, sem emolumentos. Aceitável hoje, mas exibir como "gasto real" sem ressalva é incoerente com a
  transparência. **Sobre ETF/BDR:** a hipótese de que os alvos de 15%/5% são "silenciosamente ignorados" foi
  **refutada** — o mecanismo de rebalance os honra (gap positivo ⇒ score > 0 ⇒ entram). O problema real é
  **qualitativo**: ETF/BDR pontuam só por `div_yield + rebalance`, sem sinal fundamentalista próprio, e há
  **mistura de moeda/tributação** (IVVB11/BDRs em BRL representam ativos em USD, com retenção de ~30% na fonte
  ignorada — `moedas-bdr-etf-internacional`, *parcial*). → **v2.0:** dados próprios para ETF/BDR (expense
  ratio, composição) **ou** tratá‑los como alocação passiva por alvo, com moeda/tributação sinalizadas.

---

## Parte IV — Fontes de dados: robustez, correção e cobertura

A camada de dados é **frágil e silenciosa** — o modo de falha mais perigoso para um app de decisão.

- **Fundamentus por regex em latin‑1 quebra mudo** (`fundamentus-regex-latin1-silencioso`, 🔴). Qualquer
  mudança de markup faz todas as regex falharem juntas → todos os campos `None` → o ativo perde valuation/setor
  sem **nenhum** alarme (o score só redistribui peso). É a fonte **principal** de P/L, P/VP, setor e cotação.
  → **v2.0:** parser HTML estruturado (lxml/selectolax) + **validação de schema** pós‑parse (se N campos vierem
  `None` para um ticker que historicamente tinha dados, marcar `parser_suspect` e **alertar**); detectar
  charset pelo header; idealmente migrar fundamentos para fonte com **contrato estável** (brapi PRO/API paga).

- **StatusInvest em endpoints internos com UA falsificado** (`statusinvest-endpoints-internos-tos`, 🟠
  *confirmado*). `mainsearchquery` e `companytickerprovents` não são APIs públicas; UA "Chrome" mascara o bot.
  É a **única** fonte de histórico de proventos (base de Bazin/consistência) e **não tem fallback encadeado**
  (`brapi-fallback-dividendos-nao-encadeado`, *confirmado* — o parser de dividendos da brapi existe mas é
  descartado). Risco de ToS/IP‑ban e quebra silenciosa. → **v2.0:** tratar proventos como dado de 1ª classe
  com fonte licenciada; **encadear** o fallback brapi.dividendsData; UA honesto/identificável; rate‑limit por
  host.

- **Extração de ano frágil** (`statusinvest-ano-ultimos-4-digitos-fragil`, *parcial*): `int(str(date)[-4:])`
  assume `dd/mm/yyyy`; ISO `yyyy-mm-dd` lança ValueError → provento **descartado silenciosamente**, zerando o
  histórico. (A "dupla contagem" foi **refutada** — o `or` é exclusivo; o defeito é o **descarte silencioso** e
  o deslocamento `pd` vs `ed` entre anos.) → **v2.0:** `strptime` multi‑formato; um único critério de
  competência (data‑com).

- **Heurística de escala do DY na brapi** (`brapi-dy-heuristica-fr...`, *parcial*): `if dy > 1.5: dy/=100`
  infere escala pela magnitude. (O exemplo "3,2% vira 320%" foi **refutado** — 3.2 > 1.5 ⇒ é dividido
  corretamente.) O furo real é estreito (yields ~1,0–1,5% em pontos percentuais ficam intactos como 120%).
  → **v2.0:** dividir de forma determinística como o Fundamentus já faz, ou não usar o DY da brapi para score.

- **Resiliência a renomeação pode atribuir o ticker errado** (`resiliencia-renomeacao-atribui-ticker-errado`,
  *parcial*): com `batch=1`, se a brapi devolve 1 resultado de símbolo diferente, o app aceita como
  "renomeado" e grava dados de **outro ativo** sob o ticker pedido, **sem aviso**. (Não é o caminho comum — só
  dispara quando o ticker some da resposta.) → **v2.0:** validar a renomeação (lista de mudanças/nome) ou
  emitir warning visível e marcar o Asset.

- **`_infer_class` da brapi contradiz o projeto** (`infer-class-brapi-11-fii-contradiz-projeto` /
  `be-infer-class-brapi-morto-e-ruim`, *confirmado*): ainda usa "termina em 11 → FII", heurística que o próprio
  `classify.py` declara abandonada. Quase morto no fluxo do plano, mas `GET /asset/{ticker}` expõe a classe
  errada. → **v2.0:** remover; fazer `/asset` passar por `classify_ticker`.

- **Cache: leak + semântica divergente** (`cache-memory-leak-sem-eviccao` / `be-cache-stale-mem-incoerente`,
  *confirmado*). Em memória, `_mem` nunca evicta e `get_stale` devolve o item expirado **para sempre** (sem
  idade); no Redis, `stale` é chave separada (~10× TTL). → **v2.0:** `cachetools.TTLCache` com idade exposta;
  recusar stale acima de um limite; padronizar memória vs Redis. **Cliente Redis síncrono bloqueia o event
  loop** (`be-cache-redis-sync-em-async`, *parcial*) — usar `redis.asyncio` ou `to_thread`.

- **`as_of` mente sobre a idade** (`ttl-coerencia-as-of-incorreto`, *parcial*): `build_assets` re‑carimba
  `as_of = now()` a cada chamada **mesmo servindo do cache de 24h**, e o **preço de decisão vem do Fundamentus
  (TTL 24h)**, não do brapi (1h). (No caminho brapi o `as_of` é fiel — o defeito é específico do `build_assets`.)
  → **v2.0:** timestamp **real de coleta por campo**; servir preço da fonte de menor TTL; expor freshness por
  campo na UI.

- **Cobertura de fontes insuficiente** (`sem-fonte-liquidez-volume` 🟠, `sem-fonte-divida-payout-crescimento`
  🟠, `sem-cotacao-historica-volatilidade` ⚪): faltam **liquidez/volume** (risco de 1ª ordem na B3),
  **dívida/payout/ROE/crescimento** (sustentabilidade do dividendo) e **série histórica** (volatilidade,
  backtest). O universo é uma **watchlist fixa hardcoded** (`universo-watchlist-fixa-hardcoded`) que envelhece
  (já há renomeações no código). → **v2.0:** derivar o universo de IBOV/IBRA/IDIV/IFIX com **filtro de
  liquidez**; manter a watchlist como "favoritos".

---

## Parte V — Lacunas de produto (visão v2.0)

O Pomar é hoje uma calculadora de uso único. As features que faltam — e que toda ferramenta brasileira séria
(StatusInvest, Investidor10, Meus Dividendos, AUVP) oferece:

| Feature | Por quê | Observação |
|---|---|---|
| 🔴 **Expor controles avançados na UI** | `targets`/`weights`/`max_assets`/`max_weight`/`min_ticket` já existem no backend, mas a UI só envia `aporte`+`strategy` | Maior valor/esforço do projeto |
| 🟠 **Persistência de preferências** | Nada é salvo (estratégia, alvos, watchlist, aporte) | Fundação que destrava o resto |
| 🟠 **Onboarding/setup** | 1ª visita sem Ghostfolio mostra erro cru ou degrada mudo; `api.health()` existe e nunca é chamado | Momento mais frágil do funil |
| 🟠 **Editar watchlist pela UI** | Hoje é editar Python + rebuild do container | Validar ticker contra provedores ao adicionar |
| 🟠 **Renda fixa/reserva** | Ver §3.2 | — |
| 🟠 **Projeção de renda passiva / bola de neve** | A promessa é "colha dividendos"; dados já coletados | "Quanto aportar para R$X/mês" |
| 🟠 **Rentabilidade vs CDI/IBOV** | Ghostfolio expõe performance; hoje só lê valor/quantidade | Fecha o loop planejar→resultado |
| 🟡 **Calendário de proventos** | `_windowed` joga fora datas/tipo individuais já baixados | Reaproveita a mesma chamada |
| 🟡 **Página de detalhe do ativo** | `GET /asset/{ticker}` existe e o front nunca chama; LPA/VPA descartados | Alto valor educativo |
| 🟡 **Red flags / "por que NÃO comprar"** | `_reasons` só tem frases positivas → viés de confirmação | Reaproveita métricas já calculadas |
| 🟡 **Tributação (IR, isenção R$20k, JCP, come‑cotas)** | Hoje zero; JCP tratado como dividendo isento | Mínimo: separar JCP×0,85 |
| 🟡 **Histórico de aportes / "já comprei"** | `/plan` é efêmero | Alimenta rentabilidade e renda |
| ⚪ **Alertas (preço‑teto/zona de compra)** | Cálculo existe; falta monitoramento contínuo | Cron diário (após persistência) |
| ⚪ **Comparação e simulação "e se"** | Decisão de aporte | Sobre detalhe + projeção |
| ⚪ **Múltiplas carteiras/cenários** | Objetivos distintos (reserva/renda/crescimento) | Modelar `cenário` já na persistência |

---

## Parte VI — UX, fluxo e estética

### 6.1 UX & fluxo

O **núcleo** (digitar aporte → estratégia → ver recomendações com decomposição) é bom: simples e transparente.
O entorno é que falta:

- **Onboarding inexistente** (`ux-sem-onboarding-setup`, 🟠): erro técnico cru ("500 em /api/portfolio") na 1ª
  visita; `api.health()` ocioso. → cartão "Conecte sua carteira em 3 passos" + "testar conexão".
- **Controles do plano só via código** (`ux-parametros-nao-expostos`, 🟠): ver Parte V. → painel "Ajustes
  avançados" recolhível.
- **Transparência incompleta na borda** (`ux-staleness-so-global`, 🟠 *confirmado*): `Provenance` é um modelo
  **órfão**; `stale`/`as_of` não chegam por ativo; o `as_of` do plano/carteira **nunca é renderizado**; a
  staleness vira um banner global desconectado do card. Contradiz o pilar do produto. → selo "⏳ cache de
  18/06" por métrica + carimbo "dados de HH:MM de DD/MM".
- **Sem persistência** (`ux-sem-persistencia`, 🟡): recomeça do zero a cada visita. → `localStorage` (última
  estratégia, aporte, aba, ajustes).
- **Falta o "por que estas compras" em linguagem simples** (`ux-falta-resumo-por-que`, 🟡): a decomposição é
  ótima para auditar, mas intimida o leigo. → parágrafo‑síntese no topo, gerado dos dados.
- **Falta a alocação RESULTANTE pós‑aporte** (`ux-alocacao-pos-aporte`, 🟡): o app mostra atual vs alvo, mas não
  "para onde este aporte leva". → 3ª barra "após este aporte" (`FIIs: 22% → 26%, alvo 30%`).
- **Falta o desfecho de execução** (`ux-sem-checklist-export-jacomprei`, 🟡): sem copiar/exportar ordens nem
  "já comprei". → botão "Copiar ordens" + checkboxes persistidos.
- **Estado vazio do ranking ausente** (`ux-estado-vazio-ranking`, 🟡): se a brapi falha, tela em branco com
  banner técnico. → empty‑state com causa provável e ação.
- **Tooltip com fricções no mobile** (`ux-tooltip-mobile-friccoes`, 🟡): `left:0` estoura à direita; clique
  colide com o expandir do card. → posicionar conforme a borda; bottom‑sheet no mobile; alvo de toque ≥ 44px.
- **Input de aporte frágil** (`ux-input-aporte-fragil`, ⚪ *confirmado*): submit silencioso para inválido;
  `"1.000,50"` vira `1` (replace só troca a 1ª vírgula). → validação + máscara pt‑BR.

### 6.2 Estética & design

A UI é limpa e honesta, mas está no patamar de **"template competente"**, não de fintech moderna:

- **Cor não comunica qualidade** (`score-badge-sempre-verde`, 🟠): o badge de score e as barras de métrica são
  **sempre verdes** — nota 28 e 92 têm o mesmo verde. → escala semântica vermelho→âmbar→verde mapeada à
  nota/distância‑da‑meta; reservar o verde de marca para header/CTA.
- **Quase zero microinterações** (`microinteracoes-ausentes`, 🟠): **1 único `:hover`** no CSS inteiro, **nenhum
  `:focus-visible`** (falha de acessibilidade — o tooltip‑anchor é focável mas invisível). → camada de
  transição 120–160ms + `:focus-visible` consistente + `prefers-reduced-motion`.
- **Sem dark mode** (`sem-dark-mode`, 🟡) e **tokens incompletos** (`tokens-espacamento-magicos`, 🟡): cores
  literais espalhadas; só cor/raio são tokens; espaçamento/tipografia são magic‑numbers. → tokenizar tudo
  (espaço 4/8, raio sm/md/lg/pill, elevação 1/2/3) + tema escuro via `prefers-color-scheme`.
- **Tipografia 100% system‑ui** (`tipografia-system-only`, 🟡): sem fonte de marca; valores em R$ sem
  `tabular-nums`. → fonte de marca para títulos/números + escala em tokens.
- **Sem favicon/logotipo** (`sem-favicon-identidade`, 🟡): identidade resume‑se ao emoji 🌳 (renderiza diferente
  por SO). → logotipo SVG + favicon multi‑tamanho + PWA manifest.
- **Donut**: paleta com verdes adjacentes pouco distintos e não color‑blind‑safe; só ~12 das 16 cores são
  usadas (4 são código morto); `<svg>` sem `aria-label` (`donut-paleta-contraste-a11y`, *parcial* — a legenda
  textual mitiga). → paleta categórica perceptual (Okabe‑Ito/Tableau) + rótulo acessível.
- **Emoji como vocabulário visual** e **header gradiente genérico** (⚪): trocar por ícones SVG do design
  system; header com mais intenção.

---

## Parte VII — Arquitetura, qualidade e segurança

### 7.1 Backend

- **Zero logging** (`be-sem-logging`, 🟠) + **15 `except Exception` amplos** (`be-except-amplo-engole`, 🟠):
  falhas de rede/parsing — e **bugs de programação** (`KeyError`/`TypeError`) — viram "dado faltante" sem
  rastro. → logging estruturado; capturar exceções **específicas** (`httpx.TimeoutException`,
  `HTTPStatusError`, `(ValueError, KeyError)`); deixar bugs propagarem; exceções de domínio
  (`ProviderUnavailable`, `ProviderParseError`).
- **DI por `lru_cache` (singletons mutáveis)** (`be-deps-lru-cache-singleton`, 🟠): difícil mockar (sem
  `dependency_overrides`); estado mutável compartilhado (`_working_params`, `_jwt`); race em `_resolve_params`
  (`be-resolve-params-race`, *parcial* — limitada a 3 pelo semáforo, mas existe). → migrar para `Depends`
  reais; resolver capacidade do plano por **config explícita** (env), eliminando a sondagem.
- **`AsyncClient` por chamada** (`be-asyncclient-por-request`, 🟡): sem pool/keep‑alive; refaz TLS a cada
  request. → client único por provedor no lifespan; retry/backoff uniforme (tenacity).
- **Config não validada** (`be-config-nao-validada`, 🟡): `targets`/`weights` podem não somar 1.0 → score fora
  de `[0,1]` silenciosamente. → validadores Pydantic + Enum de classes/famílias; falhar com 422.
- **Cobertura de testes mínima** (`be-cobertura-testes-insuficiente`, 🟠): só `scoring`/`allocation`, com uma
  **asserção tautológica** em `test_allocation` (`alloc-testes-fracos`); nenhum teste de parser/rota/cache/
  classify/bordas. → golden files de HTML/JSON para Fundamentus/StatusInvest (uma mudança de markup **falha o
  teste** em vez de degradar mudo); testes de `_windowed`, `_dig`, cache e rotas com `dependency_overrides`.
- **Sem CI/lint/mypy** (`be-sem-ci-lint-typecheck`, 🟡): há `# noqa: BLE001` mas sem config de ruff. → `[tool.ruff]`/
  `[tool.mypy]` + GitHub Actions (lint + mypy + pytest).
- **Cleanups**: warmup fire‑and‑forget sem observabilidade; `get_settings()` em tempo de import; dupla consulta
  ao StatusInvest por ativo; Dockerfile duplica deps do pyproject; `_dig` busca em `summaryDetail` que nunca é
  pedido (código morto parcial).

### 7.2 Frontend

- **Data‑fetching manual em `useEffect`** (`fe-no-query-lib`, 🟠): sem cache/dedupe/cancelamento/retry; sob
  StrictMode dispara fetch duplo. → `@tanstack/react-query` (ou SWR) + `AbortController`.
- **Motor inacessível** (`fe-backend-params-not-exposed`, 🟠 *confirmado*): ver Parte V (P0).
- **Duas fontes de verdade**: `FALLBACK_PRESETS` duplica `config.py` (`fe-duplicated-presets`, 🟠) e `types.ts`
  espelha os modelos Pydantic à mão, **já divergindo** (`targets`/`weights` ausentes — `fe-manual-types`, 🟠
  *confirmado*). → eliminar o fallback hardcoded; gerar tipos com **openapi‑typescript** do `/openapi.json`.
- **Sem ErrorBoundary** (`fe-no-error-boundary`, 🟡); **navegação por `useState`** sem rota/deep‑link
  (`fe-tabs-no-router`, 🟡); **a11y do Tooltip e do PieChart** (sem teclado/`aria-expanded`/`aria-label` —
  `fe-tooltip-a11y`/`fe-piechart-a11y`, 🟡); **zero testes e lint** (`fe-no-tests-no-lint`, 🟡).
- **Inconsistências de dados/UX**: rodapé credita só "brapi.dev" quando as fontes primárias são
  Fundamentus+StatusInvest (`fe-footer-stale-sources`, *confirmado*); `%` da legenda usa base diferente do
  donut e diverge quando há holding com `value ≤ 0` (`fe-pct-base-mismatch`, *confirmado*); `brl` duplicado em
  3 arquivos e moeda hardcoded ignorando o campo `currency` da API.

### 7.3 Segurança & operação — **o ponto mais fraco**

- 🔴 **API sem autenticação** (`no-auth-portfolio-exposure`): `GET /api/portfolio` devolve patrimônio e
  carteira completos **sem login**, a qualquer dispositivo na rede. O README instrui expor na LAN e pelo
  celular. → **bloqueador da v2.0:** middleware exigindo senha/token (`secrets.compare_digest`) em todas as
  rotas `/api` exceto `/health`; idealmente sessão com cookie HttpOnly+Secure+SameSite; **bind 127.0.0.1** por
  padrão + reverse proxy autenticado para exposição.
- 🟠 **CORS `*`** com métodos/headers `*` (`cors-wildcard-default`) e 🟠 **sem HTTPS** (`no-https-plaintext-lan`):
  tráfego financeiro em texto claro; qualquer senha futura trafegaria interceptável. → origens explícitas; TLS
  num reverse proxy (Caddy/Traefik), redirect 80→443.
- 🟡 **`/api/debug/brapi`** sem auth (`debug-brapi-no-auth`) e 🟡 **`/docs`/`/openapi.json`** abertos
  (`docs-openapi-exposed`): entregam o mapa da API. → atrás de flag `DEBUG`/auth; 404 em produção.
  *(Acerto:* o `diagnose` **não** vaza o token, só o comprimento.)
- 🟡 **Containers como root** (`containers-run-as-root`), **sem lockfile Python** (`no-python-lockfile` — o
  frontend tem `package-lock`, mas usa `npm install` em vez de `npm ci` e nem copia o lock), **bind 0.0.0.0**
  (`backend-binds-all-interfaces`), **sem rate limit** + `proxy_read_timeout 120s` que mascara lentidão e
  amplia DoS (`no-rate-limit-timeout-mask`), **sem healthcheck/limites no compose** (`no-healthcheck-no-limits`),
  **Redis sem senha** e **sem `.dockerignore`**. *(Acerto:* segredos **não** versionados — `.gitignore` cobre
  `.env`, só `.env.example` é trackeado.)

---

## Parte VIII — Roadmap proposto para a v2.0

Sequência por dependência e valor (cada fase entrega valor por si):

**Fase 0 — Fundações de segurança e integração (P0, rápido)**
1. Autenticação (senha/token), bind local, CORS explícito, `/docs` e `/debug` atrás de flag, HTTPS via proxy.
2. Expor os controles avançados que já existem no backend (painel "Ajustes avançados").
3. Persistência (`localStorage` + camada `/api/preferences`) e onboarding com `api.health()`.

**Fase 1 — Corrigir e aprofundar o motor de investimentos (P0/P1)**
4. **Eixo de risco/qualidade** (dívida, payout, liquidez, lucro negativo) como filtro/penalidade + selo.
5. **Renda fixa/reserva** na alocação; CDI/Selic como benchmark.
6. **Correções financeiras**: DY trailing‑12m real; média de Bazin sem zeros; P/L≤0 inelegível; Graham por
   distância ao teto (+ Número de Graham com LPA/VPA); JCP líquido; consistência com piso e CAGR.
7. **Normalização híbrida** (distância‑ao‑justo + percentil, por setor).
8. **Alocação v2**: rateio need‑based, slots por classe, segunda passada de redistribuição, lote real,
   decomposição da sobra.
9. **Robustez de dados**: logging + exceções específicas; parser resiliente com validação de schema; encadear
   fallback de proventos; fonte de liquidez/dívida/payout; universo por índice + filtro de liquidez.

**Fase 2 — Ciclo de vida do investidor (P1/P2)**
10. Projeção de renda passiva / bola de neve + calendário de proventos.
11. Rentabilidade vs CDI/IBOV (ler performance do Ghostfolio).
12. Página de detalhe do ativo + red flags + alocação resultante pós‑aporte + checklist/exportar ordens.
13. Estratégias com filtros de elegibilidade + novas estratégias (Dividend Growth, Magic Formula, Valor+Qualidade).

**Fase 3 — Acabamento (P3)**
14. Sistema de design (semântica de cor, dark mode, fonte de marca, tokens, microinterações, favicon/logo).
15. Qualidade de engenharia (react‑query, openapi‑typescript, testes de parser/rota, CI, lint/mypy, lockfile,
    containers não‑root, healthchecks, rate limit).

### Princípios de design da v2.0 (do que aprendemos)
- **Transparência até o fim:** todo número mostra fonte **e idade**; mostre o "porquê não" tanto quanto o
  "porquê"; quando truncar/aproximar (sobra, fallback, stale), **diga**.
- **Risco em primeiro plano:** nenhuma recomendação sem checagem de sustentabilidade e liquidez.
- **Fidelidade ao método, não só à vibe:** estratégia = universo + filtros + pesos.
- **Falhe alto, não baixo:** erro de fonte/parser deve **alertar**, nunca virar "dado faltante" mudo.
- **Configurável e com memória:** as alavancas do motor são do usuário, e ele não deve reconfigurar tudo a cada
  visita.

---

## Apêndice A — Notas de verificação (o que foi corrigido/refutado)

A auditoria verificou adversarialmente 56 achados; 26 foram **corrigidos ou parcialmente refutados**. Os ajustes
mais relevantes para não propagar imprecisões na v2.0:

- **Bazin/zeros:** afeta só **pagadores irregulares estabelecidos** (pulo no meio do histórico), **não** IPOs
  novos (clamp `max(first, …)`), e só no caminho **StatusInvest**.
- **DY:** é "último ano‑calendário **fechado** ÷ preço atual", **não** trailing‑12m; o glossário ("12 meses")
  está incorreto.
- **ETF/BDR:** os alvos 15%/5% **são** honrados pelo rebalance (a hipótese de "ignorar 20% da meta" foi
  **refutada**); o problema é ranking interno pobre + moeda/tributação.
- **`rebalance_gap`:** há **acoplamento** (ordenação do score + split de orçamento), mas **não** dupla contagem
  do dinheiro (o valor por classe vem só de `_class_budget`).
- **`last_diagnostic`:** é estado **morto** (escrito, nunca lido) — `diagnose()` retorna um diag local; **não**
  vaza entre usuários.
- **brapi serial:** o **plano** usa `build_assets` concorrente; só `/asset` (1 ticker) usa o `get_assets`
  serial — a alegação de que `/universe` o usa direto foi **refutada**.
- **DY ÷100 da brapi:** o exemplo "3,2%→320%" estava **errado** (3.2 é dividido corretamente); o furo real é
  estreito (1,0–1,5% em pontos percentuais).
- **`_num` do Fundamentus:** parseia negativos corretamente; a causa‑raiz do P/L negativo é a **falta de guard
  no scoring**, não o parser.
- **Cache multi‑worker:** o deploy real roda **1 worker** e usa Redis; a fragmentação por `>1 worker` é
  hipotética.

> O catálogo completo (Apêndice B) marca cada achado verificado com seu veredito (`confirmed` /
> `partially-correct`). Em qualquer divergência, vale a **versão corrigida** descrita nas Partes II–VII.

---

## Apêndice B — Catálogo completo dos achados

**160 achados** em 11 dimensões. Severidade: 🔴 4 · 🟠 42 · 🟡 64 · ⚪ 50. Verificados adversarialmente: 56 (✔ 30 confirmados · ≈ 26 parciais · ✖ 0 refutados · ? 0 incertos).

Categorias: `design` 34 · `missing-feature` 33 · `improvement` 32 · `financial-correctness` 26 · `bug` 22 · `security` 9 · `removable` 4.

> Legenda de verificação: ✔ confirmado · ≈ parcialmente correto/refinado · (em branco) = não submetido a verificação (juízo de design/UX subjetivo). Em divergência, vale a versão corrigida das Partes II–VII.


### Metodologia de SCORE (foco em investimentos)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🔴 | `missing-feature` | `score-sem-eixo-risco-qualidade` | Ausência total de eixo de risco/qualidade: score vulnerável a value trap |  |
| 🟠 | `design` | `score-completude-infla-rank` | Redistribuição de peso pode inflar o score de ativos com poucos dados |  |
| 🟠 | `financial-correctness` | `score-percentil-descarta-magnitude` | Normalização por percentil descarta magnitude e vira ranque puro num universo pequeno |  |
| 🟠 | `financial-correctness` | `score-graham-nao-usa-teto-22` | Graham normalizado por percentil ignora completamente o teto absoluto 22,5 |  |
| 🟠 | `financial-correctness` | `score-bazin-media-deflacionada-por-zeros` | Média de Bazin é deflacionada por anos-zero preenchidos artificialmente | ≈ parcial |
| 🟠 | `missing-feature` | `score-fii-sem-metricas-proprias` | FIIs avaliados com métricas de ação; faltam P/VP-FII contextual, vacância, cap rate, segmento |  |
| 🟡 | `bug` | `score-div-yield-ano-calendario-nao-12m` | Dividend yield usa último ano-calendário completo, mas é rotulado como 'últimos 12 meses' | ≈ parcial |
| 🟡 | `financial-correctness` | `score-bazin-fallback-circular` | Fallback de Bazin via yield×preço é matematicamente circular | ✔ confirmado |
| 🟡 | `financial-correctness` | `score-consistencia-ignora-valor-e-crescimento` | Consistência de dividendos ignora valor, crescimento e tendência |  |
| 🟡 | `financial-correctness` | `score-sector-besst-binario-substring` | sector_besst é binário 0/1 por substring frágil, sem granularidade de qualidade |  |
| 🟡 | `improvement` | `score-sem-penalizacao-stale` | Score não penaliza dados defasados (stale) nem carimbo de data | ✔ confirmado |
| ⚪ | `design` | `score-rebalance-gap-mistura-por-classe` | rebalance_gap é por CLASSE, idêntico para todo ativo da classe — não discrimina dentro dela | ≈ parcial |
| ⚪ | `design` | `score-bdr-etf-quase-sem-sinal` | ETF/BDR pontuam quase só por div_yield e rebalance — ranking pobre e enviesado | ≈ parcial |
| ⚪ | `improvement` | `score-percentil-empates-1.0` | Empates no percentil inflam a normalização (vários ativos recebem 1.0) |  |
| ⚪ | `removable` | `score-brapi-dividends-codigo-orfao` | Código de dividendos da brapi (_dividends_by_year) está órfão e glossário aponta fonte errada | ≈ parcial |

### Motor de ALOCAÇÃO do aporte (allocation.py + routes_plan.py + test_allocation.py)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `bug` | `alloc-chosen-global-vies-primeira-classe` | Contador global `chosen` + slice por classe ordenada por orçamento faz a primeira classe consumir quase todos os slots; classes seguintes ficam sub-alocadas |  |
| 🟠 | `design` | `alloc-orcamento-so-por-gap-ignora-score` | Orçamento por classe é proporcional só ao gap de rebalanceamento; classes no/acima do alvo recebem ZERO e o score do ativo não influencia a divisão entre classes |  |
| 🟠 | `financial-correctness` | `alloc-sobra-nao-redistribuida-tres-fontes` | Aporte vaza para `unallocated` por três fontes não redistribuídas (arredondamento para baixo, orçamento de classe sub-gasto, ativo pulado por min_ticket/cap) |  |
| 🟡 | `bug` | `alloc-cap-concentracao-sobre-total-after-fixo` | Teto de concentração usa total_after = total_value + aporte fixo e desconta `held`, mas não acumula compras do mesmo run nem soma corretamente compras de outros ativos | ≈ parcial |
| 🟡 | `financial-correctness` | `alloc-total-leq-zero-divide-por-alvos-nao-residual` | Quando todas as classes estão no/acima do alvo, divide proporcional aos ALVOS (não ao residual de gap negativo), o que pode reforçar o desbalanceamento | ✔ confirmado |
| 🟡 | `financial-correctness` | `alloc-gap-usa-pesos-sem-caixa-distorce-meta` | O gap de classe é calculado sobre pesos que somam 1.0 entre holdings (sem caixa); aporte grande relativo à carteira distorce o cálculo de gap | ✔ confirmado |
| 🟡 | `improvement` | `alloc-testes-fracos` | Testes de alocação são fracos: asserção tautológica e cobertura ausente dos casos críticos (multi-classe com max_assets, redistribuição, total<=0) |  |
| 🟡 | `missing-feature` | `alloc-sem-tratamento-aporte-menor-que-um-lote` | Sem tratamento explícito para aporte menor que o preço de 1 lote do candidato mais barato; resultado é unallocated = aporte inteiro sem orientação |  |
| 🟡 | `missing-feature` | `alloc-sem-rebalance-real-so-compra` | Não sugere vendas nem rebalanceamento real; só compra com dinheiro novo — insuficiente para carteiras muito desbalanceadas |  |
| ⚪ | `bug` | `alloc-budget-positivo-mas-classe-presente-sem-investivel` | classes_present pode conter classe com orçamento>0 mas cujos candidatos têm score 0 ou sem preço, gerando sobra silenciosa |  |
| ⚪ | `improvement` | `alloc-ignora-custos-e-tributacao` | Alocação ignora custos de transação e tributação por completo; aceitável hoje, mas não modelado nem sinalizado | ✔ confirmado |
| ⚪ | `improvement` | `alloc-docstring-desatualizada-score-proporcional` | Docstring afirma distribuição 'proporcional ao score' dentro da classe, mas o teto e o slice distorcem isso sem mencionar |  |

### Correção financeira e lógica (bugs em cálculos de investimento)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `financial-correctness` | `dy-mistura-periodos-e-defasagem` | DY 'real' mistura proventos de até 2 anos atrás com preço de hoje e fica defasado fora do 1º trimestre | ✔ confirmado |
| 🟠 | `financial-correctness` | `bazin-media-deflacionada-por-zeros-e-janela-variavel` | Média de Bazin deflacionada por anos-zero e por janela de tamanho variável (preço-teto subestimado) | ✔ confirmado |
| 🟠 | `financial-correctness` | `jcp-vs-dividendo-sem-ajuste-ir` | JCP, dividendos e rendimentos de FII somados sem ajuste de IR — yield bruto engana a comparação entre classes | ≈ parcial |
| 🟡 | `bug` | `brapi-dy-heuristica-fr...` | Heurística DY da brapi (÷100 se >1,5) corrompe yields legítimos altos e não corrige todos os casos | ≈ parcial |
| 🟡 | `bug` | `resiliencia-renomeacao-atribui-ticker-errado` | Resiliência a renomeação pode atribuir dados do ativo errado quando o cache mistura símbolos | ≈ parcial |
| 🟡 | `bug` | `statusinvest-ano-ultimos-4-digitos-fragil` | Extração de ano por 'últimos 4 dígitos da data' é frágil e o fallback pd→ed mistura datas-com e datas de pagamento | ≈ parcial |
| 🟡 | `bug` | `alloc-budget-nao-redistribui-sobra-classe` | Orçamento de classe não é redistribuído quando um ativo é barrado por teto/ticket, gerando sobra evitável |  |
| 🟡 | `bug` | `alloc-max-assets-corte-prematuro-por-classe` | max_assets é consumido classe a classe na ordem do orçamento, podendo bloquear melhores ativos de classes posteriores |  |
| 🟡 | `financial-correctness` | `moedas-bdr-etf-internacional` | BDRs e ETFs internacionais (IVVB11) misturam moeda e fundamentos incomparáveis no mesmo ranking | ≈ parcial |
| 🟡 | `financial-correctness` | `bazin-fallback-yield-circular` | Fallback de Bazin sem histórico usa yield×preço, tornando a margem de Bazin matematicamente trivial | ≈ parcial |
| ⚪ | `bug` | `infer-class-brapi-11-fii-contradiz-projeto` | _infer_class da brapi ainda usa 'termina em 11 → FII', heurística que o projeto declara abandonada |  |
| ⚪ | `bug` | `fundamentus-num-pl-negativo-nao-tratado` | Parser numérico do Fundamentus não distingue sinais/valores ausentes e P/L negativo passa para o score | ≈ parcial |
| ⚪ | `bug` | `class-budget-divisao-por-alvos-quando-no-alvo` | Quando a carteira já está no alvo, orçamento é dividido por alvos de classe podendo destinar dinheiro a classe sem candidato investível |  |
| ⚪ | `design` | `graham-margem-invertida-confusa` | Métrica 'graham' usa P/L×P/VP cru no percentil sem ancorar no teto 22,5 — label 'Margem Graham' é enganoso |  |
| ⚪ | `financial-correctness` | `percentile-self-inclusion-vies` | Percentil inclui o próprio ativo na contagem, inflando scores em classes com poucos pares | ✔ confirmado |
| ⚪ | `financial-correctness` | `dividend-consistency-janela-curta-infla` | Consistência de dividendos com janela curta (start=first) dá 100% trivial a empresas recém-listadas | ✔ confirmado |

### Qualidade e Robustez das Fontes de Dados (foco em investimentos)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🔴 | `bug` | `fundamentus-regex-latin1-silencioso` | Fundamentus: scraping por regex em latin-1 quebra silenciosamente para None |  |
| 🟠 | `design` | `statusinvest-endpoints-internos-tos` | StatusInvest: uso de endpoints JSON internos não-documentados com User-Agent falsificado | ✔ confirmado |
| 🟠 | `design` | `resiliencia-falha-silenciosa-engole-erro` | try/except amplos engolem falhas: degradação silenciosa sem distinguir erro de ausência |  |
| 🟠 | `improvement` | `brapi-batch1-sequencial-latencia` | brapi tier grátis (batch=1): requests sequenciais por ticker tornam o plano lento e sujeito a timeout | ≈ parcial |
| 🟠 | `missing-feature` | `sem-fonte-liquidez-volume` | Nenhuma fonte de liquidez/volume: recomenda ativos sem filtrar negociabilidade |  |
| 🟠 | `missing-feature` | `sem-fonte-divida-payout-crescimento` | Faltam dívida (dív/EBITDA), payout e crescimento de lucro/dividendo — sinais centrais de qualidade |  |
| 🟡 | `bug` | `brapi-resolve-params-probe-storm` | brapi _resolve_params faz até 5 sondagens sequenciais no cold start; diagnose() reseta e força re-probe (estado compartilhado) | ≈ parcial |
| 🟡 | `bug` | `cache-memory-leak-sem-eviccao` | Cache em memória nunca evicta: dict cresce indefinidamente e get_stale retorna item expirado para sempre |  |
| 🟡 | `bug` | `ttl-coerencia-as-of-incorreto` | as_of carimba o instante da consulta, não a idade real do dado; TTLs coerentes mas freshness mal exposta | ≈ parcial |
| 🟡 | `design` | `universo-watchlist-fixa-hardcoded` | Universo é uma watchlist fixa hardcoded (~45 tickers); não varre nem filtra a B3 |  |
| 🟡 | `improvement` | `brapi-fallback-dividendos-nao-encadeado` | Fallback de dividendos da brapi nunca é usado: market_data só chama brapi para preço/setor | ✔ confirmado |
| 🟡 | `improvement` | `sem-testes-camada-dados` | Zero testes na camada de provedores/clientes/cache |  |
| ⚪ | `missing-feature` | `sem-cotacao-historica-volatilidade` | Sem fonte de cotação histórica: impossível medir risco/volatilidade ou drawdown |  |

### Fidelidade das estratégias e filosofia de investimento

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `design` | `estrategias-so-mudam-pesos-sem-universo-nem-filtro` | Estratégias diferem apenas em pesos; não há diferenciação de universo nem filtros qualitativos |  |
| 🟠 | `financial-correctness` | `bazin-media-deflacionada-por-zeros` | Média de proventos do Bazin é deflacionada por anos zerados na janela de 5 anos | ✔ confirmado |
| 🟠 | `financial-correctness` | `bazin-teto-6pct-hardcoded-desatualizado` | DY-alvo de 6% do Bazin é constante hardcoded, não-parametrizável e desatualizado frente à Selic | ✔ confirmado |
| 🟠 | `financial-correctness` | `graham-so-multiplo-sem-solidez` | Estratégia Graham captura só o múltiplo 22,5 e ignora todos os critérios de solidez do método | ✔ confirmado |
| 🟠 | `missing-feature` | `alocacao-default-sem-renda-fixa` | Alocação default ignora renda fixa — lacuna grave de asset allocation para o investidor brasileiro |  |
| 🟡 | `financial-correctness` | `barsi-besst-binario-proxy-pobre` | BESST de Barsi reduzido a um flag binário por substring de setor — proxy muito pobre do método | ≈ parcial |
| 🟡 | `financial-correctness` | `dy-e-bazin-mesma-familia-double-counting` | Dividend yield e margem de Bazin pesam na mesma família, dobrando o efeito do mesmo provento | ≈ parcial |
| 🟡 | `missing-feature` | `faltam-estrategias-uteis` | Faltam estratégias relevantes: dividend growth, Magic Formula, small caps de valor, paridade de risco |  |
| ⚪ | `design` | `max-weight-20pct-vs-barsi-concentracao` | Teto de concentração default (20%) e max_assets (5) destoam da filosofia de concentração do Barsi |  |
| ⚪ | `financial-correctness` | `graham-pl-pvp-aplica-a-bancos-distorcido` | P/VP e número de Graham aplicados indiscriminadamente a bancos/financeiras distorcem o valuation | ≈ parcial |
| ⚪ | `improvement` | `besst-keyword-financ-amplo-demais` | Keyword 'financ' no BESST arrasta setores financeiros não-bancários para dentro do conceito de Barsi | ✔ confirmado |
| ⚪ | `removable` | `lpa-vpa-coletados-mas-descartados` | LPA e VPA são extraídos do Fundamentus mas descartados — bloqueiam o Graham correto | ✔ confirmado |

### Lacunas de Produto (visão v2.0)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🔴 | `missing-feature` | `expor-controles-avancados-api` | Frontend não expõe targets/weights/max_assets/max_weight/min_ticket que a API JÁ aceita |  |
| 🟠 | `missing-feature` | `editar-watchlist-ui` | Watchlist/universo é hardcoded em Python, sem edição pela UI |  |
| 🟠 | `missing-feature` | `persistencia-preferencias` | Nada do usuário é persistido — sem memória entre sessões |  |
| 🟠 | `missing-feature` | `renda-fixa-reserva` | Não há renda fixa / Tesouro Direto / reserva de emergência na alocação |  |
| 🟠 | `missing-feature` | `projecao-renda-passiva-snowball` | Sem projeção de renda passiva futura / bola de neve de dividendos |  |
| 🟠 | `missing-feature` | `acompanhamento-rentabilidade-benchmark` | Sem acompanhamento de rentabilidade da carteira nem comparação vs CDI/IBOV | ✔ confirmado |
| 🟡 | `missing-feature` | `calendario-proventos` | Sem calendário de proventos (datas-com, pagamentos previstos) | ✔ confirmado |
| 🟡 | `missing-feature` | `historico-aportes` | Sem histórico de aportes/planos gerados |  |
| 🟡 | `missing-feature` | `pagina-detalhe-ativo` | Sem página de detalhe do ativo (histórico, gráficos, fundamentos completos) |  |
| 🟡 | `missing-feature` | `red-flags-por-que-nao-comprar` | Só explica por que comprar; não há red flags / por que NÃO comprar |  |
| 🟡 | `missing-feature` | `tributacao-ir-jcp` | Sem nenhum tratamento de tributação (IR, isenção R$20k, come-cotas, JCP) | ✔ confirmado |
| ⚪ | `missing-feature` | `alertas-preco-teto-zona-compra` | Sem alertas (preço-teto atingido, ativo entrou na zona de compra) |  |
| ⚪ | `missing-feature` | `comparacao-e-simulacao-e-se` | Sem comparação entre ativos e simulação 'e se' |  |
| ⚪ | `missing-feature` | `multiplas-carteiras-cenarios` | Sem suporte a múltiplas carteiras/cenários | ✔ confirmado |

### Qualidade de Código e Arquitetura do Backend

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `design` | `be-except-amplo-engole` | 15 blocos `except Exception`/`except:` amplos mascaram erros distintos |  |
| 🟠 | `design` | `be-deps-lru-cache-singleton` | Injeção de dependência via lru_cache (singletons globais) em vez de FastAPI Depends |  |
| 🟠 | `financial-correctness` | `be-bazin-media-deflacionada-por-zeros` | Média de Bazin é deflacionada por anos com 0 inseridos pela janela | ≈ parcial |
| 🟠 | `improvement` | `be-sem-logging` | Zero logging estruturado em todo o backend; falhas são invisíveis |  |
| 🟠 | `missing-feature` | `be-cobertura-testes-insuficiente` | Cobertura de teste mínima: só scoring e allocation; sem providers, rotas, cache, classify, bordas |  |
| 🟡 | `bug` | `be-resolve-params-race` | Corrida em _resolve_params do brapi sob concorrência | ≈ parcial |
| 🟡 | `bug` | `be-cache-stale-mem-incoerente` | get_stale em modo memória retorna o próprio valor expirado; sem cópia stale de longa duração como no Redis | ≈ parcial |
| 🟡 | `financial-correctness` | `be-lot-size-sempre-1` | lot_size sempre 1 — lotes reais da B3 ignorados | ✔ confirmado |
| 🟡 | `financial-correctness` | `be-dy-mistura-periodos` | Dividend yield usa último ano completo isolado, mas Bazin usa média — semânticas misturadas e DY pode não ser 12m | ✔ confirmado |
| 🟡 | `improvement` | `be-asyncclient-por-request` | AsyncClient criado por chamada — sem pool/reuso de conexão |  |
| 🟡 | `improvement` | `be-config-nao-validada` | default_targets e default_weights não são validados (soma 1.0, chaves) |  |
| 🟡 | `improvement` | `be-cache-redis-sync-em-async` | Cliente Redis síncrono usado em handlers async (bloqueia o event loop) | ≈ parcial |
| 🟡 | `missing-feature` | `be-sem-ci-lint-typecheck` | Sem CI, sem ruff/black/mypy configurados no pyproject (só caches no .gitignore) |  |
| 🟡 | `security` | `be-debug-brapi-sem-auth` | /api/debug/brapi exposto sem autenticação |  |
| ⚪ | `bug` | `be-dig-camada-summarydetail-incoerente` | _dig do brapi procura em summaryDetail mas _MODULES não pede esse módulo; e mistura priceEarnings/trailingPE | ≈ parcial |
| ⚪ | `design` | `be-semaforos-magicos` | Semáforos com números mágicos (6 e 3) e sem coordenação entre eles |  |
| ⚪ | `design` | `be-settings-import-time` | get_settings() chamado em tempo de import no main.py (acopla import a env) |  |
| ⚪ | `financial-correctness` | `be-percentile-inclui-proprio` | Percentil inclui o próprio valor e nunca atinge 0 — comprime a base do ranking | ✔ confirmado |
| ⚪ | `improvement` | `be-warmup-fire-and-forget` | Warmup no lifespan dispara task sem await nem observabilidade |  |
| ⚪ | `improvement` | `be-dockerfile-deps-duplicadas` | Dockerfile duplica a lista de dependências em vez de instalar do pyproject |  |
| ⚪ | `improvement` | `be-classify-duas-chamadas-statusinvest` | classify_ticker e statusinvest.fetch consultam o StatusInvest duas vezes; classificação redundante no pipeline |  |
| ⚪ | `removable` | `be-infer-class-brapi-morto-e-ruim` | _infer_class do brapi é heurística ruim e praticamente código morto |  |

### Qualidade de Código e Arquitetura do Frontend

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `design` | `fe-no-query-lib` | Data-fetching manual em useEffect sem cache, dedupe, cancelamento ou retry |  |
| 🟠 | `design` | `fe-duplicated-presets` | FALLBACK_PRESETS duplica os presets do backend — fonte dupla de verdade |  |
| 🟠 | `design` | `fe-manual-types` | types.ts espelha os modelos pydantic à mão — sem geração automática | ✔ confirmado |
| 🟠 | `missing-feature` | `fe-backend-params-not-exposed` | UI expõe só aporte+estratégia; backend aceita targets, weights, max_assets, max_weight_per_asset e min_ticket — motor inacessível | ✔ confirmado |
| 🟡 | `design` | `fe-tabs-no-router` | Abas com useState em vez de rota: sem deep-link, sem histórico, F5 reseta |  |
| 🟡 | `design` | `fe-tooltip-a11y` | Tooltip não é acessível: sem teclado, sem aria-expanded, e hover quebra no mobile |  |
| 🟡 | `design` | `fe-piechart-a11y` | PieChart sem rótulo acessível, sem legenda associada por aria e sem tabela alternativa |  |
| 🟡 | `improvement` | `fe-no-error-boundary` | Sem ErrorBoundary; erro de render derruba a árvore inteira sem feedback |  |
| 🟡 | `improvement` | `fe-no-tests-no-lint` | Zero testes e nenhuma config de lint/format |  |
| ⚪ | `bug` | `fe-footer-stale-sources` | Rodapé credita só 'brapi.dev', mas as fontes principais agora são Fundamentus + StatusInvest | ✔ confirmado |
| ⚪ | `bug` | `fe-pct-base-mismatch` | Percentuais da legenda usam total da carteira como base, podendo não fechar 100% nas visões 'tag'/'Outros' | ✔ confirmado |
| ⚪ | `bug` | `fe-piechart-active-bounds` | Estado 'active' por índice pode ficar fora de sincronia ao trocar de agrupamento |  |
| ⚪ | `improvement` | `fe-loading-no-skeleton` | Estados de carregamento pobres: só 'Carregando…' e ausência de skeletons |  |
| ⚪ | `improvement` | `fe-glossary-error-swallowed` | Erros de glossário e de estratégias são engolidos silenciosamente |  |
| ⚪ | `improvement` | `fe-no-currency-from-api` | Moeda hardcoded 'BRL' ignora o campo currency retornado pela API |  |
| ⚪ | `removable` | `fe-brl-duplicated` | Formatação de moeda (brl) copiada em 3 arquivos |  |

### UX, Fluxo e Produto (experiência do usuário)

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `design` | `ux-staleness-so-global` | Staleness e as_of dos dados existem no backend mas não chegam à UI por ativo; campo as_of nunca é renderizado | ✔ confirmado |
| 🟠 | `missing-feature` | `ux-sem-onboarding-setup` | Primeira visita sem Ghostfolio: erro cru no Portfolio e degradação silenciosa no Plano, sem nenhuma tela de setup/ajuda |  |
| 🟠 | `missing-feature` | `ux-parametros-nao-expostos` | Parâmetros do plano (nº de ativos, teto por ativo, ticket mínimo, alvos por classe) só são ajustáveis editando código, embora o backend já os aceite |  |
| 🟡 | `design` | `ux-tooltip-mobile-friccoes` | Tooltip por toque tem fricções no mobile: fecha ao tocar fora, posicionamento left:0 estoura à direita, e o clique colide com o expandir do card |  |
| 🟡 | `improvement` | `ux-alocacao-pos-aporte` | AllocationSummary mostra atual vs alvo, mas não mostra a alocação RESULTANTE depois de executar as compras sugeridas |  |
| 🟡 | `improvement` | `ux-estado-vazio-ranking` | Sem estado vazio amigável quando o plano não gera compras nem candidatos (apenas warnings soltos) |  |
| 🟡 | `missing-feature` | `ux-sem-persistencia` | Zero persistência: estratégia, aporte e plano somem a cada recarga; nenhuma memória entre visitas |  |
| 🟡 | `missing-feature` | `ux-falta-resumo-por-que` | Falta um resumo em linguagem simples de 'por que essas compras' no topo do resultado |  |
| 🟡 | `missing-feature` | `ux-sem-checklist-export-jacomprei` | Falta o desfecho de execução: nenhum checklist de ordens, exportar/copiar plano, ou marcar 'já comprei' |  |
| ⚪ | `improvement` | `ux-disclaimer-redundante-posicao` | Disclaimer aparece só no rodapé do resultado e duplica o footer global; risco regulatório/UX de ser ignorado |  |
| ⚪ | `improvement` | `ux-input-aporte-fragil` | Campo de aporte sem validação/feedback: aceita texto, submit silencioso quando <=0, sem máscara de moeda | ✔ confirmado |
| ⚪ | `improvement` | `ux-footer-fonte-desatualizada` | Microcopy do rodapé credita só a brapi como fonte de mercado, mas o app agora usa Fundamentus + StatusInvest (brapi virou fallback) | ✔ confirmado |
| ⚪ | `improvement` | `ux-sem-loading-skeleton-portfolio` | Estados de carregamento pobres: 'Carregando carteira…' simples e botão que só muda o rótulo, sem skeleton/progresso no plano que pode demorar |  |

### Design Visual e Estética

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🟠 | `design` | `score-badge-sempre-verde` | Badge de score é sempre verde, mesmo para notas ruins — cor não comunica qualidade |  |
| 🟠 | `design` | `microinteracoes-ausentes` | Quase zero microinterações: 1 único :hover e nenhum :focus-visible no CSS inteiro |  |
| 🟡 | `design` | `tipografia-system-only` | Tipografia 100% system-ui — sem fonte de marca, hierarquia plana por tamanho |  |
| 🟡 | `design` | `estados-loading-empty-pobres` | Estados de loading e vazio rasos: sem skeleton e sem empty-state do ranking |  |
| 🟡 | `design` | `donut-paleta-contraste-a11y` | Paleta do donut de 16 cores: fatias adjacentes com baixa distinção e sem reforço não-cromático | ≈ parcial |
| 🟡 | `improvement` | `tokens-espacamento-magicos` | Tokenização incompleta: cores e raio único viram token, mas espaçamento e tipografia são magic-numbers |  |
| 🟡 | `missing-feature` | `sem-dark-mode` | Dark mode inexistente e nenhuma estrutura para suportá-lo |  |
| 🟡 | `missing-feature` | `sem-favicon-identidade` | Sem favicon, sem logotipo — identidade resume-se ao emoji 🌳 |  |
| ⚪ | `design` | `donut-svg-nao-fluido` | Donut com largura fixa em px, não fluido — sobra/falta espaço e risco de overflow |  |
| ⚪ | `design` | `header-gradiente-generico` | Header gradiente verde + identidade visual genérica (vibe template Bootstrap) |  |
| ⚪ | `design` | `emoji-na-ui-densa` | Uso de emoji como vocabulário visual (🌱, 🌳, ⚠️) reduz percepção de produto sério |  |
| ⚪ | `design` | `barra-meta-alocacao-fraca` | Marcador de meta na barra de alocação é pouco legível e pode ultrapassar a trilha |  |

### Segurança, Privacidade e Operação/Deploy

| | Cat | ID | Título | Verif. |
|---|---|---|---|---|
| 🔴 | `security` | `no-auth-portfolio-exposure` | API totalmente sem autenticação expõe carteira e patrimônio a qualquer um na rede |  |
| 🟠 | `security` | `cors-wildcard-default` | CORS default '*' com allow_methods e allow_headers '*' |  |
| 🟠 | `security` | `no-https-plaintext-lan` | Sem HTTPS — tráfego financeiro em texto plano (nginx só :80) |  |
| 🟡 | `design` | `scraping-spoofed-ua-tos` | Scraping de Fundamentus e StatusInvest com User-Agent falsificado | ≈ parcial |
| 🟡 | `improvement` | `no-python-lockfile` | Dependências Python sem lockfile — versões soltas '>=' no Dockerfile e pyproject |  |
| 🟡 | `security` | `debug-brapi-no-auth` | Endpoint /api/debug/brapi exposto sem autenticação |  |
| 🟡 | `security` | `containers-run-as-root` | Containers rodam como root, sem usuário não-privilegiado |  |
| 🟡 | `security` | `backend-binds-all-interfaces` | Frontend publica porta em todas as interfaces (0.0.0.0) por padrão |  |
| 🟡 | `security` | `ghostfolio-token-protected-portfolio-not` | Segredos versionados corretamente, mas o token Ghostfolio 'protege' a fonte enquanto a carteira fica exposta pela API sem auth |  |
| ⚪ | `design` | `no-rate-limit-timeout-mask` | Sem rate limiting; proxy_read_timeout 120s mascara lentidão e amplia DoS |  |
| ⚪ | `design` | `redis-no-auth-no-backup` | Redis sem senha e sem backup (aceitável em rede interna, mas frágil) |  |
| ⚪ | `improvement` | `no-dockerignore-frontend` | Sem .dockerignore — build context pode incluir node_modules e arquivos locais |  |
| ⚪ | `improvement` | `npm-install-not-ci` | Frontend usa 'npm install' em vez de 'npm ci' e nem copia o lockfile antes |  |
| ⚪ | `improvement` | `no-healthcheck-no-limits` | Compose sem healthcheck, sem limites de recursos e sem dependência por saúde |  |
| ⚪ | `security` | `docs-openapi-exposed` | /docs, /redoc e /openapi.json expostos por padrão sem auth |  |
