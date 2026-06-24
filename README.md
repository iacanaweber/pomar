# 🌳 Pomar

**Plante seus aportes, colha dividendos.**

Pomar é um app web **pessoal e educativo** para planejar aportes na B3. Sempre que você recebe
dinheiro, informa quanto tem para investir e o Pomar recomenda **quais ativos comprar** para
compor melhor sua carteira — priorizando **desconto (valuation)**, **dividendos consistentes**,
**rebalanceamento** rumo às suas metas e **qualidade/risco** (para evitar armadilhas de valor).

As recomendações são **transparentes**: todo número tem um tooltip explicando o que é e de onde
vem, e o app mostra tanto **por que comprar** (reasons) quanto **por que NÃO comprar** (red flags).
As estratégias embutidas são inspiradas em grandes investidores:

| Estratégia | Inspiração | Ideia central |
|---|---|---|
| **Equilibrado** | — | Combina desconto, dividendos, rebalanceamento e setores perenes. |
| **Barsi** | Luiz Barsi | Dividendos perenes em setores essenciais — **BESST** (Bancos, Energia, Saneamento, Seguros, Telecom), buy & hold. |
| **Bazin** | Décio Bazin | **Preço-teto** = dividendo médio ÷ 6%. Comprar abaixo do teto garante yield mínimo. |
| **Graham** | Benjamin Graham | Margem de segurança: P/L e P/VP baixos, **P/L × P/VP ≤ 22,5**, lucro positivo. |
| **Dividend Growth** | — | Crescimento e consistência de proventos em pagadoras recorrentes. |
| **Valor + Qualidade** | — | Desconto com empresas de qualidade (penaliza dívida alta e payout insustentável). |

Cada estratégia ajusta os **pesos** das métricas (sempre visíveis na tela) e aplica **filtros de
elegibilidade** próprios — ex.: Graham exclui empresas com prejuízo ou caras demais.

> ⚠️ Conteúdo educativo. **Não é recomendação de investimento.** Confira os dados antes de operar.

---

## Como funciona

```
Login (senha) ─► Pomar lê sua carteira (Ghostfolio, somente leitura)
                  │
                  ├─►  dados da B3: Fundamentus (P/L, P/VP, setor, LPA/VPA…) +
                  │     StatusInvest (proventos) + brapi (fallback de cotação)
                  │
                  ├─►  pontua cada ativo em 4 famílias (valuation / dividendos /
                  │     rebalanceamento / setor) e aplica um eixo de RISCO/QUALIDADE
                  │
                  └─►  divide seu aporte entre os melhores (need-based por classe,
                        respeitando lotes, tetos de concentração e ticket mínimo)
```

- **Carteira:** [Ghostfolio](https://ghostfol.io) (`/api/v1/portfolio/holdings`), somente leitura.
- **Mercado:** [Fundamentus](https://www.fundamentus.com.br) + [StatusInvest](https://statusinvest.com.br)
  + [brapi.dev](https://brapi.dev) como fallback de cotação.
- **Transparência:** cada métrica carrega sua fonte; dado faltante nunca é inventado — a métrica
  vira indisponível e seu peso é redistribuído (a "completude" aparece em cada ativo).
- **Risco em primeiro plano:** um selo (🟢/🟡/🔴) e *red flags* sinalizam prejuízo, payout
  insustentável, endividamento e baixa liquidez — para o "barato que paga muito" não enganar.

### Destaques da v2
- 🔐 **Autenticação por senha única** — a API (que expõe sua carteira) fica protegida.
- 🧮 **Score corrigido**: Graham pela distância ao teto 22,5, Número de Graham (LPA/VPA),
  Bazin só sobre anos pagos, percentil sem viés.
- 🛡️ **Eixo de risco/qualidade** anti *value-trap* + red flags por ativo.
- 💰 **Alocador need-based**: distribui o aporte pela carteira *resultante* (sem sobre-corrigir),
  com slots por classe e reaproveitamento da sobra de arredondamento.
- 🏷️ **Classificação de setor própria** (mapa curado + default por classe): ETFs/BDRs deixam de
  cair em "Sem setor".
- 🎛️ **Painel de ajustes avançados** na UI: metas por classe, pesos, nº de ativos, teto e ticket.
- 💾 **Persistência** (SQLite) de preferências e watchlist.
- 🥧 **Carteira com detalhamento**: clique numa fatia (classe/setor/tag) e veja os ativos dentro.

---

## Configuração

1. **Crie o `.env`** a partir do exemplo:
   ```bash
   cp .env.example .env
   ```
2. **Preencha o `.env`** (mínimo): `APP_PASSWORD`, `GHOSTFOLIO_ACCESS_TOKEN`, `BRAPI_TOKEN`.

| Variável | Para quê |
|---|---|
| `APP_PASSWORD` | **Obrigatória.** Senha única que protege a API. Sem ela, as rotas respondem 503. |
| `COOKIE_SECURE` | `false` em HTTP/LAN (padrão); **`true` somente sob HTTPS** (senão o login não funciona). |
| `DEBUG` | `true` expõe `/docs` e `/api/debug/*` (só em desenvolvimento). Produção: `false`. |
| `GHOSTFOLIO_URL` | Endereço do Ghostfolio alcançável pelo container (ex.: `http://192.168.0.10:3333`; ou `http://host.docker.internal:3333`). |
| `GHOSTFOLIO_ACCESS_TOKEN` | *Security Token* do Ghostfolio (**Settings → Security Token**). O Pomar troca por um JWT sozinho. |
| `BRAPI_TOKEN` / `BRAPI_PLAN` | Token grátis da brapi (https://brapi.dev/dashboard); `BRAPI_PLAN` = `free` (padrão) ou `pro`. |
| `CORS_ORIGINS` | Vazio = só mesma origem (recomendado). Liste origens só se precisar de acesso cross-origin. |
| `REDIS_URL` / `REDIS_PASSWORD` | Cache (o `docker-compose` já sobe um Redis). Vazio = cache em memória. |
| `DB_PATH` | Banco SQLite de preferências/watchlist (padrão `data/pomar.db`). |
| `WEB_PORT` | Porta web pública (padrão **3334**). |

---

## Subir no servidor (Docker)

```bash
docker compose up -d --build
```

Acesse em **`http://<ip-do-servidor>:3334`** e entre com a sua `APP_PASSWORD`.

> 💾 **Persistência.** O banco (preferências, watchlist, renda fixa, histórico) fica no volume
> Docker `pomar-data` (montado em `/app/data`), então sobrevive a `up --build`. **Backup atômico:**
> `docker compose exec backend sqlite3 /app/data/pomar.db ".backup '/app/data/backup.db'"`.

### Acesso pelo celular (LAN)
O celular na **mesma rede** abre o mesmo endereço. A interface é responsiva (mobile-first) e os
tooltips funcionam por toque. Em HTTP, mantenha `COOKIE_SECURE=false`.

### HTTPS (recomendado para exposição externa)
Para servir por `https://` (ex.: via um reverse proxy como **Caddy** ou **Nginx Proxy Manager**
com certificado Let's Encrypt), aponte o proxy para o frontend (porta `WEB_PORT`) e então defina
`COOKIE_SECURE=true` no `.env`. Em HTTP a senha trafega em texto claro — evite expor sem TLS.

---

## Desenvolvimento local

**Backend** (FastAPI):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
APP_PASSWORD=dev DEBUG=true uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest                                                       # testes
```

**Frontend** (React + Vite):
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxy /api -> :8000)
npm run build        # checagem de tipos + build de produção
npm run gen:api      # regenera src/api/schema.d.ts a partir do /openapi.json (backend em DEBUG)
```

---

## Estrutura

```
backend/   FastAPI:
  api/         rotas + segurança (auth por senha) + injeção de dependências
  providers/   Fundamentus / StatusInvest / brapi / Ghostfolio
  services/    universe, market_data, classify (classe+setor), scoring, allocation, strategies
  repositories/ SQLite (preferências, watchlist, …) com migrações
  models/      contrato de transparência (métricas com fonte) ; data/  watchlist + glossário
frontend/  React + Vite: login, aba de aporte (ranking + decomposição do score + selo de risco)
           e aba "Minha carteira" (donut com detalhamento por fatia). Tipos gerados do OpenAPI.
docker-compose.yml   backend + frontend (nginx) + redis (cache).
```

### Personalização
- **Watchlist (universo):** editável via API (`/api/watchlist`) e persistida no SQLite; a lista
  curada inicial fica em `backend/app/data/watchlist.py` (semente).
- **Setores curados:** `SECTOR_BY_TICKER` em `backend/app/data/watchlist.py`.
- **Pesos/alvos default e presets de estratégia:** `backend/app/config.py`.
- **Parâmetros do plano (metas, pesos, nº de ativos, teto, ticket):** ajustáveis na própria UI
  ("Ajustes avançados") e persistidos por usuário.
- **Textos do glossário (tooltips):** `backend/app/data/glossary.py`.

---

## Licença

[MIT](LICENSE). Conteúdo educativo; não é recomendação de investimento.
