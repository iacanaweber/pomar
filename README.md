# 🌳 Pomar

**Plante seus aportes, colha dividendos.**

App web pessoal para planejar aportes na B3. Você define uma **carteira alvo** — quanto cada
classe (Ações, FIIs, ETFs, BDRs) deve pesar e, dentro de cada classe, quais ativos a compõem e
com que percentual. Ao aportar, você informa quanto tem disponível e o Pomar responde **quantas
cotas comprar de quê** para chegar mais perto dessa carteira.

O app não escolhe ativos por você e não dá nota a ninguém: a seleção é sua, e a recomendação é
aritmética de rebalanceamento — quem está mais longe do peso-alvo recebe mais. Além disso ele
calcula o **preço-teto de Bazin** (dividendo médio ÷ DY-alvo) e destaca quem está abaixo dele
mesmo sem compra sugerida, sinaliza *red flags* factuais (prejuízo, endividamento, payout
insustentável, liquidez baixa) e desvia parte do aporte para a reserva enquanto ela não atinge
o alvo.

As abas são **Plantar** (o aporte), **Carteira** (atual × alvo e composição), **Reserva**
(rastreador de renda fixa) e **Descobrir** (watchlist com radar de preço-teto).

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
rede abre o mesmo endereço — a interface é mobile-first.

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
2. Defina as metas por classe (somando 100%) e, em cada classe, os ativos e seus pesos
   (também somando 100%). O botão *"Usar pesos atuais da carteira"* semeia a partir do que você
   já tem no Ghostfolio.
3. Volte ao Plantar, informe o aporte e gere as recomendações.

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
as recomendações; ticket mínimo e reserva-alvo ficam em "Ajustes avançados" no Plantar; a
watchlist inicial está em `backend/app/data/watchlist.py` e os textos dos tooltips em
`backend/app/data/glossary.py`.

## Licença

[MIT](LICENSE). Conteúdo educativo; não é recomendação de investimento.
