"""Rótulos EMBUTIDOS, por dimensão — semeados de forma idempotente, nunca por migração.

Ficam fora do `_MIGRATIONS` de propósito: acrescentar um indexador novo daqui a seis meses
não deveria exigir uma versão de schema, e o `_split_statements` do motor de migração
quebra em `;` dentro de literal de texto. O seed roda por `INSERT OR IGNORE` (ver
`repositories/labels_repo.ensure_builtins`), então rodar de novo é inofensivo e um rótulo
renomeado pelo usuário não é revertido.

As três dimensões de hoje:

* **bucket** — a única que DIRIGE a compra. É a generalização de `class_targets_json`:
  atribuir um ticker a um bucket tem precedência absoluta sobre a classificação automática
  de `services/classify.py` (é assim que um ETF de renda fixa vira `RENDA_FIXA`).
* **indexer** — a que indexador a aplicação rende. São os ITENS da cesta de `RENDA_FIXA`,
  no lugar que os tickers ocupam nas outras classes.
* **geography** — só visualização. Ver `data/geography.py` para os defaults por ticker.
"""
from __future__ import annotations

# Dimensões conhecidas. Restringir é deliberado: uma dimensão com typo criaria um universo
# paralelo silencioso, onde os rótulos existem mas nenhuma tela os procura.
DIMENSIONS = ("bucket", "indexer", "geography")

# A dimensão `bucket` de nível 1 são as próprias classes da carteira alvo.
BUCKET_LABELS: tuple[tuple[str, str], ...] = (
    ("STOCK", "Ações"),
    ("FII", "FIIs"),
    ("ETF", "ETFs"),
    ("BDR", "BDRs"),
    ("RENDA_FIXA", "Renda fixa"),
)

INDEXER_LABELS: tuple[tuple[str, str], ...] = (
    ("CDI", "CDI"),
    ("SELIC", "Selic"),
    ("IPCA", "IPCA+"),
    ("PREFIXADO", "Prefixado"),
    ("LCI", "LCI"),
    ("LCA", "LCA"),
    ("POUPANCA", "Poupança"),
)

GEOGRAPHY_LABELS: tuple[tuple[str, str], ...] = (
    ("BR", "Brasil"),
    ("INTL", "Internacional"),
)

BUILTIN_LABELS: tuple[tuple[str, str, str], ...] = (
    *(("bucket", code, name) for code, name in BUCKET_LABELS),
    *(("indexer", code, name) for code, name in INDEXER_LABELS),
    *(("geography", code, name) for code, name in GEOGRAPHY_LABELS),
)

# Bucket residual da renda fixa: conta que conta na carteira mas não tem indexador algum.
# Existe como constante (e não como rótulo no banco) para nunca virar um item editável da
# cesta — é um estado a resolver, não uma escolha de alocação.
NO_INDEXER_CODE = "SEM_INDEXADOR"
NO_INDEXER_NAME = "Sem indexador"
