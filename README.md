# 🌳 Pomar

**Plante seus aportes, colha dividendos.**

Pomar é um app web **pessoal e educativo** para planejar aportes na B3. Você define a
**carteira alvo** — quanto cada classe (Ações/FIIs/ETFs/BDRs) deve pesar e, dentro de cada
classe, quais ativos a compõem e com que percentual. Na hora de investir, informa quanto tem
disponível e o Pomar responde **quantas cotas comprar de quê** para chegar mais perto dessa
carteira.

O app **não escolhe ativos por você e não dá nota a ninguém**: a seleção é sua, e a
recomendação é aritmética de rebalanceamento — quem está mais longe do peso-alvo recebe mais.

O que o Pomar acrescenta a essa conta:

| Recurso | Para quê |
|---|---|
| **Preço-teto de Bazin** | Dividendo médio (janela de 5 anos) ÷ DY-alvo. Um ativo pode estar no peso certo e ainda assim barato — ele vem destacado mesmo com compra sugerida zero, para você decidir se antecipa. |
| **Red flags factuais** | Prejuízo, endividamento, payout insustentável, liquidez baixa, histórico irregular de proventos. Dado ausente é neutro, nunca inventado. |
| **Reserva antes da RV** | Disciplina Barsi: parte do aporte vai para a reserva/renda fixa até o alvo ser atingido. |
| **Lote e ticket mínimo** | A sugestão sai em número inteiro de cotas, com piso para abrir posição nova. |

Todo número tem um tooltip explicando o que é e de onde vem.

> ⚠️ Conteúdo educativo. **Não é recomendação de investimento.** Confira os dados antes de operar.

---

## Como funciona

```
Login (senha) ─► Pomar lê sua carteira (Ghostfolio, somente leitura)
                  │
                  ├─►  dados da B3: Fundamentus (P/L, P/VP, setor, LPA/VPA…) +
                  │     StatusInvest (proventos) + brapi (fallback de cotação)
                  │
                  ├─►  compara a carteira ATUAL com a sua carteira alvo (metas por
                  │     classe + composição por ativo dentro de cada classe)
                  │
                  └─►  divide o aporte pelo DÉFICIT até o alvo (need-based entre as
                        classes marcadas, por desvio dentro da cesta, respeitando
                        lote e ticket mínimo)
```

- **Carteira:** [Ghostfolio](https://ghostfol.io) (`/api/v1/portfolio/holdings`), somente leitura.
- **Mercado:** [Fundamentus](https://www.fundamentus.com.br) + [StatusInvest](https://statusinvest.com.br)
  + [brapi.dev](https://brapi.dev) como fallback de cotação.
- **Transparência:** cada número carrega sua fonte; dado faltante nunca é inventado — o campo
  fica vazio em vez de receber uma estimativa.
- **Risco em primeiro plano:** um selo (🟢/🟡/🔴) e *red flags* sinalizam prejuízo, payout
  insustentável, endividamento e baixa liquidez — para o "barato que paga muito" não enganar.

### Abas
- **Plantar** — o aporte: valor disponível, quais classes entram (por padrão todas) e as compras
  sugeridas. A configuração da **Carteira alvo** fica em `/alvo`, linkada daqui.
- **Carteira** — donut com detalhamento por fatia (classe/setor/tag) e os ativos dentro.
- **Reserva** — rastreador de renda fixa (saldos, rendimento, % do CDI) que alimenta a
  reserva-alvo do plano.
- **Descobrir** — watchlist com radar de preço-teto: o viveiro de onde saem candidatos à
  carteira alvo.

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
  services/    universe, market_data, classify (classe+setor), analysis (fatos do ativo),
               allocation (rebalanceamento), reserve, fixed_income
  repositories/ SQLite (preferências, watchlist, planos, renda fixa…) com migrações
  models/      contrato da API ; data/  watchlist curada + glossário
frontend/  React + Vite: login, Plantar (aporte + compras sugeridas), Carteira alvo (/alvo),
           Carteira, Reserva e Descobrir. Tipos gerados do OpenAPI.
docker-compose.yml   backend + frontend (nginx) + redis (cache).
```

### Personalização
- **Watchlist (universo):** editável via API (`/api/watchlist`) e persistida no SQLite; a lista
  curada inicial fica em `backend/app/data/watchlist.py` (semente).
- **Setores curados:** `SECTOR_BY_TICKER` em `backend/app/data/watchlist.py`.
- **Alvos default por classe:** `backend/app/config.py` (ponto de partida; a UI sobrescreve).
- **Carteira alvo (metas por classe + composição por ativo):** editável em `/alvo` e persistida
  no SQLite. É o que define TODAS as recomendações.
- **Ticket mínimo e reserva-alvo:** "Ajustes avançados" no Plantar.
- **Textos do glossário (tooltips):** `backend/app/data/glossary.py`.

---

## Licença

[MIT](LICENSE). Conteúdo educativo; não é recomendação de investimento.
