"""Rotas da carteira: a leitura crua do Ghostfolio e a composição do patrimônio."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.data.labels_seed import GEOGRAPHY_LABELS
from app.deps import get_cache, get_db, get_ghostfolio
from app.models.portfolio import (
    ExposureDimension,
    ExposureItem,
    ExposureResponse,
    Portfolio,
)
from app.repositories import fixed_income_repo, labels_repo, preferences_repo
from app.services import exposure as exposure_svc
from app.services import fixed_income as fi
from app.models.plan import CLASS_LABEL
from app.services.portfolio_service import get_enriched_portfolio

router = APIRouter()

_GEO_NAME = dict(GEOGRAPHY_LABELS)


@router.get("/portfolio", response_model=Portfolio)
async def portfolio() -> Portfolio:
    try:
        overrides = await labels_repo.bucket_overrides(get_db())
        return await get_enriched_portfolio(get_ghostfolio(), get_cache(), overrides)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Não consegui ler o Ghostfolio: {exc}. Verifique GHOSTFOLIO_URL e o token.",
        )


@router.get("/portfolio/exposure", response_model=ExposureResponse)
async def exposure() -> ExposureResponse:
    """Composição do patrimônio INTEIRO — renda variável mais a renda fixa que conta.

    Enquanto a renda fixa vivia só na aba Reserva, o gráfico da Carteira contava a história
    toda; deixou de contar no momento em que uma conta pode ser marcada como patrimônio.
    Sem isto, quem tem 30% em Tesouro Selic veria uma carteira 100% em bolsa.

    `geography` e `sector` são visualização: nenhuma decisão de compra passa por elas. A
    meta é opcional e informativa — metas vinculantes em duas dimensões independentes
    formam um sistema sobredeterminado, e resolver isso é problema de otimização com
    folga, não de rebalanceamento proporcional.
    """
    db = get_db()
    warnings: list[str] = []

    posicoes: list[dict] = []
    rv_total = 0.0
    try:
        overrides = await labels_repo.bucket_overrides(db)
        pf = await get_enriched_portfolio(get_ghostfolio(), get_cache(), overrides)
        warnings.extend(pf.warnings)
        rv_total = pf.total_value
        posicoes = [
            {"ticker": p.ticker, "asset_class": p.asset_class, "sector": p.sector, "value": p.value}
            for p in pf.positions
        ]
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            f"Não consegui ler a carteira ({exc}); a composição mostra só a renda fixa."
        )

    contas = [a for a in await fixed_income_repo.balances(db) if fi.counts_in_portfolio(a)]
    composicao = exposure_svc.compose(
        posicoes,
        contas,
        await labels_repo.assignments_by_subject(db, "geography", "ticker"),
        await labels_repo.assignments_by_subject(db, "geography", "fi_account"),
    )

    prefs = await preferences_repo.get(db, get_settings())
    metas = prefs.get("dimension_targets") or {}
    total = composicao["total"]

    def nome(dimension: str, code: str) -> str:
        if dimension == "class":
            return CLASS_LABEL.get(code, code)
        if dimension == "geography":
            return _GEO_NAME.get(code, code)
        return code

    dimensoes = [
        ExposureDimension(
            dimension=dim,
            items=[
                ExposureItem(**item, name=nome(dim, item["code"]))
                for item in exposure_svc.with_targets(
                    composicao[chave], total, metas.get(dim), composicao["members"][dim]
                )
            ],
        )
        for dim, chave in (
            ("class", "by_class"),
            ("geography", "by_geography"),
            ("sector", "by_sector"),
        )
    ]
    return ExposureResponse(
        total=total,
        rv_total=round(rv_total, 2),
        rf_total=round(total - rv_total, 2),
        dimensions=dimensoes,
        warnings=warnings,
    )
