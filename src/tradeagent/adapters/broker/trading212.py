"""Trading 212 broker adapter — executes trades via the T212 Practice API."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from tradeagent.adapters.base import (
    BrokerAdapter,
    BrokerInstrument,
    BrokerPosition,
    OrderRequest,
    OrderStatus,
)
from tradeagent.core.exceptions import BrokerError
from tradeagent.core.logging import get_logger

log = get_logger(__name__)

_RETRY_DELAYS = [2.0, 4.0]


class Trading212Adapter(BrokerAdapter):
    """Broker adapter for Trading 212 Practice API.

    Handles rate limiting, retries on 5xx, and ticker mapping.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://demo.trading212.com/api/v0",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": api_key},
            timeout=timeout,
        )
        self._ticker_map: dict[str, str] | None = None

    async def place_order(self, order: OrderRequest) -> OrderStatus:
        """Place a market order via POST /equity/orders."""
        payload = {
            "ticker": order.ticker,
            "quantity": float(order.quantity),
            "orderType": order.order_type,
        }
        if order.limit_price is not None:
            payload["limitPrice"] = float(order.limit_price)

        data = await self._request("POST", "/equity/orders", json=payload)

        order_id = str(data.get("id", ""))
        status = self._map_status(data.get("status", ""))

        # Poll for final status if still pending
        if status == "PENDING":
            return await self._poll_order_status(order_id)

        return OrderStatus(
            broker_order_id=order_id,
            ticker=order.ticker,
            side=order.side,
            status=status,
            filled_quantity=Decimal(str(data.get("filledQuantity", 0))) or None,
            filled_price=Decimal(str(data.get("filledPrice", 0))) or None,
            filled_at=datetime.now(tz=timezone.utc) if status == "FILLED" else None,
        )

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Get order status via GET /equity/orders/{id}."""
        data = await self._request("GET", f"/equity/orders/{broker_order_id}")

        status = self._map_status(data.get("status", ""))
        return OrderStatus(
            broker_order_id=broker_order_id,
            ticker=data.get("ticker", ""),
            side=data.get("side", "").upper(),
            status=status,
            filled_quantity=Decimal(str(data.get("filledQuantity", 0))) or None,
            filled_price=Decimal(str(data.get("filledPrice", 0))) or None,
            filled_at=datetime.now(tz=timezone.utc) if status == "FILLED" else None,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        """Get all open positions via GET /equity/portfolio."""
        data = await self._request("GET", "/equity/portfolio")

        positions = []
        for item in data if isinstance(data, list) else []:
            positions.append(
                BrokerPosition(
                    ticker=item.get("ticker", ""),
                    quantity=Decimal(str(item.get("quantity", 0))),
                    avg_price=Decimal(str(item.get("averagePrice", 0))),
                    current_price=Decimal(str(item.get("currentPrice", 0))),
                    unrealized_pnl=Decimal(str(item.get("ppl", 0))),
                )
            )
        return positions

    async def get_instruments(
        self, *, search: str | None = None
    ) -> list[BrokerInstrument]:
        """Get available instruments via GET /equity/metadata/instruments."""
        params = {}
        if search:
            params["search"] = search

        data = await self._request(
            "GET", "/equity/metadata/instruments", params=params
        )

        instruments = []
        for item in data if isinstance(data, list) else []:
            instruments.append(
                BrokerInstrument(
                    ticker=item.get("ticker", ""),
                    name=item.get("name", ""),
                    exchange=item.get("exchange", ""),
                    currency=item.get("currencyCode", ""),
                    isin=item.get("isin"),
                    min_quantity=Decimal(str(item.get("minTradeQuantity", 0)))
                    if item.get("minTradeQuantity")
                    else None,
                )
            )
        return instruments

    async def build_ticker_map(self) -> dict[str, str]:
        """Fetch instruments and build yfinance <-> T212 ticker mapping."""
        instruments = await self.get_instruments()
        self._ticker_map = {i.ticker: i.ticker for i in instruments}
        return self._ticker_map

    async def close(self) -> None:
        """Close the httpx client."""
        await self._client.aclose()

    # ── Private helpers ──────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict | list:
        """Make an HTTP request with retry on 5xx and rate limit handling."""
        last_error: Exception | None = None

        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                response = await self._client.request(
                    method, path, json=json, params=params
                )

                # Rate limiting
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "5"))
                    log.warning(
                        "rate_limited",
                        path=path,
                        retry_after=retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                # 4xx errors — do not retry
                if 400 <= response.status_code < 500:
                    raise BrokerError(
                        f"Broker API error {response.status_code}: {response.text}"
                    )

                # 5xx errors — retry with backoff
                if response.status_code >= 500:
                    if attempt < len(_RETRY_DELAYS):
                        delay = _RETRY_DELAYS[attempt]
                        log.warning(
                            "broker_5xx_retrying",
                            status=response.status_code,
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise BrokerError(
                        f"Broker API error {response.status_code} after retries"
                    )

                response.raise_for_status()
                return response.json()

            except BrokerError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < len(_RETRY_DELAYS):
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                raise BrokerError(f"HTTP request failed: {exc}") from exc

        raise BrokerError(f"Request failed after retries: {last_error}")

    async def _poll_order_status(
        self,
        order_id: str,
        max_polls: int = 5,
        poll_interval: float = 10.0,
    ) -> OrderStatus:
        """Poll order status until terminal state or max polls reached."""
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            status = await self.get_order_status(order_id)
            if status.status in ("FILLED", "FAILED", "CANCELLED"):
                return status
        return await self.get_order_status(order_id)

    @staticmethod
    def _map_status(t212_status: str) -> str:
        """Map Trading 212 order status to our TradeStatus."""
        mapping = {
            "NEW": "PENDING",
            "PENDING": "PENDING",
            "CONFIRMED": "PENDING",
            "FILLED": "FILLED",
            "REJECTED": "FAILED",
            "CANCELLED": "CANCELLED",
            "CANCELLING": "CANCELLED",
        }
        return mapping.get(t212_status.upper(), "PENDING")
