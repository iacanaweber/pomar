#!/usr/bin/env bash
# Atualiza o Pomar em produção: pega o código novo do GitHub e sobe os containers.
#
# Uso:  ./update.sh
#
# Os containers rodam por IMAGEM (sem bind mount do código), então `git pull` sozinho
# não muda nada no ar — o rebuild é obrigatório. O volume `pomar-data` (SQLite) não é
# tocado; as migrações rodam no boot do backend.
set -euo pipefail

cd "$(dirname "$0")"

info() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!! \033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx \033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || die "docker não encontrado no PATH."
docker compose version >/dev/null 2>&1 || die "'docker compose' (v2) não disponível."
[ -f .env ] || die ".env não encontrado — copie de .env.example e preencha antes de subir."

# 1) Código novo -------------------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  die "Há alterações locais não commitadas. Resolva (commit ou 'git stash') e rode de novo."
fi

before="$(git rev-parse HEAD)"
info "Buscando alterações do GitHub…"
git pull --ff-only origin main
after="$(git rev-parse HEAD)"

if [ "$before" = "$after" ]; then
  info "Nenhum commit novo — seguindo mesmo assim para garantir que o que está no ar é o HEAD."
else
  info "Novidades aplicadas:"
  git --no-pager log --oneline "$before..$after"
fi

# 2) .env x .env.example -----------------------------------------------------
# O .env fica fora do Git; uma variável nova no exemplo precisa ser preenchida à mão.
faltando=""
while IFS= read -r chave; do
  grep -qE "^[[:space:]]*${chave}=" .env || faltando="${faltando} ${chave}"
done < <(grep -oE '^[A-Z_][A-Z0-9_]*=' .env.example | tr -d '=')
[ -n "$faltando" ] && warn "Variáveis presentes no .env.example e ausentes no seu .env:${faltando}"

# 3) Backup do SQLite antes das migrações ------------------------------------
# Best-effort: roda no container ANTIGO, antes do rebuild. Fica em data/backups,
# dentro do próprio volume (mesmo lugar do backup diário automático).
if docker compose ps --status running --services 2>/dev/null | grep -qx backend; then
  info "Backup do pomar.db antes de migrar…"
  docker compose exec -T backend python -c "
import os, sqlite3, datetime
os.makedirs('/app/data/backups', exist_ok=True)
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
dest = f'/app/data/backups/pre-update-{stamp}.db'
src = sqlite3.connect('/app/data/pomar.db')
dst = sqlite3.connect(dest)
src.backup(dst); dst.close(); src.close()
print(dest)
" || warn "Backup falhou — o backend guarda snapshots diários em data/backups; siga por sua conta."
else
  warn "Backend não está rodando; pulando o backup pré-update."
fi

# 4) Rebuild e subida --------------------------------------------------------
info "Reconstruindo as imagens e subindo…"
docker compose up -d --build

info "Estado dos containers:"
docker compose ps

# 5) Verificação rápida ------------------------------------------------------
porta="$(grep -E '^[[:space:]]*WEB_PORT=' .env | tail -1 | cut -d= -f2 | tr -d '"'"'"' ')"
porta="${porta:-3334}"
info "Aguardando a API responder…"
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${porta}/api/health" >/dev/null 2>&1; then
    info "Pomar no ar em http://localhost:${porta} 🌳"
    exit 0
  fi
  sleep 2
done
warn "A API não respondeu em ~60s. Veja o que houve com: docker compose logs -f backend"
exit 1
