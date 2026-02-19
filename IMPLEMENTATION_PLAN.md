# SpeculAI / TradeAgent - Implementation Plan

This document breaks the PRD into small, independently testable feature branches. Each branch results in a working increment that can be reviewed, tested, and merged via Pull Request.

**Branching convention:** `feature/<number>-<short-name>` off `main`
**Merge strategy:** Each feature branch merges into `main` sequentially

---

## Feature 1: Project Scaffolding & Configuration System

**Branch:** `feature/01-project-scaffolding`
**Estimated effort:** ~4 hours

### Scope
- Create Python project structure with `pyproject.toml` (Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic Settings, pandas-ta, httpx, APScheduler, structlog, pytest)
- Create directory tree matching PRD structure (`src/tradeagent/`, `tests/`, `scripts/`, `config/`, `alembic/`, `frontend/`)
- Implement `config.py` using Pydantic Settings: load from `config/config.yaml` + environment variables
- Create `config/config.example.yaml` with all documented defaults (screening weights, max positions, schedule, etc.)
- Create `.env.example` with all required/optional env vars
- Set up structured JSON logging with `structlog` (`core/logging.py`)
- Create `core/types.py` with shared enums (`Action`, `Side`, `TradeStatus`, `PipelineStatus`)
- Create `core/exceptions.py` with custom exception hierarchy
- Add `.gitignore` for Python, Node, `.env`, `__pycache__`, etc.

### How to Test
- `pip install -e .` succeeds
- `python -c "from tradeagent.config import Settings; s = Settings(); print(s)"` loads defaults from config.yaml
- Logging outputs structured JSON to stdout
- All enums and exceptions are importable
- `pytest` runs (even if 0 tests)

### PR Description
Sets up the complete Python project skeleton, configuration system (Pydantic Settings from YAML + env vars), structured logging, shared types, and exception hierarchy. No runtime behavior yet - this is the foundation all other features build on.

---

## Feature 2: Database Models & Migrations

**Branch:** `feature/02-database-models`
**Estimated effort:** ~5 hours

### Scope
- Create SQLAlchemy 2.0 models in `models/`:
  - `base.py` - Base class with `id`, `created_at`, `updated_at` mixins
  - `stock.py` - `Stock`, `StockPrice`, `StockFundamental`
  - `portfolio.py` - `Position`, `PortfolioSnapshot`, `PositionSnapshot`
  - `trade.py` - `Trade` (with `is_backtest`, `backtest_run_id`)
  - `decision.py` - `DecisionReport`, `DecisionContextItem`
  - `benchmark.py` - `Benchmark`, `BenchmarkPrice`
- Configure Alembic with auto-generation from models
- Create initial migration
- Add all indexes and constraints from PRD (unique constraints, partial indexes)
- Create Pydantic schemas in `schemas/` for API request/response models

### How to Test
- `alembic upgrade head` applies migration to a local PostgreSQL (or test container)
- `alembic downgrade base` cleanly reverts
- Models can be instantiated and relationships work
- `pytest` with a test that creates/queries each model against a test DB

### PR Description
Implements all 11 database entities from the PRD (Stock, StockPrice, StockFundamental, Position, PortfolioSnapshot, PositionSnapshot, Trade, DecisionReport, DecisionContextItem, Benchmark, BenchmarkPrice) with SQLAlchemy 2.0, Alembic migrations, indexes, constraints, and Pydantic response schemas.

---

## Feature 3: Docker Compose & Health Check

**Branch:** `feature/03-docker-health`
**Estimated effort:** ~3 hours

### Scope
- Create `docker-compose.yml` with 3 services: `db` (postgres:16-alpine), `backend`, `frontend` (placeholder)
- Create `Dockerfile` for backend (Python 3.12-slim)
- Implement `main.py` - FastAPI app entry point with lifespan, CORS middleware
- Implement `GET /api/health` endpoint returning `{status, database, last_pipeline_run, last_pipeline_status}`
- Backend startup runs: `alembic upgrade head` then `uvicorn`
- PostgreSQL healthcheck via `pg_isready`

### How to Test
- `docker compose up` starts PostgreSQL + backend
- `curl http://localhost:8000/api/health` returns `{"status": "ok", "database": "connected", ...}`
- Migrations auto-apply on startup
- `docker compose down -v` cleanly shuts down

### PR Description
Adds Docker Compose setup with PostgreSQL 16 and Python backend, FastAPI application entry point with CORS, and a health check endpoint. Running `docker compose up` gives you a working API at localhost:8000 with auto-applied database migrations.

---

## Feature 4: Repository Layer

**Branch:** `feature/04-repositories`
**Estimated effort:** ~4 hours

### Scope
- Create `api/dependencies.py` with database session dependency (async SQLAlchemy session)
- Implement repository classes in `repositories/`:
  - `stock.py` - CRUD for stocks, prices, fundamentals; bulk upsert for daily prices
  - `portfolio.py` - Position management, portfolio snapshots, position snapshots
  - `trade.py` - Trade creation, status updates, history queries with filtering
  - `decision.py` - Decision report CRUD, memory retrieval queries (by ticker, sector, similar signals)
  - `benchmark.py` - Benchmark CRUD, price history
- Each repository uses async SQLAlchemy sessions
- All paginated queries support `limit`, `offset`

### How to Test
- Unit tests for each repository method against a test database
- Test bulk upsert of stock prices (insert + update on conflict)
- Test decision memory queries return correct results for ticker match, sector match, and signal similarity
- Test pagination returns correct page sizes

### PR Description
Implements the full data access layer with async SQLAlchemy repositories for all entities. Includes bulk upsert for market data, paginated queries for trade/decision history, and the memory retrieval queries (by ticker, sector, similar signal) that power the agent's learning system.

---

## Feature 5: Adapter Interfaces & Market Data Adapter

**Branch:** `feature/05-adapters-market-data`
**Estimated effort:** ~5 hours

### Scope
- Create abstract base classes in `adapters/`:
  - `adapters/base.py` - Common adapter interface
  - `adapters/llm/base.py` - `LLMAdapter` ABC (`analyze(analysis_package) -> LLMResponse`)
  - `adapters/market_data/base.py` - `MarketDataAdapter` ABC (`fetch_prices`, `fetch_fundamentals`)
  - `adapters/news/base.py` - `NewsAdapter` ABC (`query_news(topics) -> list[NewsItem]`)
  - `adapters/broker/base.py` - `BrokerAdapter` ABC (`place_order`, `get_order_status`, `get_positions`, `get_instruments`)
- Implement `adapters/market_data/yfinance_adapter.py`:
  - `fetch_daily_prices(tickers, start, end)` - OHLCV data via yfinance
  - `fetch_fundamentals(tickers)` - P/E, market cap, etc.
  - Data validation: reject zero/negative prices, flag missing dates, allow zero volume
  - Rate-limiting / batching for ~1000 tickers
- Create seed scripts:
  - `scripts/seed_watchlist.py` - Populate stock watchlist from S&P 500 + STOXX 600 + emerging market large-caps
  - `scripts/seed_benchmarks.py` - Fetch 3 years of benchmark data (^GSPC, IWDA.AS, VWCE.DE)

### How to Test
- `python scripts/seed_watchlist.py --skip-existing` populates the stock table with ~800-1200 stocks
- `python scripts/seed_benchmarks.py --skip-existing` fetches benchmark history
- Unit tests with mocked yfinance: verify data validation rejects bad data, handles missing dates
- Integration test: fetch 5 real tickers from yfinance, verify data stored correctly

### PR Description
Defines the abstract adapter interfaces (LLM, MarketData, News, Broker) that make all external integrations swappable. Implements the yfinance market data adapter with data validation and rate-limiting, plus seed scripts to populate the stock watchlist (~1000 global equities) and benchmark history (S&P 500, IWDA, VWCE).

---

## Feature 6: Technical Analysis Engine

**Branch:** `feature/06-technical-analysis`
**Estimated effort:** ~4 hours

### Scope
- Implement `services/technical_analysis.py`:
  - Compute RSI(14), MACD(12,26,9), Bollinger Bands(20,2), SMA(50), SMA(200), EMA(12), EMA(26), Volume SMA(20)
  - Uses `pandas-ta` library on stock price DataFrames
  - Returns structured indicator dict per stock
  - Handles edge cases: insufficient history (compute what's possible, mark missing as null)
- Implement `services/screening.py`:
  - Score stocks based on configurable weights from config: RSI (0.25), MACD (0.20), Bollinger (0.15), SMA cross (0.15), Volume (0.10), P/E (0.15)
  - Filter: min market cap, sufficient price history
  - Always include stocks currently in portfolio (for SELL/HOLD analysis)
  - Return top N candidates (configurable, default 50)

### How to Test
- Unit test: compute indicators on known price data, verify RSI/MACD/Bollinger values match expected
- Unit test: screening with sample data scores stocks correctly, respects max_candidates limit
- Unit test: stocks in portfolio always included regardless of score
- Unit test: stocks with insufficient history excluded, recent IPOs get partial scores
- `pytest` all green

### PR Description
Implements the technical analysis engine (RSI, MACD, Bollinger Bands, SMA/EMA, Volume) using pandas-ta, and the stock screening service that scores and ranks ~1000 stocks down to ~50 actionable candidates using configurable weighted signals. Portfolio holdings are always included for SELL/HOLD analysis.

---

## Feature 7: News Adapter (Perplexity)

**Branch:** `feature/07-news-adapter`
**Estimated effort:** ~3 hours

### Scope
- Implement `adapters/news/perplexity_adapter.py`:
  - Query Perplexity API (sonar model) for sector-level and stock-specific news
  - Parse response into structured `NewsItem` objects (headline, summary, sentiment, source, citations)
  - Retry with exponential backoff (2s, 4s) on failure
  - Fallback: return empty list with warning if all retries fail
- Rate limiting and error handling per Perplexity API docs

### How to Test
- Unit test with mocked HTTP responses: verify parsing, retry logic, fallback behavior
- Integration test (optional, requires API key): query real Perplexity API for "AAPL stock news"
- Test graceful degradation: adapter returns empty list + logs warning when API is down

### PR Description
Implements the Perplexity API news adapter (sonar model) for gathering financial news context. Includes structured parsing into NewsItem objects with sentiment, retry logic with exponential backoff, and graceful degradation (pipeline continues without news if API fails).

---

## Feature 8: LLM Adapter (Claude CLI)

**Branch:** `feature/08-llm-adapter`
**Estimated effort:** ~4 hours

### Scope
- Implement `adapters/llm/claude_cli.py`:
  - Invoke Claude Code CLI via subprocess: `echo "<prompt>" | claude --print --output-format text`
  - Parse JSON from response (extract between first `{` and last `}`)
  - Retry on parse failure with reinforcement prompt (up to 3 attempts)
  - Handle: timeout (120s configurable), non-zero exit, empty stdout, CLI not found
- Create prompt templates in `adapters/llm/prompts/`:
  - `system_prompt.md` - Main analysis prompt with response schema
  - `report_prompt.md` - Report generation prompt
- Implement analysis package builder: assemble prompt from portfolio state, candidates with indicators, news context, memory items

### How to Test
- Unit test with mocked subprocess: verify prompt assembly, JSON extraction, retry logic
- Test timeout handling, non-zero exit code, empty response
- Test JSON extraction from messy output (text before/after JSON)
- Test analysis package builder produces well-structured prompt within token limits
- Integration test (optional, requires Claude CLI): send small analysis package, verify JSON response

### PR Description
Implements the Claude Code CLI adapter for LLM-powered trade analysis via subprocess. Includes prompt templates, analysis package builder (assembles portfolio + candidates + news + memory into a structured prompt), JSON response parsing with retries, and comprehensive error handling (timeouts, parse failures, CLI issues).

---

## Feature 9: Risk Manager

**Branch:** `feature/09-risk-manager`
**Estimated effort:** ~3 hours

### Scope
- Implement `services/risk_manager.py`:
  - Validate trades against portfolio constraints:
    - Max positions (default 20)
    - Max per-position allocation (default 5% of portfolio)
    - Minimum trade value ($100)
    - Available cash check
  - Process SELL orders first (to free cash + position slots)
  - Prioritize BUY orders by confidence (highest first)
  - Return approved + rejected lists with rejection reasons
  - Currency conversion via yfinance rates for non-base-currency stocks
  - Never throws - always returns a result

### How to Test
- Unit test: BUY exceeding max_position_pct gets rejected
- Unit test: BUY when at max_positions gets rejected
- Unit test: SELLs processed before BUYs, freeing cash for subsequent BUYs
- Unit test: Multiple BUYs ordered by confidence
- Unit test: BUY quantity adjusted down to fit within available cash
- Unit test: Min trade value check ($100)
- All edge cases: 100% invested with no cash, portfolio empty, etc.

### PR Description
Implements the risk manager that enforces portfolio constraints before trade execution. Validates max positions, per-position allocation limits, minimum trade value, and available cash. Processes SELLs before BUYs, prioritizes by confidence, and provides detailed rejection reasons. Designed to never throw - always returns approved and rejected trade lists.

---

## Feature 10: Memory & Learning Service

**Branch:** `feature/10-memory-service`
**Estimated effort:** ~3 hours

### Scope
- Implement `services/memory.py`:
  - Retrieve relevant past decisions for a given stock candidate:
    1. Exact ticker match (max 10, most recent first)
    2. Same sector match (max 5, sorted by outcome)
    3. Similar technical signal match (RSI range, MACD direction via JSONB comparison)
  - Total memory per candidate: max 10 items
  - Format memory items for LLM prompt: ticker, action, confidence, reasoning snippet (200 chars), outcome, date
- Implement outcome assessment logic:
  - For decision reports >7 days old, compute current P&L
  - For closed positions, compute final P&L and mark assessed
  - Run as daily job after pipeline

### How to Test
- Unit test: ticker match returns correct decisions ordered by recency
- Unit test: sector match returns relevant cross-stock decisions
- Unit test: similar signal match finds decisions with comparable RSI ranges
- Unit test: total capped at 10 per candidate
- Unit test: fresh system with no history returns empty memory gracefully
- Unit test: outcome assessment correctly computes P&L for open and closed positions

### PR Description
Implements the memory and learning system that retrieves relevant past decisions when analyzing stocks. Uses SQL-based retrieval by ticker, sector, and similar technical signals (no vector search for MVP). Includes outcome assessment that retroactively evaluates past decisions against actual market outcomes for continuous learning.

---

## Feature 11: Daily Pipeline Orchestrator

**Branch:** `feature/11-pipeline-orchestrator`
**Estimated effort:** ~5 hours

### Scope
- Implement `services/pipeline.py` - Orchestrates the full daily pipeline:
  1. Fetch market data (prices + fundamentals)
  2. Compute technical indicators
  3. Screen and score stocks → top 50 candidates
  4. Query news for sectors + top candidates
  5. Retrieve memory for each candidate
  6. Build analysis package
  7. Send to LLM, parse response
  8. Risk-validate recommendations
  9. (Trade execution delegated to Feature 12)
  10. Generate decision reports
  11. Persist reports to memory
  - Error handling per PRD: abort on data failure, continue without news if news fails, retry LLM 3x, sanity checks on LLM output
  - Track pipeline_run_id (UUID) for each run
- Implement `services/report_generator.py` - Create decision reports with full context
- Implement `scheduler.py` - APScheduler trigger at configurable time (default 07:00 UTC)
- Implement `POST /api/pipeline/run` (manual trigger, 409 if already running)
- Implement `GET /api/pipeline/status`

### How to Test
- Integration test with mocked adapters: run full pipeline, verify all steps execute in order
- Test error handling: data failure aborts, news failure continues, LLM failure retries then aborts
- Test sanity checks: >5 buys/day or >50% portfolio sell flags anomaly
- Test pipeline status: only one run at a time (409 on concurrent)
- Test manual trigger via API endpoint
- Test scheduler fires at configured time

### PR Description
Implements the daily pipeline orchestrator that chains all services together: market data fetch → technical analysis → stock screening → news gathering → memory retrieval → LLM analysis → risk validation → report generation → memory persistence. Includes APScheduler for automated daily runs, manual trigger API endpoint, pipeline status tracking, and comprehensive error handling with abort/continue logic per step.

---

## Feature 12: Trading 212 Broker Adapter & Trade Execution

**Branch:** `feature/12-broker-trade-execution`
**Estimated effort:** ~5 hours

### Scope
- Implement `adapters/broker/trading212.py`:
  - Auth: API key in Authorization header
  - `GET /api/v0/equity/metadata/instruments` - Fetch instrument list, build yfinance↔T212 ticker mapping
  - `POST /api/v0/equity/orders` - Place market orders (quantity for BUY, negative for SELL)
  - `GET /api/v0/equity/orders/{id}` - Poll order status (5 polls, 10s apart)
  - `GET /api/v0/equity/portfolio` - Current positions
  - Rate limit handling: respect `x-ratelimit-remaining` / `x-ratelimit-reset`
  - Retry on 5xx (2x exponential backoff), no retry on 4xx
  - Base URL: `https://demo.trading212.com/api/v0` (practice)
- Wire trade execution into pipeline (step 9):
  - Execute approved trades via broker adapter
  - Log trade results, update positions
  - Handle partial fills, maintenance windows
- Implement `POST /api/pipeline/run` now triggers full pipeline including execution

### How to Test
- Unit test with mocked HTTP: verify order placement, status polling, rate limit handling
- Unit test: ticker mapping from yfinance to T212 format
- Unit test: partial fill handling, maintenance retry
- Integration test (requires T212 practice API key): place and poll a small order
- Pipeline integration test with MockBrokerAdapter: full pipeline end-to-end with simulated fills

### PR Description
Implements the Trading 212 Practice API broker adapter with instrument mapping, market order placement, status polling, rate limiting, and retry logic. Wires trade execution into the daily pipeline so approved recommendations are automatically executed. Handles partial fills, maintenance windows, and yfinance-to-T212 ticker mapping.

---

## Feature 13: Portfolio API Endpoints

**Branch:** `feature/13-portfolio-api`
**Estimated effort:** ~4 hours

### Scope
- Implement `api/routes/portfolio.py`:
  - `GET /api/portfolio/summary` - Total value, cash, invested, daily P&L, cumulative %, positions array
  - `GET /api/portfolio/performance` - Time series with benchmark overlays, indexed to 100 at start
  - Query params: start_date, end_date, benchmarks (comma-separated)
- Implement `api/routes/trades.py`:
  - `GET /api/trades` - Paginated trade history with filters (ticker, side, date range, include_backtest)
- Implement `api/routes/decisions.py`:
  - `GET /api/decisions` - Paginated decision list with filters (ticker, action, min_confidence, date range)
  - `GET /api/decisions/{id}` - Full decision detail with context items
- Implement `services/portfolio_snapshot.py` - Daily portfolio valuation snapshot job
- Standard error responses, Pydantic validation on all query params

### How to Test
- API tests: each endpoint returns correct shape with test data
- Test filtering: ticker filter, date range, side filter all work correctly
- Test pagination: limit/offset produce correct pages
- Test performance endpoint: series indexed to 100, benchmarks included
- Test 404 for non-existent decision ID
- Test invalid query params return 400

### PR Description
Implements all REST API endpoints for portfolio data: summary with positions and P&L, performance time series with benchmark comparisons (S&P 500, IWDA, VWCE indexed to 100), paginated trade history, and decision reports with full detail views. Includes Pydantic validation, filtering, pagination, and standard error responses.

---

## Feature 14: React Dashboard - Setup & Portfolio View

**Branch:** `feature/14-dashboard-portfolio`
**Estimated effort:** ~6 hours

### Scope
- Set up React + Vite + TypeScript project in `frontend/`
- Install and configure: Tailwind CSS, React Router, TradingView Lightweight Charts, Recharts
- Create `frontend/Dockerfile` for production build (nginx serving static files)
- Create API client (`api/client.ts`) with base URL from env
- Implement Dashboard page (`/`):
  - Portfolio summary card (total value, cash, daily P&L, cumulative %)
  - Performance chart with toggleable benchmark lines (S&P 500, IWDA, VWCE)
  - Current positions table (sortable by weight, shows ticker, qty, avg price, current price, unrealized P&L, weight %)
  - "Today's Actions" panel showing latest pipeline trades
  - Pipeline status badge
- Dark theme: dark background, green = gains, red = losses
- Loading states and error handling (banner when API unreachable)
- Empty/onboarding state: "Run pipeline to start"

### How to Test
- `npm run dev` starts dev server at localhost:5173
- Dashboard loads and shows portfolio data from API
- Performance chart renders with toggleable benchmark lines
- Positions table sorts by weight
- Dark theme applied consistently
- Error banner shows when backend is down
- Empty state shows when no data exists

### PR Description
Sets up the React + Vite + TypeScript frontend with Tailwind CSS and implements the main dashboard page. Features a portfolio summary card, interactive performance chart with toggleable benchmark overlays (TradingView Lightweight Charts), sortable positions table, today's actions panel, and pipeline status. Dark theme with green/red P&L coloring, loading states, and error handling.

---

## Feature 15: React Dashboard - Trade History & Decisions Pages

**Branch:** `feature/15-dashboard-trades-decisions`
**Estimated effort:** ~5 hours

### Scope
- Implement Trade History page (`/trades`):
  - Filter bar (ticker search, BUY/SELL toggle, date range picker)
  - Trade table with pagination
  - Link from trade to decision detail
- Implement Decisions page (`/decisions`):
  - Filter bar (ticker, action, confidence slider, date range)
  - Decision card list with action badge, confidence, reasoning snippet, outcome
  - Click to navigate to detail
- Implement Decision Detail page (`/decisions/:id`):
  - Header: ticker, action badge, confidence, date
  - Reasoning section (full LLM text)
  - Technical indicators panel
  - News context panel
  - Memory references panel (clickable links to past decisions)
  - Outcome panel (P&L, benchmark comparison if assessed)
- Navigation: sidebar/header with links to Dashboard, Trades, Decisions

### How to Test
- Trade history page loads with data, filters work (ticker, side, date range)
- Pagination works (next/prev pages)
- Decisions page filters by confidence, action, ticker
- Decision detail shows all sections (reasoning, technicals, news, memory, outcome)
- Memory reference links navigate to other decision details
- Navigation between pages works smoothly

### PR Description
Implements the Trade History and Decisions pages for the dashboard. Trade History features filterable, paginated trade logs. Decisions page shows decision cards with action badges and confidence scores. Decision Detail view provides full transparency into the agent's reasoning: LLM text, technical indicators, news context, memory references (clickable), and outcome assessment.

---

## Feature 16: Backtesting Engine

**Branch:** `feature/16-backtesting-engine`
**Estimated effort:** ~6 hours

### Scope
- Implement `adapters/broker/simulated.py`:
  - Simulated broker that executes at next day's open price
  - Tracks simulated positions, cash, portfolio value
  - No external API calls
- Implement `services/backtest.py`:
  - Iterate through historical trading days in date range
  - Use same pipeline, screening, TA, LLM for each day
  - Memory isolation: backtest builds its own memory (doesn't use/pollute live memory)
  - No lookahead bias: only data up to day N available on day N
  - All trades/decisions stored with `is_backtest=True`, `backtest_run_id`
  - Compute metrics: total return %, annualized return %, max drawdown %, Sharpe ratio, win rate %, avg holding period, benchmark-relative alpha
- Implement API endpoints:
  - `POST /api/backtest/run` - Start backtest (202, async)
  - `GET /api/backtest/{run_id}` - Get results + metrics
  - Business rules: one backtest at a time, max 5-year range

### How to Test
- Unit test: SimulatedBroker executes at correct prices, tracks P&L accurately
- Unit test: no lookahead bias (day N only sees data up to day N)
- Unit test: memory isolation (backtest doesn't pollute live data)
- Unit test: metrics computation (Sharpe, drawdown, win rate) on known data
- Integration test: run short backtest (1 month) with MockLLMAdapter, verify results
- API test: POST returns 202 with run_id, GET returns results when complete, 409 on concurrent

### PR Description
Implements the backtesting engine that replays historical data through the exact same pipeline used for live trading. Features a simulated broker (fills at next-day open), memory isolation per backtest run, no-lookahead-bias guarantee, and comprehensive performance metrics (return %, Sharpe ratio, max drawdown, win rate, benchmark alpha). Backtest results and all trades/decisions are browsable through existing API endpoints.

---

## Feature 17: Backtest Dashboard Page

**Branch:** `feature/17-dashboard-backtest`
**Estimated effort:** ~3 hours

### Scope
- Implement Backtest page (`/backtest`):
  - Form: start date, end date, initial capital, optional config overrides
  - Run button (disabled while running, shows progress)
  - Progress indicator: "Processing day X of Y..."
  - Results panel: return %, benchmarks, key metrics table
  - Performance chart: equity curve vs benchmarks
  - Backtest trade log (links to backtest decisions)
- Wire to `POST /api/backtest/run` and `GET /api/backtest/{run_id}` with polling

### How to Test
- Backtest form submits and shows progress
- Results display correctly when backtest completes
- Performance chart renders equity curve with benchmarks
- Backtest trade log links to decision details
- Form validates dates (must be in past, max 5 year range)

### PR Description
Adds the Backtest page to the dashboard with a configuration form, real-time progress indicator, results panel with performance metrics, equity curve chart with benchmark overlays, and a browsable trade log. Users can run historical simulations and visually compare the agent's strategy against S&P 500, IWDA, and VWCE.

---

## Feature 18: Testing & Error Handling Hardening

**Branch:** `feature/18-testing-hardening`
**Estimated effort:** ~5 hours

### Scope
- Create mock adapters for testing: `MockLLMAdapter`, `MockBrokerAdapter`, `MockMarketDataAdapter`, `MockNewsAdapter`
- Create test fixtures in `tests/conftest.py`: test DB, sample stocks, prices, decisions, portfolio
- Unit tests for all services (>= 80% coverage target):
  - `technical_analysis.py`, `screening.py`, `risk_manager.py`, `memory.py`, `pipeline.py`, `report_generator.py`
- Unit tests for all adapters (mocked external calls)
- Integration tests:
  - Full pipeline with mocked adapters
  - API routes with test database
- Comprehensive error handling review:
  - Verify all custom exceptions are caught and logged
  - Verify API returns proper error responses (400, 404, 409, 500)
  - Verify pipeline abort/continue logic per PRD

### How to Test
- `pytest --cov=tradeagent` shows >= 80% coverage for services and adapters
- All tests pass
- No unhandled exceptions in normal or error paths
- Error responses match documented format

### PR Description
Adds comprehensive test coverage (target 80%+) with mock adapters, test fixtures, and tests for all services and adapters. Includes a full pipeline integration test with mocked external dependencies and API route tests with a test database. Hardens error handling across all layers with proper exception catching, logging, and API error responses.

---

## Feature 19: Documentation & Final Polish

**Branch:** `feature/19-docs-polish`
**Estimated effort:** ~3 hours

### Scope
- Update `README.md` with:
  - Project overview and architecture diagram
  - Prerequisites (Docker, Claude CLI, API keys)
  - Quick start guide (`docker compose up`)
  - Configuration reference (config.yaml options)
  - Running backtests
  - Development setup (local without Docker)
- Complete `config/config.example.yaml` with inline documentation
- Verify Docker Compose end-to-end: `docker compose up` from clean state works
- Verify frontend production build and nginx serving
- Smoke test: full pipeline → dashboard viewing → backtest run

### How to Test
- Fresh clone → follow README → `docker compose up` → working system
- Dashboard loads at localhost:3000
- API responds at localhost:8000
- Health check passes
- Config example has all options documented

### PR Description
Final polish: comprehensive README with setup guide, architecture overview, configuration reference, and development instructions. Verifies the complete Docker Compose deployment works end-to-end from a clean state. Completes config.example.yaml with inline documentation for all options.

---

## Summary & Dependency Graph

```
Feature 1:  Project Scaffolding & Config
    │
Feature 2:  Database Models & Migrations
    │
Feature 3:  Docker Compose & Health Check
    │
Feature 4:  Repository Layer
    │
    ├── Feature 5:  Adapter Interfaces & Market Data
    │       │
    │       ├── Feature 6:  Technical Analysis Engine
    │       │
    │       ├── Feature 7:  News Adapter (Perplexity)
    │       │
    │       └── Feature 8:  LLM Adapter (Claude CLI)
    │
    ├── Feature 9:  Risk Manager
    │
    └── Feature 10: Memory & Learning Service
            │
Feature 11: Pipeline Orchestrator  ← depends on 5-10
    │
Feature 12: Broker Adapter & Trade Execution
    │
Feature 13: Portfolio API Endpoints
    │
Feature 14: Dashboard - Portfolio View
    │
Feature 15: Dashboard - Trades & Decisions
    │
Feature 16: Backtesting Engine
    │
Feature 17: Dashboard - Backtest Page
    │
Feature 18: Testing & Hardening
    │
Feature 19: Documentation & Polish
```

**Total: 19 feature branches, ~80 hours estimated**

Features 5-10 can be developed in parallel after Feature 4 is merged.
Features 14-15 (frontend) can begin as soon as Feature 13 (API) is ready.
Feature 16-17 (backtesting) can begin after Feature 11 (pipeline) is working.
