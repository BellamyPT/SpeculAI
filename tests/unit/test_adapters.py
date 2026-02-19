"""Tests for adapter ABCs, DTOs, and yfinance adapter validation logic."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from tradeagent.adapters.base import (
    BrokerAdapter,
    BrokerInstrument,
    BrokerPosition,
    FundamentalSnapshot,
    LLMAdapter,
    LLMResponse,
    MarketDataAdapter,
    NewsAdapter,
    NewsItem,
    OrderRequest,
    OrderStatus,
    PriceBar,
    ValidationResult,
)
from tradeagent.adapters.market_data.yfinance_adapter import (
    YFinanceAdapter,
    _is_valid_price,
    _safe_decimal,
)


# ── DTO construction tests ───────────────────────────────────────────


class TestPriceBar:
    def test_create(self):
        bar = PriceBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("153.50"),
            adj_close=Decimal("153.50"),
            volume=50_000_000,
        )
        assert bar.ticker == "AAPL"
        assert bar.date == date(2024, 1, 15)
        assert bar.close == Decimal("153.50")
        assert bar.volume == 50_000_000

    def test_frozen(self):
        bar = PriceBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150"),
            high=Decimal("155"),
            low=Decimal("149"),
            close=Decimal("153"),
            adj_close=Decimal("153"),
            volume=100,
        )
        with pytest.raises(AttributeError):
            bar.ticker = "MSFT"  # type: ignore[misc]


class TestFundamentalSnapshot:
    def test_create_minimal(self):
        snap = FundamentalSnapshot(
            ticker="AAPL",
            snapshot_date=date(2024, 1, 15),
        )
        assert snap.ticker == "AAPL"
        assert snap.name is None
        assert snap.market_cap is None

    def test_create_full(self):
        snap = FundamentalSnapshot(
            ticker="AAPL",
            snapshot_date=date(2024, 1, 15),
            name="Apple Inc.",
            exchange="NASDAQ",
            currency="USD",
            sector="Technology",
            industry="Consumer Electronics",
            country="US",
            market_cap=Decimal("3000000000000"),
            pe_ratio=Decimal("28.5"),
            beta=Decimal("1.2"),
        )
        assert snap.name == "Apple Inc."
        assert snap.market_cap == Decimal("3000000000000")


class TestValidationResult:
    def test_default_values(self):
        vr = ValidationResult(ticker="AAPL")
        assert vr.valid_bars == []
        assert vr.rejected_count == 0
        assert vr.rejection_reasons == []
        assert vr.missing_dates == []

    def test_mutable(self):
        vr = ValidationResult(ticker="AAPL")
        bar = PriceBar(
            ticker="AAPL",
            date=date(2024, 1, 15),
            open=Decimal("150"),
            high=Decimal("155"),
            low=Decimal("149"),
            close=Decimal("153"),
            adj_close=Decimal("153"),
            volume=100,
        )
        vr.valid_bars.append(bar)
        vr.rejected_count += 1
        assert len(vr.valid_bars) == 1
        assert vr.rejected_count == 1


class TestLLMResponse:
    def test_create(self):
        resp = LLMResponse(
            raw_text="some text",
            parsed={"action": "BUY"},
            token_count=500,
            response_time_seconds=2.5,
            parse_success=True,
        )
        assert resp.parse_success is True
        assert resp.parsed == {"action": "BUY"}


class TestNewsItem:
    def test_create(self):
        item = NewsItem(
            source="reuters",
            headline="Market rally",
            summary="Stocks went up",
            published_at=datetime(2024, 1, 15, 10, 30),
            url="https://example.com/news/1",
            relevance_score=0.85,
        )
        assert item.source == "reuters"
        assert item.relevance_score == 0.85

    def test_optional_relevance(self):
        item = NewsItem(
            source="reuters",
            headline="Test",
            summary="Test",
            published_at=None,
            url="https://example.com",
        )
        assert item.relevance_score is None


class TestOrderRequest:
    def test_defaults(self):
        order = OrderRequest(
            ticker="AAPL",
            side="BUY",
            quantity=Decimal("10"),
        )
        assert order.order_type == "MARKET"
        assert order.limit_price is None

    def test_limit_order(self):
        order = OrderRequest(
            ticker="AAPL",
            side="BUY",
            quantity=Decimal("10"),
            order_type="LIMIT",
            limit_price=Decimal("150.00"),
        )
        assert order.order_type == "LIMIT"
        assert order.limit_price == Decimal("150.00")


class TestOrderStatus:
    def test_create(self):
        status = OrderStatus(
            broker_order_id="ORD-123",
            ticker="AAPL",
            side="BUY",
            status="FILLED",
            filled_quantity=Decimal("10"),
            filled_price=Decimal("150.00"),
            filled_at=datetime(2024, 1, 15, 14, 30),
        )
        assert status.status == "FILLED"
        assert status.error_message is None


class TestBrokerPosition:
    def test_create(self):
        pos = BrokerPosition(
            ticker="AAPL",
            quantity=Decimal("50"),
            avg_price=Decimal("145.00"),
            current_price=Decimal("155.00"),
            unrealized_pnl=Decimal("500.00"),
        )
        assert pos.unrealized_pnl == Decimal("500.00")


class TestBrokerInstrument:
    def test_create(self):
        inst = BrokerInstrument(
            ticker="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            currency="USD",
        )
        assert inst.isin is None
        assert inst.min_quantity is None


# ── ABC contract tests ───────────────────────────────────────────────


class TestMarketDataAdapterABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            MarketDataAdapter()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        """A concrete subclass implementing all methods can be instantiated."""

        class Dummy(MarketDataAdapter):
            async def fetch_prices(self, tickers, start, end, *, batch_size=100):
                return {}

            async def fetch_fundamentals(self, tickers):
                return {}

        adapter = Dummy()
        assert isinstance(adapter, MarketDataAdapter)


class TestLLMAdapterABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMAdapter()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        class Dummy(LLMAdapter):
            async def analyze(self, analysis_package, *, system_prompt=None):
                return LLMResponse("", {}, 0, 0.0, False)

        assert isinstance(Dummy(), LLMAdapter)


class TestNewsAdapterABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            NewsAdapter()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        class Dummy(NewsAdapter):
            async def query_news(self, topics, *, max_results_per_topic=5):
                return []

        assert isinstance(Dummy(), NewsAdapter)


class TestBrokerAdapterABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BrokerAdapter()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        class Dummy(BrokerAdapter):
            async def place_order(self, order):
                return OrderStatus("", "", "", "")

            async def get_order_status(self, broker_order_id):
                return OrderStatus("", "", "", "")

            async def get_positions(self):
                return []

            async def get_instruments(self, *, search=None):
                return []

        assert isinstance(Dummy(), BrokerAdapter)


# ── Validation helper tests ──────────────────────────────────────────


class TestSafeDecimal:
    def test_valid_int(self):
        assert _safe_decimal(42) == Decimal("42")

    def test_valid_float(self):
        assert _safe_decimal(3.14) == Decimal("3.14")

    def test_valid_string(self):
        assert _safe_decimal("100.5") == Decimal("100.5")

    def test_none_returns_none(self):
        assert _safe_decimal(None) is None

    def test_nan_returns_none(self):
        assert _safe_decimal(float("nan")) is None

    def test_inf_returns_none(self):
        assert _safe_decimal(float("inf")) is None

    def test_invalid_string(self):
        assert _safe_decimal("not-a-number") is None


class TestIsValidPrice:
    def test_positive(self):
        assert _is_valid_price(100.0) is True

    def test_zero(self):
        assert _is_valid_price(0) is False

    def test_negative(self):
        assert _is_valid_price(-5.0) is False

    def test_nan(self):
        assert _is_valid_price(float("nan")) is False

    def test_inf(self):
        assert _is_valid_price(float("inf")) is False

    def test_none(self):
        assert _is_valid_price(None) is False

    def test_string(self):
        assert _is_valid_price("abc") is False


# ── YFinanceAdapter validation logic tests ───────────────────────────


class TestYFinanceAdapterValidation:
    def test_validate_valid_row(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 150.0,
            "High": 155.0,
            "Low": 149.0,
            "Close": 153.0,
            "Volume": 50_000_000,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, PriceBar)
        assert result.ticker == "AAPL"
        assert result.close == Decimal(str(153.0))

    def test_validate_zero_price_rejected(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 0.0,
            "High": 155.0,
            "Low": 149.0,
            "Close": 153.0,
            "Volume": 100,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, str)
        assert "invalid Open" in result

    def test_validate_nan_price_rejected(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 150.0,
            "High": float("nan"),
            "Low": 149.0,
            "Close": 153.0,
            "Volume": 100,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, str)
        assert "invalid High" in result

    def test_validate_negative_price_rejected(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 150.0,
            "High": 155.0,
            "Low": -1.0,
            "Close": 153.0,
            "Volume": 100,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, str)
        assert "invalid Low" in result

    def test_validate_zero_volume_allowed(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 150.0,
            "High": 155.0,
            "Low": 149.0,
            "Close": 153.0,
            "Volume": 0,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, PriceBar)
        assert result.volume == 0

    def test_validate_none_volume_defaults_to_zero(self):
        row = MagicMock()
        row.get = lambda k: {
            "Open": 150.0,
            "High": 155.0,
            "Low": 149.0,
            "Close": 153.0,
            "Volume": None,
        }.get(k)

        result = YFinanceAdapter._validate_price_row(
            "AAPL", date(2024, 1, 15), row
        )
        assert isinstance(result, PriceBar)
        assert result.volume == 0


class TestYFinanceAdapterFetchPrices:
    async def test_empty_tickers_returns_empty(self):
        adapter = YFinanceAdapter()
        result = await adapter.fetch_prices([], date(2024, 1, 1), date(2024, 1, 31))
        assert result == {}

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.download")
    async def test_single_ticker_download(self, mock_download):
        """Mock yf.download for a single ticker and verify parsing."""
        import pandas as pd

        # Build a DataFrame mimicking single-ticker yf.download output
        index = pd.DatetimeIndex([pd.Timestamp("2024-01-15")])
        data = {
            "Open": [150.0],
            "High": [155.0],
            "Low": [149.0],
            "Close": [153.0],
            "Volume": [50_000_000],
        }
        mock_download.return_value = pd.DataFrame(data, index=index)

        adapter = YFinanceAdapter()
        results = await adapter.fetch_prices(
            ["AAPL"], date(2024, 1, 1), date(2024, 1, 31)
        )

        assert "AAPL" in results
        vr = results["AAPL"]
        assert len(vr.valid_bars) == 1
        assert vr.valid_bars[0].close == Decimal(str(153.0))
        assert vr.rejected_count == 0

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.download")
    async def test_download_exception_raises(self, mock_download):
        """yf.download failure propagates as DataIngestionError."""
        from tradeagent.core.exceptions import DataIngestionError

        mock_download.side_effect = Exception("network error")

        adapter = YFinanceAdapter()
        with pytest.raises(DataIngestionError, match="network error"):
            await adapter.fetch_prices(
                ["AAPL"], date(2024, 1, 1), date(2024, 1, 31)
            )

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.download")
    async def test_empty_dataframe_returns_empty_results(self, mock_download):
        """Empty DataFrame returns ValidationResult with no valid bars."""
        import pandas as pd

        mock_download.return_value = pd.DataFrame()

        adapter = YFinanceAdapter()
        results = await adapter.fetch_prices(
            ["AAPL"], date(2024, 1, 1), date(2024, 1, 31)
        )

        assert "AAPL" in results
        assert len(results["AAPL"].valid_bars) == 0


class TestYFinanceAdapterFetchFundamentals:
    async def test_empty_tickers_returns_empty(self):
        adapter = YFinanceAdapter()
        result = await adapter.fetch_fundamentals([])
        assert result == {}

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.Ticker")
    async def test_single_ticker_fundamentals(self, mock_ticker_class):
        """Mock yf.Ticker().info and verify FundamentalSnapshot mapping."""
        mock_info = {
            "regularMarketPrice": 153.0,
            "shortName": "Apple Inc.",
            "exchange": "NMS",
            "currency": "USD",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 28.5,
            "beta": 1.2,
        }
        mock_ticker_class.return_value.info = mock_info

        adapter = YFinanceAdapter()
        results = await adapter.fetch_fundamentals(["AAPL"])

        assert "AAPL" in results
        snap = results["AAPL"]
        assert snap.name == "Apple Inc."
        assert snap.sector == "Technology"
        assert snap.market_cap == Decimal("3000000000000")
        assert snap.pe_ratio == Decimal("28.5")
        assert snap.beta == Decimal("1.2")

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.Ticker")
    async def test_ticker_with_no_data_skipped(self, mock_ticker_class):
        """Ticker with no regularMarketPrice is skipped."""
        mock_ticker_class.return_value.info = {}

        adapter = YFinanceAdapter()
        results = await adapter.fetch_fundamentals(["INVALID"])
        assert "INVALID" not in results

    @patch("tradeagent.adapters.market_data.yfinance_adapter.yf.Ticker")
    async def test_ticker_exception_skipped(self, mock_ticker_class):
        """If yf.Ticker().info raises, the ticker is skipped."""
        mock_ticker_class.return_value.info = property(
            lambda self: (_ for _ in ()).throw(Exception("API error"))
        )
        # Simpler: make .info access raise
        type(mock_ticker_class.return_value).info = property(
            lambda self: (_ for _ in ()).throw(Exception("API error"))
        )

        adapter = YFinanceAdapter()
        results = await adapter.fetch_fundamentals(["BAD"])
        assert "BAD" not in results


# ── Import tests ─────────────────────────────────────────────────────


class TestAdapterImports:
    def test_import_from_adapters_package(self):
        """All DTOs and ABCs are importable from the adapters package."""
        from tradeagent.adapters import (
            BrokerAdapter,
            BrokerInstrument,
            BrokerPosition,
            FundamentalSnapshot,
            LLMAdapter,
            LLMResponse,
            MarketDataAdapter,
            NewsAdapter,
            NewsItem,
            OrderRequest,
            OrderStatus,
            PriceBar,
            ValidationResult,
        )

        # Just verify they're the right types
        assert PriceBar is not None
        assert MarketDataAdapter is not None

    def test_import_yfinance_adapter(self):
        """YFinanceAdapter is importable from the market_data sub-package."""
        from tradeagent.adapters.market_data import YFinanceAdapter

        adapter = YFinanceAdapter()
        assert isinstance(adapter, MarketDataAdapter)
