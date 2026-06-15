"""Cliente do Ghostfolio (somente leitura).

Fluxo: POST /api/v1/auth/anonymous {accessToken} -> JWT; depois
GET /api/v1/portfolio/holdings com Authorization: Bearer <jwt>.
Reautentica automaticamente em caso de 401.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.models.portfolio import Allocations, Portfolio, Position

# Mapeia tipos do Ghostfolio para as classes que o Pomar usa.
_CLASS_MAP = {
    "EQUITY": "STOCK",
    "STOCK": "STOCK",
    "ETF": "ETF",
    "MUTUALFUND": "ETF",
    "REALESTATE": "FII",
}


class GhostfolioClient:
    def __init__(self, base_url: str, access_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self._jwt: Optional[str] = None

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            f"{self.base_url}/api/v1/auth/anonymous",
            json={"accessToken": self.access_token},
        )
        resp.raise_for_status()
        self._jwt = resp.json()["authToken"]
        return self._jwt

    async def _get(self, client: httpx.AsyncClient, path: str) -> dict:
        if not self._jwt:
            await self._authenticate(client)
        headers = {"Authorization": f"Bearer {self._jwt}"}
        resp = await client.get(f"{self.base_url}{path}", headers=headers)
        if resp.status_code == 401:  # JWT expirou: reautentica e tenta de novo
            await self._authenticate(client)
            headers = {"Authorization": f"Bearer {self._jwt}"}
            resp = await client.get(f"{self.base_url}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def get_portfolio(self) -> Portfolio:
        async with httpx.AsyncClient(timeout=20.0) as client:
            data = await self._get(client, "/api/v1/portfolio/holdings")

        holdings = data.get("holdings", data.get("positions", []))
        total = sum(float(h.get("valueInBaseCurrency") or h.get("value") or 0) for h in holdings)
        positions = []
        by_class: dict[str, float] = {}
        by_sector: dict[str, float] = {}
        for h in holdings:
            value = float(h.get("valueInBaseCurrency") or h.get("value") or 0)
            if value <= 0:
                continue
            raw_type = (h.get("assetSubClass") or h.get("assetClass") or "").upper()
            cls = _CLASS_MAP.get(raw_type, "STOCK")
            sector = _first_sector(h)
            weight = value / total if total else 0.0
            positions.append(
                Position(
                    ticker=h.get("symbol", "?"),
                    name=h.get("name"),
                    asset_class=cls,
                    sector=sector,
                    value=value,
                    weight=weight,
                    quantity=h.get("quantity"),
                )
            )
            by_class[cls] = by_class.get(cls, 0.0) + weight
            if sector:
                by_sector[sector] = by_sector.get(sector, 0.0) + weight

        return Portfolio(
            total_value=round(total, 2),
            currency=data.get("currency", "BRL"),
            positions=positions,
            allocations=Allocations(by_class=by_class, by_sector=by_sector),
            as_of=datetime.now(timezone.utc).isoformat(),
        )

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{self.base_url}/api/v1/health")
                return resp.status_code == 200
        except Exception:
            return False


def _first_sector(holding: dict) -> Optional[str]:
    countries = holding.get("sectors") or []
    if countries and isinstance(countries, list):
        return countries[0].get("name")
    return holding.get("sector")
