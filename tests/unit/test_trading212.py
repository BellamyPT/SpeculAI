"""Unit tests for Trading212Adapter."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tradeagent.adapters.base import BrokerPosition, OrderRequest
from tradeagent.adapters.broker.trading212 import Trading212Adapter
from tradeagent.core.exceptions import BrokerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter() -> Trading212Adapter:
    """Create a Trading212Adapter with a dummy API key."""
    return Trading212Adapter(api_key="test-key-abc123", base_url="https://demo.trading212.com/api/v0")


def _make_order_request(ticker: str = "AAPL", side: str = "BUY", qty: str = "5") -> OrderRequest:
    return OrderRequest(ticker=ticker, side=side, quantity=Decimal(qty))


def _make_httpx_response(status_code: int, json_data: dict | list) -> MagicMock:
    """Create a mock httpx.Response with the given status code and JSON body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    resp.text = str(json_data)
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("httpx.AsyncClient.request")
async def test_place_order_success(mock_request):
    """Successful order placement should return OrderStatus with FILLED status."""
    mock_request.return_value = _make_httpx_response(
        200,
        {
            "id": "order-123",
            "status": "FILLED",
            "filledQuantity": 5.0,
            "filledPrice": 152.50,
        },
    )

    adapter = _make_adapter()
    order = _make_order_request()
    result = await adapter.place_order(order)

    assert result.status == "FILLED"
    assert result.broker_order_id == "order-123"
    assert result.ticker == "AAPL"
    assert result.filled_quantity == Decimal("5.0")


@patch("httpx.AsyncClient.request")
async def test_rate_limiting_retry(mock_request):
    """429 response should trigger a retry and eventually succeed."""
    rate_limit_resp = _make_httpx_response(200, {})  # placeholder
    rate_limit_resp.status_code = 429
    rate_limit_resp.headers = {"Retry-After": "0.01"}  # tiny delay for tests

    success_resp = _make_httpx_response(
        200,
        {
            "id": "order-456",
            "status": "FILLED",
            "filledQuantity": 3.0,
            "filledPrice": 150.00,
        },
    )

    mock_request.side_effect = [rate_limit_resp, success_resp]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        adapter = _make_adapter()
        order = _make_order_request("MSFT", qty="3")
        result = await adapter.place_order(order)

    assert result.status == "FILLED"
    assert result.broker_order_id == "order-456"


@patch("httpx.AsyncClient.request")
async def test_5xx_retry(mock_request):
    """500 response should trigger a retry; second attempt succeeds."""
    server_error_resp = _make_httpx_response(500, {"error": "Internal server error"})
    success_resp = _make_httpx_response(
        200,
        {
            "id": "order-789",
            "status": "FILLED",
            "filledQuantity": 10.0,
            "filledPrice": 200.00,
        },
    )

    mock_request.side_effect = [server_error_resp, success_resp]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        adapter = _make_adapter()
        order = _make_order_request("GOOGL", qty="10")
        result = await adapter.place_order(order)

    assert result.status == "FILLED"
    assert result.broker_order_id == "order-789"


@patch("httpx.AsyncClient.request")
async def test_4xx_no_retry(mock_request):
    """400 response should raise BrokerError immediately without retry."""
    bad_request_resp = _make_httpx_response(400, {"error": "Invalid ticker"})
    mock_request.return_value = bad_request_resp

    adapter = _make_adapter()
    order = _make_order_request("INVALID")

    with pytest.raises(BrokerError):
        await adapter.place_order(order)

    # Should only have been called once — no retries on 4xx
    assert mock_request.call_count == 1


@patch("httpx.AsyncClient.request")
async def test_get_positions(mock_request):
    """get_positions should parse the T212 portfolio list into BrokerPosition objects."""
    mock_request.return_value = _make_httpx_response(
        200,
        [
            {
                "ticker": "AAPL",
                "quantity": 10.0,
                "averagePrice": 145.00,
                "currentPrice": 152.50,
                "ppl": 75.00,
            },
            {
                "ticker": "MSFT",
                "quantity": 5.0,
                "averagePrice": 300.00,
                "currentPrice": 310.00,
                "ppl": 50.00,
            },
        ],
    )

    adapter = _make_adapter()
    positions = await adapter.get_positions()

    assert len(positions) == 2
    aapl = next(p for p in positions if p.ticker == "AAPL")
    assert aapl.quantity == Decimal("10.0")
    assert aapl.avg_price == Decimal("145.00")
    assert aapl.current_price == Decimal("152.50")
    assert aapl.unrealized_pnl == Decimal("75.00")


def test_status_mapping():
    """_map_status should correctly translate T212 statuses to our internal statuses."""
    assert Trading212Adapter._map_status("FILLED") == "FILLED"
    assert Trading212Adapter._map_status("NEW") == "PENDING"
    assert Trading212Adapter._map_status("PENDING") == "PENDING"
    assert Trading212Adapter._map_status("CONFIRMED") == "PENDING"
    assert Trading212Adapter._map_status("REJECTED") == "FAILED"
    assert Trading212Adapter._map_status("CANCELLED") == "CANCELLED"
    assert Trading212Adapter._map_status("CANCELLING") == "CANCELLED"
    # Unknown status defaults to PENDING
    assert Trading212Adapter._map_status("UNKNOWN_STATUS") == "PENDING"


@patch("httpx.AsyncClient.request")
async def test_get_positions_empty(mock_request):
    """get_positions with an empty list should return an empty list."""
    mock_request.return_value = _make_httpx_response(200, [])

    adapter = _make_adapter()
    positions = await adapter.get_positions()

    assert positions == []


@patch("httpx.AsyncClient.request")
async def test_5xx_exhausted_raises(mock_request):
    """Exhausting all retries on 5xx should raise BrokerError."""
    server_error = _make_httpx_response(500, {"error": "Server error"})
    mock_request.return_value = server_error

    with patch("asyncio.sleep", new_callable=AsyncMock):
        adapter = _make_adapter()
        order = _make_order_request()
        with pytest.raises(BrokerError):
            await adapter.place_order(order)


@patch("httpx.AsyncClient.request")
async def test_place_order_pending_polls(mock_request):
    """When order status is PENDING, adapter should poll for final status."""
    # First call: order placed → PENDING (maps from NEW)
    place_resp = _make_httpx_response(
        200,
        {"id": "order-pending-001", "status": "NEW", "filledQuantity": 0, "filledPrice": 0},
    )
    # Poll call: GET /equity/orders/order-pending-001 → FILLED
    poll_resp = _make_httpx_response(
        200,
        {
            "id": "order-pending-001",
            "status": "FILLED",
            "ticker": "AAPL",
            "side": "BUY",
            "filledQuantity": 5.0,
            "filledPrice": 152.00,
        },
    )
    mock_request.side_effect = [place_resp, poll_resp]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        adapter = _make_adapter()
        order = _make_order_request()
        result = await adapter.place_order(order)

    assert result.status == "FILLED"
