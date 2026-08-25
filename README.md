# 🌳 Pomar

**Plante seus aportes, colha dividendos.**

App web pessoal para planejar aportes na B3. Você define uma **carteira alvo** — quanto cada
classe (Ações, FIIs, ETFs, BDRs e Renda fixa) deve pesar e, dentro de cada classe, quais itens
a compõem e com que percentual. Ao aportar, você informa quanto tem disponível e o Pomar
responde **quantas cotas comprar de quê** para chegar mais perto dessa carteira.

O app não escolhe ativos por você e não dá nota a ninguém: a seleção é sua, e a recomendação é
aritmética de rebalanceamento — quem está mais longe do peso-alvo recebe mais. Além disso ele
calcula o **preço-teto de Bazin** (dividendo médio ÷ DY-alvo) e destaca quem está abaixo dele
mesmo sem compra sugerida, e sinaliza *red flags* factuais (prejuízo, endividamento, payout
insustentável, liquidez baixa).

As abas são **Plantar** (o aporte), **Carteira** (atual × alvo e composição), **Reserva**
(renda fixa) e **Descobrir** (watchlist com radar de preço-teto). É instalável como **PWA**.

> ⚠️ Conteúdo educativo. **Não é recomendação de investimento.** Confira os dados antes de operar.

**Fontes:** carteira via [Ghostfolio](https://ghostfol.io) (somente leitura); dados de mercado
via [Fundamentus](https://www.fundamentus.com.br), [StatusInvest](https://statusinvest.com.br) e
[brapi.dev](https://brapi.dev).

---

## Instalação

Requisitos: **Docker** com Compose, uma instância do **Ghostfolio** acessível e um token grátis
da **brapi**.

```bash
git clone git@github.com:iacanaweber/pomar.git
cd pomar
cp .env.example .env      # preencha (veja abaixo)
docker compose up -d --build
```

Acesse **`http://<ip-do-servidor>:3334`** e entre com a sua `APP_PASSWORD`. O celular na mesma
rede abre o mesmo endereço — a interface é mobile-first, com a navegação fixa no rodapé.

### Instalar no celular

No Chrome (Android), menu → **Adicionar à tela inicial**; no Safari (iOS), compartilhar →
**Adicionar à Tela de Início**. O app abre em tela cheia, sem barra do navegador.

Uma ressalva honesta: **service worker exige HTTPS** (ou `localhost`). Servido em
`http://<ip-da-lan>:3334`, a instalação e o modo standalone funcionam, mas o cache offline e o
Web Push não — e o que o Chrome cria é um atalho, não um WebAPK. O app não esconde isso: a
linha de estado em *Plantar → Ajustes avançados* diz se o cache offline está ativo. Servindo
por HTTPS, ele passa a valer sozinho, sem mudar nada no código.

### O mínimo do `.env`

| Variável | Para quê |
|---|---|
| `APP_PASSWORD` | **Obrigatória.** Senha única que protege a API (ela expõe sua carteira). Sem ela, as rotas respondem 503. |
| `GHOSTFOLIO_URL` | Endereço do Ghostfolio alcançável **pelo container** (ex.: `http://192.168.0.10:3333`). |
| `GHOSTFOLIO_ACCESS_TOKEN` | *Security Token* da sua conta Ghostfolio (Settings → Security Token). |
| `BRAPI_TOKEN` | Token grátis em [brapi.dev/dashboard](https://brapi.dev/dashboard). |
| `WEB_PORT` | Porta web pública (padrão **3334**). |
| `COOKIE_SECURE` | `false` em HTTP/LAN (padrão); **`true` só sob HTTPS** — em HTTP, `true` impede o login. |

O `.env.example` documenta as demais (cache, CORS, backup, sessão).

### Primeiro uso

1. Abra a aba **Plantar** → **Montar carteira alvo**.
2. Defina as metas por classe (somando 100%) e, em cada classe, os itens e seus pesos
   (também somando 100%). O botão *"Usar pesos atuais da carteira"* semeia a partir do que você
   já tem no Ghostfolio.
3. Na aba **Reserva**, marque quais contas contam no patrimônio e informe a liquidez de cada
   uma (veja abaixo).
4. Volte ao Plantar, informe o aporte e gere as recomendações.

---

## Como a renda fixa entra na carteira

A renda fixa deixou de ser só um rastreador ao lado da carteira: ela é uma **classe** como as
outras. Três decisões, por conta:

| Campo | O que muda |
|---|---|
| **Conta no patrimônio** | Só contas marcadas entram no total, nos gráficos e no cálculo dos alvos. O padrão é **não** contar — nenhuma conta antiga mudou de comportamento sozinha. |
| **Propósito** | `investimento` ou `reservado para outro fim`. O segundo (a conta que provisiona o IR, por exemplo) **nunca** entra na carteira, mesmo marcado. |
| **Liquidez** | `resgate imediato`, `janela/vencimento` ou `carência`. Só a primeira satisfaz o **piso da reserva**. |

Os itens da cesta de Renda fixa não são tickers: são **tags de indexador** (CDI, Selic, IPCA,
prefixado, LCI, LCA, poupança, ou o que você criar). Um ETF de renda fixa (IMAB11, IRFM11) pode
receber uma tag e ser atribuído ao bucket `RENDA_FIXA` — a atribuição manual tem precedência
sobre a classificação automática.

### Piso da reserva

Não existe reserva de emergência separada: ela mora no mesmo Tesouro Selic que é sua alocação
em renda fixa, e duplicar o conceito faria o mesmo dinheiro aparecer duas vezes. O que existe é
um **piso em reais** dentro da classe:

```
alvo da renda fixa (R$) = max(peso da classe × patrimônio, piso corrigido)
```

Com piso de R$ 30.000, peso de 20% e patrimônio de R$ 100.000, o alvo é R$ 30.000. Conforme o
patrimônio cresce, o piso perde relevância sozinho. Um saque faz o déficit reaparecer, e ele
tem prioridade absoluta no próximo aporte.

**Só conta de resgate imediato satisfaz o piso.** Uma LCI travada por dois anos soma no peso
percentual da classe, mas não no piso — mostrar a reserva como cumprida enquanto o dinheiro
está preso é exatamente a falha que a reserva existe para evitar.

**Correção pelo IPCA (opcional).** Um piso nominal encolhe: a 4,5% ao ano, R$ 30.000 valem o
equivalente a ~R$ 19.000 em dez anos, e o número na tela nunca avisa. Ligando a correção, o
piso sobe alguns reais por mês (e o plano pede aportes residuais na renda fixa de vez em
quando — é o comportamento correto). Falha do Banco Central não quebra a tela: vale o nominal,
com aviso.

### Ordem de prioridade do aporte

1. **Déficit do piso da reserva** — só cobrível por conta de resgate imediato.
2. **Déficit percentual da classe Renda fixa**, rateado entre as tags de indexador.
3. **O que sobrar** vai para a renda variável, pelo rebalanceamento de sempre.

Como a compra de renda fixa é manual, a saída é uma instrução em reais (nunca quantidade de
cotas), com atalho para lançar o novo saldo na conta sugerida.

---

## Curva de rendimento

Comparar a evolução do VALOR da carteira com o Ibovespa é incorreto: o valor cresce por
aporte, não só por rentabilidade, e sem correção qualquer carteira que aporta "bate o
índice". A aba **Carteira → Rendimento** mostra duas medidas, que respondem perguntas
diferentes:

- **TWR** (ponderado pelo tempo) — "quão boas foram as escolhas". Neutraliza aportes e
  resgates encadeando os retornos entre snapshots semanais, com ponderação por **Dietz
  modificado** (cada fluxo pesa pela fração de dias que passou aplicado). É o único
  comparado com índice, porque índice não recebe aporte.
- **XIRR** (ponderado pelo dinheiro) — "quanto o meu dinheiro rendeu". Sensível a QUANDO
  o dinheiro entrou, e por isso não se compara a índice.

**Os fluxos vêm das duas fontes**, porque metade do patrimônio nunca esteve no Ghostfolio:
as transações de renda variável saem do Ghostfolio (`/api/v1/activities`) e os aportes e
resgates de renda fixa dos lançamentos do próprio app. Um dividendo entra como *saída*: o
preço cai ex-dividendo e o dinheiro sai do que é medido, então sem registrar a saída o TWR
leria a queda como prejuízo.

### Índices

| Índice | Fonte |
|---|---|
| Ibovespa | brapi `^BVSP` |
| CDI, IPCA, Dólar | Banco Central (SGS 12, 433, 1) |
| IFIX, IMA-B, IRF-M, S&P 500 | **ETF como proxy** (XFIX11, IMAB11, IRFM11, IVVB11) |
| Sua estratégia | pesos da sua própria carteira alvo |

Os quatro marcados como proxy não têm API pública gratuita; um ETF tem taxa de
administração e desvio em relação ao índice, e a tela diz isso. O S&P entra **em reais**
de propósito — é o que você efetivamente ganha, com o câmbio embutido.

O **benchmark composto** ("Sua estratégia") é o único comparável metodologicamente
defensável: confronta a execução da estratégia com a estratégia. O Ibovespa fica como
referência cultural, não como critério.

### Captura

Semanal, fechando no domingo, chave `yyyy-Www`. O container pode estar desligado no
domingo, então a captura não é um alarme que se perde: no boot e a cada 6 horas o app
pergunta "a semana corrente já foi gravada?" — e a resposta é idempotente. Captura fora da
janela é marcada como atrasada, e **semana perdida vira lacuna**, nunca valor inventado
com o preço de hoje. Com menos de quatro pontos a tela mostra tabela em vez de gráfico.

---

## Rótulos por dimensão

Em vez de uma coluna por ideia nova, o app tem rótulos `(dimensão, código)` e atribuições com
peso. Três dimensões hoje:

- **`bucket`** — a cesta em que o ativo é comprado. É a **única** que dirige a compra, e vence
  a classificação automática.
- **`indexer`** — a que indexador a aplicação rende. São os itens da cesta de Renda fixa.
- **`geography`** — Brasil ou Internacional. **Só visualização.**

Metas vinculantes em duas dimensões independentes formam um sistema sobredeterminado, sem
solução para a maioria das combinações — por isso a geografia tem meta *informativa*, com
desvio em p.p., e nenhum efeito sobre o que o app manda comprar.

A geografia tem defaults curados por ticker (`backend/app/data/geography.py`), com fallback por
sufixo, e a tela distingue o rótulo herdado do escolhido por você. A classificação é por
**domicílio do ativo, não por origem da receita**: empresa brasileira com receita majoritariamente
externa continua `BR`.

### Ativos fora do alvo

Uma posição cujo peso-alvo é zero (a classe foi a 0%, ou o ticker saiu da cesta) recebe o
estado `LEGACY` e **não tem razão ao alvo**: sem alvo, "desvio percentual" não é um número
pequeno, é um número que não existe. Ela ganha seção própria na Carteira, com valor em R$ e
participação no patrimônio — nunca uma barra de progresso contra denominador zero.

A preferência **"contar o que está fora do alvo no patrimônio"** (padrão: sim) decide a base
dos alvos em R$. Contando, a carteira fica subalocada até a venda, que é o retrato
aritmeticamente honesto.

### Persistência

Preferências, watchlist, renda fixa e histórico de planos ficam em SQLite no volume Docker
`pomar-data` — sobrevivem a `up --build`. Backup atômico:

```bash
docker compose exec backend python -c \
  "import sqlite3;s=sqlite3.connect('/app/data/pomar.db');d=sqlite3.connect('/app/data/backup.db');s.backup(d)"
```

---

## Desenvolvimento

```bash
# backend (FastAPI, Python >= 3.10)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
APP_PASSWORD=dev DEBUG=true uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest

# frontend (React + Vite)
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxy /api -> :8000)
npm test
npm run build
npm run gen:api  # regenera src/api/schema.d.ts a partir do backend em DEBUG
```

```
backend/   FastAPI
  api/          rotas + autenticação por senha
  services/     allocation (rebalanceamento), analysis (fatos do ativo), universe, reserve…
  providers/    Fundamentus · StatusInvest · brapi · Ghostfolio
  repositories/ SQLite com migrações aditivas
frontend/  React + Vite; tipos gerados do OpenAPI
```

**Onde ajustar o comportamento:** a carteira alvo é editável em `/alvo` e é o que define todas
as recomendações; o ticket mínimo fica em "Ajustes avançados" no Plantar e o piso da reserva na
aba Reserva; a watchlist inicial está em `backend/app/data/watchlist.py`, os defaults de
geografia em `backend/app/data/geography.py`, os rótulos embutidos em
`backend/app/data/labels_seed.py` e os textos dos tooltips em `backend/app/data/glossary.py`.

**Ícone:** `cd frontend && node scripts/gen-icons.mjs` regenera os PNGs, o favicon e o SVG a
partir da geometria no próprio script (sem dependência). As variações descartadas ficam em
`frontend/icons-src/`.

## Licença

[MIT](LICENSE). Conteúdo educativo; não é recomendação de investimento.
