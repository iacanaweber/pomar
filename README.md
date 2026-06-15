# 🌳 Pomar

**Plante seus aportes, colha dividendos.**

Pomar é um app web pessoal para planejar aportes na B3. Sempre que você recebe dinheiro,
informa quanto tem para investir e o Pomar recomenda **quais ativos comprar** para compor
melhor sua carteira — priorizando **desconto (valuation)**, **dividendos consistentes** e
**rebalanceamento** rumo às suas metas.

As recomendações são **transparentes e educativas**: todo número tem um tooltip explicando
o que é e de onde vem. As estratégias embutidas são inspiradas em grandes investidores:

| Estratégia | Inspiração | Ideia central |
|---|---|---|
| **Barsi** | Luiz Barsi | Dividendos perenes em setores essenciais — **BESST** (Bancos, Energia, Saneamento, Seguros, Telecom), buy & hold. |
| **Bazin** | Décio Bazin | **Preço-teto** = dividendo médio ÷ 6%. Comprar abaixo do teto garante yield mínimo. |
| **Graham** | Benjamin Graham | Margem de segurança: P/VP e P/L baixos, **P/L × P/VP ≤ 22,5**. |
| **Equilibrado** | — | Combina desconto, dividendos, rebalanceamento e setores perenes. |

Escolher uma estratégia só **muda os pesos** das métricas — e os pesos ficam sempre visíveis
na tela.

> ⚠️ Conteúdo educativo. **Não é recomendação de investimento.** Confira os dados antes de operar.

---

## Como funciona

```
Você informa o aporte  ──►  Pomar lê sua carteira (Ghostfolio, somente leitura)
                              │
                              ├─►  busca dados da B3 (brapi.dev): preço, fundamentos, dividendos
                              │
                              ├─►  pontua cada ativo (Barsi / Bazin / Graham / rebalanceamento)
                              │
                              └─►  divide seu aporte entre os melhores, respeitando lotes e limites
```

- **Fontes:** carteira via [Ghostfolio](https://ghostfol.io) (`/api/v1/portfolio/holdings`);
  mercado via [brapi.dev](https://brapi.dev).
- **Transparência:** cada métrica carrega sua fonte; o glossário explica tudo em linguagem simples.
- **Dados faltantes nunca são inventados:** a métrica é marcada como indisponível e seu peso é
  redistribuído entre as disponíveis (a "completude" aparece em cada ativo).

---

## Configuração

1. **Crie o `.env`** a partir do exemplo:
   ```bash
   cp .env.example .env
   ```
2. **Preencha o `.env`:**
   - `GHOSTFOLIO_URL` — endereço do seu Ghostfolio alcançável pelo container. Recomendado: o
     **IP da LAN + porta** que você já usa (ex.: `http://192.168.0.10:3333`). Como o Ghostfolio
     roda em outro container, o `docker-compose.yml` também habilita
     `http://host.docker.internal:3333` como alternativa.
   - `GHOSTFOLIO_ACCESS_TOKEN` — o *Security Token* da sua conta Ghostfolio
     (em **Settings → Security Token**). O Pomar troca isso por um JWT temporário sozinho.
   - `BRAPI_TOKEN` — token grátis da brapi (crie em https://brapi.dev/dashboard). Sem token,
     só funcionam alguns poucos tickers de teste.
   - `WEB_PORT` — porta web (padrão **3334**).

---

## Subir no servidor (Docker)

```bash
docker compose up -d --build
```

Acesse em **`http://<ip-do-servidor>:3334`**.

### Acesso pelo celular

O celular na **mesma rede** abre o mesmo endereço: `http://<ip-do-servidor>:3334`. A interface
é responsiva (mobile-first) e os tooltips funcionam por toque. Para descobrir o IP do servidor:
`ip addr` (Linux) ou veja no painel do seu roteador.

---

## Desenvolvimento local

**Backend** (FastAPI):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload          # http://localhost:8000/docs
pytest                                  # testes
```

**Frontend** (React + Vite):
```bash
cd frontend
npm install
npm run dev                             # http://localhost:5173 (proxy /api -> :8000)
```

---

## Estrutura

```
backend/   FastAPI: clientes (Ghostfolio/brapi), serviços (universe/scoring/allocation),
           modelos (contrato de transparência) e glossário.
frontend/  React + Vite: página de aporte, ranking com decomposição do score e tooltips.
docker-compose.yml   backend + frontend (nginx) + redis (cache).
```

### Personalização

- **Universo de candidatos:** edite `backend/app/data/watchlist.py` (ações, FIIs, ETFs, BDRs).
- **Pesos/alvos default e presets:** `backend/app/config.py`.
- **Textos do glossário (tooltips):** `backend/app/data/glossary.py`.
