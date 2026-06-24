# 🌳 Pomar — Análise crítica v3 (estado pós‑v2) e roadmap para "viver de dividendos"

> **O que é este documento.** Uma análise crítica do Pomar **como ele está hoje** (depois da reforma v2),
> sob a ótica de um investidor que segue **Barsi/Bazin** (dividendos perenes, BESST, preço‑teto, bola de
> neve). Foi produzido a partir de **leitura integral do código atual** (não do diagnóstico antigo) por uma
> auditoria multi‑agente (11 subsistemas, 79 achados) **com verificação adversarial** das alegações
> financeiras e de segurança, mais **pesquisa da plataforma AGF** (Ações Garantem o Futuro, casa da Louise
> Barsi) e da **metodologia Barsi/Bazin** com fontes.
>
> **Como ler.** A Parte I é o veredito. A Parte II é o **placar do que foi prometido na v2 vs entregue**. As
> Partes III–IX detalham por área (com peso para investimentos). A Parte X é o **roadmap v3 priorizado**. O
> Apêndice traz notas de verificação, achados completos e fontes.
>
> **Honestidade sobre severidade.** A verificação adversarial **rebaixou** a maioria das acusações
> financeiras de "alto" para "médio" (são imprecisões de calibração, não bugs) e uma de segurança para
> "baixo". Este texto usa a **severidade verificada**, não a alegação original. 🔴 crítico · 🟠 alto ·
> 🟡 médio · ⚪ baixo.

---

## Parte I — Veredito

**A v2 foi um salto real e fiel ao método.** O Pomar deixou de ser uma "calculadora de ranking
barato+paga‑muito" e virou um **copiloto de aportes consciente de risco, com ciclo de vida e autenticado**.
Três conquistas decisivas, todas confirmadas no código atual:

1. **Eixo de risco/qualidade anti *value‑trap*** — `_quality_assessment` (`scoring.py:211‑248`) é um
   **multiplicador** separado das 4 famílias (`final_score = composite * q`, `scoring.py:349`), não mais uma
   média diluível. Penaliza prejuízo (×0,5), dív.líq/EBITDA>3, payout>100% e baixa liquidez, com selo
   🟢/🟡/🔴 e *red flags*. Dado ausente é **neutro** (distingue "fonte falhou" de "fundamento ruim"). Isso é
   exatamente o que protege uma carteira perene do "barato que paga muito porque está afundando".
2. **Os números clássicos saíram do decorativo** — Graham agora **ancora no teto 22,5** por distância
   (`_graham_anchor`, `scoring.py:48‑54`); o **Número de Graham** clássico `√(22,5·LPA·VPA)` foi implementado
   com LPA/VPA que antes eram coletados e jogados fora (`scoring.py:126‑138`); Bazin **não deflaciona mais**
   por anos‑zero e exige piso de anos pagos (`scoring.py:105‑123`); P/L≤0 vira inelegível; o percentil
   corrige o viés de auto‑inclusão e empates (`scoring.py:177‑199`).
3. **Estratégia virou método, não só peso** — cada estratégia tem **filtro de elegibilidade de universo**
   (`strategies.py`): Barsi = BESST + consistência ≥ 0,8; Graham = lucro positivo + P/L×P/VP ≤ 22,5 +
   liquidez corrente; Bazin = consistência alta + abaixo do teto. Inelegível recebe score 0 **com motivo**.

Some‑se a isso a fundação de produto destravada: **autenticação** por senha (mata o vazamento de carteira que
era o 🔴 da v1), **CORS/docs restritos**, **controles avançados expostos na UI**, **persistência SQLite**,
**alocador need‑based** com slots por classe e segunda passada, **página de detalhe do ativo**, e a
**projeção de renda passiva / bola de neve** — que é, literalmente, a tese "colha dividendos".

**O que ainda separa o Pomar de uma ferramenta Barsi de primeira linha** (ordem de gravidade para *você*):

- 🔴 **Um bug operacional crítico**: o **SQLite não tem volume no Docker** — toda preferência e watchlist se
  perde a cada `docker compose up --build` (que o próprio README manda rodar). Você pode já ter perdido
  ajustes sem perceber.
- 🟠 **A renda fixa / reserva não existe** — único P0 do roadmap v2 **não entregue**; os campos
  `reserve_target` e `bazin_target_mode` são gravados no banco mas **ninguém os lê** (stubs mortos). Para o
  brasileiro sob Selic alta e para a disciplina Barsi ("reserva antes de tudo, prêmio sobre o CDI"), é a
  maior lacuna conceitual.
- 🟡 **O preço‑teto — coração do método — só existe no backend**: não aparece em nenhuma tela. O usuário não
  vê "este ativo está abaixo do teto de Bazin".
- 🟡 **Refinamentos de fidelidade**: DY ainda é "último ano‑calendário ÷ preço de hoje" (defasado, não
  trailing‑365d); JCP entra **bruto** (sem ×0,85), inflando o yield dos bancos BESST; Bazin a **6% fixo**;
  BESST ainda **binário por substring** ("financ" arrasta corretora/fintech); valuation normalizado por
  **classe, não por setor** (banco comparado a mineradora).
- 🟡 **Ciclo de vida pela metade**: faltam *yield on cost*, calendário de proventos, "próximo melhor aporte",
  rentabilidade vs CDI/IBOV, e a UI de watchlist/ranking (a API já existe).

> **Resumo de uma linha:** a v2 acertou o **motor de investimentos** e a **segurança básica**; a v3 deve
> tapar o **buraco da renda fixa**, **trazer o preço‑teto e o ciclo de vida para a tela**, e **calibrar os
> detalhes do método** — inspirando‑se no que o AGF faz bem.

---

## Parte II — Placar: prometido na v2 × entregue

| Item planejado (v2) | Prio | Status | Evidência |
|---|---|---|---|
| Expor controles avançados na UI | P0 | ✅ **Feito** | `PlanControls.tsx:152‑225` (painel "Ajustes avançados") + `routes_plan.py` consome |
| Eixo de risco/qualidade no score | P0 | ✅ **Feito** | `scoring.py:211‑248`, `:349` (multiplicador + selo + red flags) |
| Autenticação + bind local + HTTPS | P0 | 🟡 **Parcial** | Auth HMAC ✅ (`security.py`); bind 127.0.0.1 e TLS no repo ❌ |
| Correções financeiras (Bazin, Graham, P/L≤0, consistência) | P1 | 🟡 **Parcial** | Quase tudo ✅ (`scoring.py`); **DY trailing‑12m e JCP×0,85 ❌** |
| Normalização híbrida **por setor** | P1 | 🟡 **Parcial** | Híbrida + sem auto‑inclusão ✅; **por setor ❌** (`peer_group=cls`, `scoring.py:341`) |
| Alocação v2 (need‑based, slots, 2ª passada, **lote real**) | P1 | 🟡 **Parcial** | Núcleo ✅; **lote real ❌** (`market_data.py:98` hardcoda `lot_size=1`) |
| Persistência + onboarding | P1 | 🟡 **Parcial** | Persistência ✅; onboarding guiado ❌ (só `HealthBanner` reativo) |
| Robustez de dados (logging, parser resiliente, golden tests) | P1 | 🟡 **Parcial** | Fontes de risco add ✅; **parser regex frágil + except amplo, sem golden test ❌** |
| Projeção de renda passiva / bola de neve **+ calendário** | P2 | 🟡 **Parcial** | Bola de neve ✅; **calendário de proventos ❌** |
| Página de ativo + red flags **+ pós‑aporte + checklist** | P2 | 🟡 **Parcial** | Página + red flags ✅; **alocação pós‑aporte / exportar ordens ❌** |
| Estratégias com filtros + novas + **Bazin parametrizável** | P2 | 🟡 **Parcial** | Filtros + 2 presets novos ✅; **Bazin 6% fixo, BESST binário, Magic Formula ❌** |
| Sistema de design (cor, dark mode, microinterações, favicon) | P3 | 🟡 **Parcial** | Só a **cor semântica do badge** ✅; dark mode/focus/microinterações ❌ |
| Qualidade de engenharia (react‑query, tipos gerados, CI, lint) | P3 | 🟡 **Parcial** | react‑query, router, tipos OpenAPI, testes (2→7) ✅; **CI/ruff/mypy/lockfile/não‑root ❌** |
| **Renda fixa / reserva; CDI/Selic como benchmark** | **P0** | ❌ **Não feito** | `config.py:65` 100% RV; `reserve_target`/`bazin_target_mode` **persistidos mas mortos** |
| Rentabilidade vs CDI/IBOV (ler performance do Ghostfolio) | P2 | ❌ **Não feito** | sem `netPerformancePercent`/benchmark em nenhuma camada |

**Leitura:** a v2 cumpriu as Fases 0 e 1 no que toca **investimentos e segurança**; ficou devendo a
**renda fixa (P0)**, a **robustez do parser (🔴 silencioso)** e **metade da Fase 2/3**.

---

## Parte III — O motor de score hoje (o que ainda pode melhorar)

O motor está **financeiramente correto** no essencial. Os pontos abaixo são **calibração e fidelidade**, não
defeitos — todos verificados adversarialmente e rebaixados para 🟡/⚪.

### 3.1 🟡 DY e Margem Bazin pesam quase em dobro; a consistência fica diluída
DY e Bazin moram na mesma família `dividend` e o peso é dividido igualmente entre as métricas disponíveis
(`scoring.py:324`). Como a Margem Bazin é uma transformação monotônica do yield (`margin = 1 − 0,06/(avg_div/price)`,
`scoring.py:122`), **~2/3 do peso da família vão para variações do yield** e só ~1/3 para a *consistência* —
que é o pilar da perenidade. Pior na estratégia Bazin, onde `dividend = 0,50` (`config.py:123`).
*Mitigante (por isso 🟡, não 🟠):* os numeradores diferem (DY = último ano; Bazin = média de anos pagos) e os
*value traps* são atacados no eixo de qualidade.
→ **Colapsar DY+Bazin numa única dimensão "renda/preço‑justo"** e dar **peso real à consistência** (e a um
CAGR de proventos — ver 3.5).

### 3.2 🟡 O "combo Graham" domina valuation 3:1 sobre o P/VP — ruim para bancos
`pvp`, `pl`, `graham` (P/L×P/VP) e `graham_intrinsic` (√(22,5·LPA·VPA)) são **todas** da família `valuation`
(`scoring.py:60‑67`). Três das quatro são variações do **mesmo critério Graham**, então o P/VP isolado pesa só
1/4. Para **bancos** (núcleo BESST), P/L×P/VP de Graham é notoriamente inadequado e o P/VP é o múltiplo mais
informativo.
→ Manter **Margem de Graham OU Número de Graham** (não os dois com peso igual) ou agrupá‑los num subbloco; dar
peso comparável ao P/VP; **desligar o combo Graham para bancos/financeiro**.

### 3.3 🟡 Valuation é normalizado por classe, não por setor
Os pares do percentil são chaveados por `asset_class` (`peers[(key, asset_class)]`, `scoring.py:285`;
`peer_group=cls`, `:341`). Logo o P/VP de um **banco** é comparado ao de uma **mineradora** dentro de `STOCK` —
leituras incomparáveis. O modelo já prevê `peer_group`; basta estendê‑lo ao setor.
→ **Normalizar P/VP e P/L por setor**, não por classe.

### 3.4 🟡 Liquidez baixa só corta 30% e nunca filtra
`avg_daily_liquidity < piso ⇒ q *= 0,7` fixo (`scoring.py:232‑234`), independentemente de quão ilíquido. E o
piso de ações é **R$1 mi** (`LIQUIDITY_MIN`, `scoring.py:39`), enquanto **Barsi exige ~R$5 mi/dia**. Para quem
monta posição por décadas, iliquidez é risco estrutural de entrada/saída.
→ Subir o piso de ações para ~R$5 mi (ao menos na estratégia Barsi) e tornar liquidez muito abaixo do piso um
**filtro real** (score 0) ou penalidade progressiva.

### 3.5 🟡 Consistência não penaliza cortes nem mede crescimento
`_dividend_consistency` é só `anos_pagos / anos_analisados` (`scoring.py:141‑146`): dá 100% tanto para quem
paga R$0,01 quanto R$3,00 crescentes, e não detecta **cortes**.
→ Complementar com **CAGR dos proventos** (crescimento, sinal positivo) e **penalização de cortes** (ano em que
o provento caiu vs anterior). Isso é o que diferencia "Dividend Growth" de "paga todo ano".

### 3.6 🟡 Payout usa só o último ano e dispara tarde (>100%)
`_payout_ratio` usa `dividends_by_year[último]` ÷ LPA (`scoring.py:202‑208`) e a flag só acende acima de 100%.
Bazin valoriza payout **sustentável (~40–80%)**.
→ Payout **médio de N anos**, penalizar progressivamente acima de ~0,8, e **isentar FIIs** (que distribuem
~100% por lei) desse corte.

### 3.7 ⚪ ROE não é pontuado
Barsi e a leitura quantitativa de Bazin valorizam **ROE alto e consistente (>15%)**. O Fundamentus já fornece
ROE (`fundamentus.py:63`) e o campo existe no modelo, mas **não entra** em `_METRIC_SPECS` nem no eixo de
qualidade.
→ Adicionar ROE como sinal **positivo** de qualidade (hoje o fator `q` só penaliza, nunca premia).

---

## Parte IV — Dados de dividendos e robustez

### 4.1 🟡 DY não é trailing‑12m real — é o último ano‑calendário, defasado
`statusinvest.py:43` (`for y in range(start, current_year)`) **exclui o ano corrente**, e `market_data.py:60‑63`
faz `dy = proventos_de_2025 / preço_de_hoje`. Em jun/2026, ignora todo provento de 2026 e a defasagem **cresce
ao longo do ano**. O glossário foi corrigido honestamente para refletir isso — mas continua subestimando quem
**cresce** o provento e superestimando quem **cortou**.
→ Somar proventos com **data nos últimos 365 dias** (o StatusInvest já traz `pd`/`ed` — hoje só os 4 últimos
dígitos do ano são lidos, `statusinvest.py:34`). Isso **destrava de uma vez** o DY correto, o **calendário de
proventos** e o *yield on cost*.

### 4.2 🟡 JCP entra bruto (sem ×0,85) — infla o yield dos bancos BESST
`statusinvest.py:31‑35` soma `dividendos + JCP` sem ler o tipo. O JCP sofre 15% de IR na fonte; dividendo de
ação é isento. Isso infla o DY e o **preço‑teto de Bazin** justamente de **ITUB4/BBDC4/BBAS3** (JCP‑pesados),
distorcendo o ranking a favor deles. Efeito líquido ~5–12% do yield (por isso 🟡, não 🟠).
→ Ler o tipo do provento e expor **yield líquido** (`dividendo + 0,85·JCP`) ao lado do bruto.

### 4.3 🟡 Parser do Fundamentus é frágil e falha em silêncio — o eixo de risco pode estar cego
`_grab` (`fundamentus.py:34‑41`) é um regex acoplado ao HTML exato; qualquer mudança de marcação faz **todos os
campos virarem `None`** sem alarme, e o `except Exception` (`:83`) devolve cache stale silenciosamente. O label
de dívida `"Dív Líq/EBIT"` (`:65`) é **suspeito** — se não casar, a penalização de endividamento **nunca
dispara** e você nem fica sabendo. Sem golden test, é o ponto mais perigoso da engenharia de dados.
→ **Golden file** de um ticker conhecido (ex.: TAEE11) que **falha o teste** quando N campos vêm `None` apesar
de HTTP 200; logar "parser_suspect"; capturar exceções específicas em vez do `except` amplo.

### 4.4 ⚪ Fallback de proventos não encadeado; brapi agrega bruto
Os dividendos vêm só do StatusInvest; o fallback da brapi (`brapi.py:54‑68`) existe mas não é encadeado, e
também soma bruto por `paymentDate`.
→ Encadear o fallback e unificar a premissa fiscal num único ponto.

---

## Parte V — Alocação e o buraco da renda fixa

O alocador v2 está **bem construído**: need‑based sobre a carteira resultante (`allocation.py:81‑92`), slots por
classe via maior‑resto/Hamilton (`:21‑50`), segunda passada gulosa que reaproveita a sobra (`:142‑165`). As
arestas:

- 🟠 **Renda fixa / caixa / reserva não existe.** `default_targets` é 100% RV (`config.py:65`); `FIXED_INCOME` só
  existe no set de validação; e `reserve_target`/`bazin_target_mode` são **gravados no SQLite e nunca lidos**
  (`preferences_repo.py:26`) — stubs mortos. Não há benchmark CDI/Selic. Bazin e Graham exigem **prêmio sobre a
  renda fixa**, que o app não modela. → Modelar um **sleeve CAIXA/RENDA_FIXA**: o aporte prioriza a reserva‑alvo
  antes da RV; quando nenhum ativo está abaixo do preço‑teto, o *need* da reserva absorve o aporte (vira "guardar
  no CDI" em vez de comprar caro). Usar **Selic/CDI** como referência explícita (API SGS do BCB).
- 🟡 **Lote real ainda é sempre 1.** `market_data.py:98` hardcoda `lot_size=1` apesar de o alocador aceitar
  `lot_sizes`. Ações no **mercado integral (lote 100)** são sugeridas como fracionárias sem aviso. → Trazer o
  lote real ou, no mínimo, **rotular** "compra via mercado fracionário".
- 🟡 **Teto de concentração por classe nunca é acionado.** `max_weight_per_class` existe e é checado, mas
  `routes_plan.py` não o envia (fica `None`). → Expor na UI com default (ex.: 0,60).
- 🟡 **`min_ticket` pode zerar uma classe inteira sem fallback** (`allocation.py:127`). → Se todas as fatias da
  classe ficam abaixo do ticket, concentrar no melhor ativo dela antes de desistir.
- ⚪ **Classe‑alvo sem candidato investível some do rateio silenciosamente** (`allocation.py:77‑83`). → Emitir
  *warning* ("BDR sem candidato — fatia vira caixa").

---

## Parte VI — Fidelidade Barsi/Bazin (o que o método realmente exige)

A pesquisa (fontes no Apêndice) confirma os critérios reais. O Pomar acerta o espírito; faltam calibrações:

| Critério real do método | Como está no Pomar | Ação |
|---|---|---|
| **Preço‑teto = média 5 anos ÷ 6%** | Usa **todos** os anos pagos, não a janela de 5 (`scoring.py:118`) | Fixar janela de 5 anos (AGF usa 6); manter piso de 3 anos pagos |
| **DY‑alvo de 6% ancorado na renda fixa** | **Hardcoded** `0.06` (`scoring.py:33`); `bazin_target_mode` morto | Tornar configurável; modo "dinâmico" = k × CDI (Bazin usava ~2×) |
| **BESST = só os 5 setores essenciais** | Binário por substring; **"financ" arrasta** corretora/fintech (`config.py:147`) | Mapa **setor→afinidade [0,1]** curado (bancos 1.0, "financial services" 0.3…) |
| **Líder/quase‑monopólio + DY médio>6% em 5–10 anos** | Filtro Barsi só checa BESST + consistência ≥ 0,8 (`strategies.py:26‑33`) | Adicionar critério de DY médio histórico e porte/liderança |
| **Liquidez ≥ ~R$5 mi/dia** | Piso R$1 mi (`scoring.py:39`) | Subir para R$5 mi na estratégia Barsi |
| **ROE consistente >15%, payout 40–80%** | ROE não pontuado; payout só >100% | Adicionar ROE; payout médio com corte em ~0,8 |
| **Só empresa lucrativa e pagadora recorrente** | ✅ P/L≤0 inelegível; consistência ≥ 0,8 | Manter |

**FIIs e BESST** (🟡): FIIs recebem setor genérico "Imobiliário" e **nunca** pontuam BESST (`classify.py:22`),
embora sejam veículo central de renda. → Dar **crédito parcial de perenidade** a FIIs defensivos (logística,
renda urbana, papel high‑grade) e **subsetorizar** os 10 FIIs da watchlist (hoje colapsados numa fatia só).

---

## Parte VII — Ciclo de vida e features inspiradas no AGF

O AGF (plataforma da Louise Barsi) é **prescritivo** — diz *o quê* e *quando* comprar. É aí que o Pomar pode
crescer. Mapeamento das features do AGF para oportunidades concretas (todas com dados que o Pomar **já coleta**):

| Feature AGF | O que faz | Oportunidade no Pomar | Esforço |
|---|---|---|---|
| **Preço‑Teto** (3 variantes) | Preço máximo p/ render 6% pela média de 6 anos | Já calculado no backend — **só falta mostrar**: selo "abaixo/acima do teto" no card, na carteira e na watchlist | Médio |
| **Aportador** | Sugere a melhor ação para o próximo aporte | O alocador já faz isso; **persistir objetivo de renda** e fechar o loop "compre X agora" | Médio |
| **Objetivo de Renda** | Define renda‑alvo e prazo, monitora | `required_monthly_contribution` **já resolve o aporte**; falta **persistir a meta** e mostrar "% atingido / quanto falta" | Médio |
| **Mapa do Dividendo Inteligente** | Mês a mês de quando cada empresa paga | Preservar a **data** do provento (hoje descartada) → **calendário + renda mês a mês** | Médio |
| **Yield on Cost** | Renda sobre o **preço pago** | Capturar `investment`/preço médio do Ghostfolio (hoje descartado) → **YoC por ativo e carteira** | Baixo |
| **Perfil BESST da carteira** | % em setores defensivos | Pomar já classifica setor → **visão "perenidade"** (essencial vs cíclico) | Baixo |
| **Ranking com filtros** | Ordena pagadoras por DY/setor/anos | API de watchlist já existe → **tela de descoberta** ordenável, marcando "abaixo do teto" | Médio |

**Outras lacunas de ciclo de vida** (não‑AGF, mas esperadas):
- 🟠 **Preço médio descartado** (`ghostfolio.py:71‑82`): sem ele não há YoC nem "preço pago vs preço‑teto".
  Capturar `investment` destrava ambos **sem nenhuma escrita** no Ghostfolio.
- 🟡 **Sem rentabilidade vs CDI/IBOV**: o Ghostfolio entrega `netPerformancePercent` de graça; ler isso já fecha
  o loop planejar→resultado.
- 🟡 **Histórico de aportes**: as tabelas `plan_history`/`executed_orders` **existem no schema mas estão mortas**
  (`db.py:59‑89`, nenhum INSERT). Gravar "já comprei" alimenta YoC, renda real e a bola de neve "para trás".
- 🟡 **Watchlist e onboarding ausentes na UI**: a API completa de watchlist existe (`client.ts:92‑96`), mas não
  há tela; e o primeiro acesso só tem o `HealthBanner` reativo, sem "conecte sua carteira em 3 passos".

---

## Parte VIII — Segurança e operação (você expõe via DuckDNS)

A auth v2 é **sólida para single‑user**: cookie HMAC HttpOnly + SameSite=strict, `compare_digest`, 503 sem
senha, docs gated por DEBUG, e o **backend não é publicado** (só o nginx). Para **exposição pública**, porém:

- 🔴 **SQLite sem volume no compose** *(engenharia, mas é o achado de maior impacto real)*: `DB_PATH=data/pomar.db`
  resolve para `/app/data/pomar.db` **dentro do container**, e o único volume do `docker-compose.yml` é do
  **redis**. Todo `docker compose up --build` **apaga preferências e watchlist**. → Adicionar
  `volumes: [pomar-data:/app/data]` ao serviço backend e declarar o volume. **Faça isto primeiro.**
- 🟡 **Login sem rate‑limit nem lockout** (`security.py:85‑91`): a senha única é o **único portão**, e o
  `/api/login` aceita tentativas ilimitadas. Verificado como 🟡 (impacto = leitura de dados, e brute‑force
  depende da entropia da senha). → Rate‑limit por IP (slowapi/Redis) + backoff, **senha forte** validada no
  boot. **Melhor ainda: não exponha à internet** — sirva por **Tailscale/WireGuard** e o problema some.
- 🟡 **Sem headers de segurança** (HSTS, X‑Content‑Type‑Options, X‑Frame‑Options/CSP, Referrer‑Policy) no nginx.
  → Adicionar no `nginx.conf` (camada de borda).
- 🟡 **HTTPS fora do repo + `COOKIE_SECURE=false` por padrão**: sob DuckDNS você **precisa** de `COOKIE_SECURE=true`.
  → Derivar `Secure` de `X‑Forwarded‑Proto` e incluir um `Caddyfile`/perfil compose de exemplo com TLS.
- 🟡 **Logout não revoga sessão** (TTL padrão **30 dias**, `config.py:55`): o token vale até expirar. → Reduzir
  o TTL e/ou `jti` + denylist em Redis. Hoje o único "kill switch" é trocar a `APP_PASSWORD`.
- ⚪ **Chave HMAC = a própria senha** (`security.py:93`); **Redis sem senha** (verificado 🟡→**⚪**: não é
  publicado e as sessões são stateless, não ficam no Redis); **containers como root** (🟡: sem volume/socket nos
  containers root, raio de dano limitado); **`/api/health` público dispara I/O a Ghostfolio+brapi** (amplificação
  leve). → SECRET_KEY dedicado; `--requirepass` no redis; `USER` não‑root nos Dockerfiles; `/health` barato.

---

## Parte IX — Frontend, UX e design

A SPA está num bom patamar (react‑query, router, tipos gerados do OpenAPI, ErrorBoundary, parsing pt‑BR, badge
com cor semântica). Lacunas:

- 🟠 **Preço‑teto não aparece em nenhuma tela** (`AssetPage.tsx` lista P/L, P/VP, DY, ROE… mas não o teto) —
  núcleo do método invisível.
- 🟠 **A carteira não mostra DY/renda por posição nem alinhamento BESST** — só valor e %.
- 🟡 **`PortfolioPage` ainda usa `useEffect` manual** (`:79‑86`) enquanto `usePortfolio()` já existe pronto.
- 🟡 **Sem watchlist, sem calendário, sem onboarding** na UI.
- 🟡 **DY/crescimento da projeção sem min/max** (`IncomePage.tsx:111‑123`) — premissas irreais passam direto.
- 🟡 **Acessibilidade**: `PieChart` sem `aria-label`; legendas não navegáveis por teclado; sem `:focus-visible`.
- ⚪ **Sem dark mode** (trivial: o CSS já é todo *custom properties* — basta um `@media (prefers-color-scheme: dark)`);
  sem favicon/logo; sem microinterações; sem feedback de "✓ salvo".

---

## Parte X — Roadmap v3 priorizado (valor × esforço)

### P0 — Não perca dados; tape o buraco conceitual; endureça a exposição
1. 🔴 **Volume do SQLite no compose** + backup documentado. *(trivial, crítico)*
2. 🟠 **Renda fixa / reserva**: classe `CAIXA/RENDA_FIXA` nos alvos + reserva‑alvo priorizada + **CDI/Selic** como
   benchmark; **ligar** os stubs `reserve_target`/`bazin_target_mode`.
3. 🟡 **Endurecer a borda**: rate‑limit no `/login` + senha forte + `COOKIE_SECURE` automático + headers no nginx.
   **Recomendação forte:** publicar via **Tailscale**, não pela internet aberta.

### P1 — Traga o método para a tela e calibre os números
4. **Preço‑teto na UI** (ativo, carteira, watchlist) com selo abaixo/acima + **DY‑alvo configurável/atrelado à Selic**.
5. **Calibração Barsi/Bazin**: média de Bazin em **5 anos**; **ROE** como qualidade; **piso de liquidez R$5 mi**;
   payout médio com corte em 0,8; **BESST graduado** por mapa curado; critério de líder + DY médio>6%.
6. **DY trailing‑365d** (preservar datas) + **JCP×0,85 / yield líquido**. *(destrava calendário e YoC)*
7. **Score**: colapsar DY+Bazin numa dimensão de renda + dar peso à consistência/CAGR; reduzir o domínio do combo
   Graham; **normalizar valuation por setor**.
8. **Robustez do parser**: golden test + alerta de falha silenciosa; exceções específicas.
9. **Alocador**: lote real (ou rótulo fracionário); acionar teto por classe; fallback de `min_ticket`.

### P2 — Feche o ciclo "viver de dividendos" (inspirado no AGF)
10. **Yield on Cost** (capturar preço médio do Ghostfolio).
11. **Calendário/Mapa de proventos** + renda mês a mês.
12. **Objetivo de renda persistido + "Aportador"** (próximo melhor aporte) + alocação **pós‑aporte** + checklist /
    exportar ordens / "já comprei" (ligar `executed_orders`/`plan_history`).
13. **Perfil BESST da carteira** + DY/renda por posição; **rentabilidade vs CDI/IBOV**.
14. **Watchlist + ranking de descoberta** na UI.

### P3 — Acabamento
15. Projeção **nominal vs real** (inflação) + crescimento via **CAGR real** dos proventos.
16. Design system: **dark mode**, `:focus-visible`, microinterações, `aria` nos gráficos, favicon/logo.
17. Engenharia: **CI** (pytest + ruff + mypy + tsc), lockfiles, **containers não‑root**, `.dockerignore`,
    healthchecks, Redis com senha, TTL de sessão menor + revogação.

### Princípios para a v3
- **Mostre o método, não só calcule‑o:** preço‑teto, BESST e meta de renda devem estar **na tela**.
- **Reserva antes da renda variável:** modelar a renda fixa é pré‑requisito de uma carteira Barsi honesta.
- **Falhe alto, não baixo:** parser e fontes devem **alertar**, nunca virar "dado faltante" mudo.
- **Líquido > bruto:** yield e renda devem poder ser vistos **após o IR do JCP**.
- **Não perca o estado do usuário:** persistência só vale com volume e backup.

---

## Apêndice A — Notas de verificação (severidade ajustada)

A verificação adversarial confirmou os **fatos** de 9 achados de alta severidade, mas corrigiu a **gravidade**:

| Achado | Alegado | Verificado | Por quê |
|---|---|---|---|
| Double counting DY/Bazin | 🟠 | 🟡 | Numeradores distintos; *value trap* tratado no eixo de qualidade |
| DY não é trailing‑12m | 🟠 | 🟡 | Escolha de design defensável (ano completo evita trailing parcial) |
| JCP sem ×0,85 | 🟠 | 🟡 | IR só sobre a parcela JCP (~5–12%), viés consistente entre ativos |
| Bazin 6% hardcoded | 🟠 | 🟡 | 6% é canônico; entra como percentil, não cutoff absoluto frouxo |
| Yield bruto na projeção | 🟠 | 🟡 | Dividendo de ação é isento; só JCP/parcela tributa |
| Projeção nominal | 🟠 | 🟡 | Internamente consistente; engana só na interpretação de longo prazo |
| Login sem rate‑limit | 🟠 | 🟡 | Dados de leitura; brute‑force depende da entropia da senha |
| Redis sem senha | 🟠 | ⚪ | Não publicado; sessões são HMAC stateless (não ficam no Redis) |
| Containers root | 🟠 | 🟡 | Sem volume/socket nos containers root → raio de dano limitado |

*(O 🔴 do volume do SQLite foi verificado diretamente: `WORKDIR /app` + `DB_PATH=data/pomar.db` + ausência de
volume no backend = perda de dados no rebuild.)*

## Apêndice B — Catálogo de achados por subsistema

79 achados em 11 subsistemas. Resumo por severidade verificada: **1 🔴** (volume SQLite), **~3 🟠**
(renda fixa, preço‑médio/YoC, preço‑teto na UI), **~30 🟡** (calibrações financeiras, robustez, segurança de
borda, UX), restante ⚪. Os detalhes com `arquivo:linha` estão nas Partes III–IX. Subsistemas auditados:
`scoring`, `dividends/market_data`, `allocation`, `strategies/config`, `classify`, `analytics`,
`portfolio/ghostfolio`, `api/security`, `persistence/cache/brapi`, `frontend`, `infra/eng`.

## Apêndice C — Fontes da pesquisa

**AGF / metodologia:** acoesgarantem.com.br · lp.agf.com.br/agf102 · apps.apple.com (AGF App) ·
comoempreenderonline.com.br/agf · sagoinvestimentos.com.br/post/agf-vale-a-pena ·
finsidersbrasil.com.br (AGF 2.0/gamificação) · neofeed.com.br (fintech Barsi).
**Barsi/Bazin:** investidor10.com.br (Barsi; método Bazin) · infomoney.com.br (preço‑teto 6%) ·
clubedovalor.com.br/blog/decio-bazin · jornalri.com.br (preço‑teto) · mobills.com.br (resumo "Faça Fortuna
com Ações") · nordinvestimentos.com.br (dividendos Barsi) · focomacronews.com.br (BESST).

> ⚠️ Conteúdo educativo. **Não é recomendação de investimento.** Números de marketing do AGF (usuários, etc.)
> são incertos. Confira os dados antes de operar.
