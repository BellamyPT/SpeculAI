# SpeculAI

Autonomous trading agent that screens global equities, computes technical indicators, gathers live news, retrieves past decision history for context, feeds everything into an LLM (Claude) for structured trade recommendations, then executes approved trades against Trading 212's Practice API (paper trading only). A React dashboard visualizes portfolio performance, trade history, decision reports, and benchmark comparisons.

```
                   ┌─────────────────────────────────────────┐
                   │            Daily Pipeline               │
                   │                                         │
  yfinance ──────► │  Market Data → Indicators → Screening  │
  Perplexity ────► │  News ──────────────────┐              │
  PostgreSQL ────► │  Memory (past decisions) ├─► LLM ──► Risk Manager ──► Broker
                   │                          │              │
                   └──────────┬──────────────────────────────┘
                              │
                   ┌──────────▼──────────────┐
                   │    React Dashboard      │
                   │  Portfolio · Trades     │
                   │  Decisions · Backtest   │
                   └─────────────────────────┘
```

**Tech stack:** Python 3.12+, FastAPI, PostgreSQL 16, SQLAlchemy 2.0, Alembic, React 18 + Vite 5, Tailwind CSS, TradingView Lightweight Charts, yfinance, Perplexity API, Claude CLI, APScheduler, Docker Compose.

## Prerequisites

- **Docker** and **Docker Compose** (v2)
- **Claude CLI** installed and authenticated (`claude` command available)
- API keys: Trading 212 (Practice), Perplexity

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd SpeculAI

# 2. Copy environment files
cp .env.example .env
cp config/config.example.yaml config/config.yaml

# 3. Fill in your API keys in .env
#    - T212_API_KEY, T212_API_SECRET
#    - PERPLEXITY_API_KEY

# 4. Start everything
docker compose up --build

# 5. Wait for backend health check
curl http://localhost:8000/api/health

# 6. Open the dashboard
open http://localhost:3000
```

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql://tradeagent:tradeagent_dev@db:5432/tradeagent` | PostgreSQL connection |
| `T212_API_KEY` | No | | Trading 212 Practice API key |
| `T212_API_SECRET` | No | | Trading 212 API secret |
| `T212_BASE_URL` | No | `https://demo.trading212.com/api/v0` | Trading 212 API URL |
| `PERPLEXITY_API_KEY` | No | | Perplexity API key for news |
| `PERPLEXITY_MODEL` | No | `sonar` | Perplexity model |
| `CLAUDE_CLI_PATH` | No | `claude` | Path to Claude CLI binary |
| `CLAUDE_CLI_TIMEOUT` | No | `120` | CLI timeout in seconds |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `FRONTEND_URL` | No | `http://localhost:5173` | Frontend URL for CORS |
| `DB_PASSWORD` | No | `tradeagent_dev` | PostgreSQL password |

### Runtime Config (`config/config.yaml`)

See `config/config.example.yaml` for a fully documented example with all available options including portfolio limits, screening weights, technical analysis parameters, and benchmark definitions.

## Running Backtests

### Via Dashboard

1. Navigate to **Backtest** in the sidebar
2. Set start date, end date, and initial capital
3. Click **Run Backtest**
4. Watch progress, then view metrics and equity curve

### Via API

```bash
# Start a backtest
curl -X POST http://localhost:8000/api/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"start_date":"2024-01-01","end_date":"2024-06-30","initial_capital":50000}'

# Poll progress (use the backtest_run_id from above)
curl http://localhost:8000/api/backtest/<run_id>
```

## Development Setup

### Without Docker

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Requires a running PostgreSQL instance
export DATABASE_URL=postgresql://tradeagent:tradeagent_dev@localhost:5432/tradeagent
alembic upgrade head
python scripts/seed_watchlist.py
python scripts/seed_benchmarks.py
uvicorn tradeagent.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

### Useful Commands

```bash
# Docker
docker compose up --build              # Start all services
docker compose logs backend -f         # Stream backend logs
docker compose exec db psql -U tradeagent  # PostgreSQL shell
docker compose down -v                 # Stop + remove volumes

# Testing
pytest                                 # Run all tests
pytest tests/unit/ -v                  # Unit tests
pytest tests/integration/ -v           # Integration tests
pytest --cov=tradeagent --cov-report=term-missing  # Coverage

# Manual pipeline run
docker compose exec backend python scripts/run_pipeline.py
```

## Architecture

```
API routes → Services → Repositories → Database
                ↓
            Adapters → External Services (LLM, market data, news, broker)
```

- **Routes** handle HTTP, validation, response formatting
- **Services** contain all business logic
- **Repositories** handle database queries (async SQLAlchemy)
- **Adapters** wrap external APIs behind abstract interfaces (swappable)

### Directory Structure

```
src/tradeagent/
├── main.py                  # FastAPI entry point
├── config.py                # Pydantic Settings
├── api/routes/              # HTTP endpoints
├── core/                    # Exceptions, logging, types
├── models/                  # SQLAlchemy 2.0 models
├── schemas/                 # Pydantic request/response schemas
├── services/                # Business logic (pipeline, backtest, etc.)
├── adapters/                # External service integrations
│   ├── broker/              # Trading 212 + simulated broker
│   ├── llm/                 # Claude CLI + mock LLM
│   ├── market_data/         # yfinance + mock market data
│   └── news/                # Perplexity + mock news
└── repositories/            # Data access layer

frontend/                    # React + Vite + TypeScript
tests/                       # Unit, integration, backtest tests
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/portfolio/summary` | Portfolio value, positions, P&L |
| `GET` | `/api/portfolio/performance` | Time series with benchmarks |
| `GET` | `/api/trades` | Paginated trade history |
| `GET` | `/api/decisions` | Paginated decision reports |
| `GET` | `/api/decisions/{id}` | Full decision detail |
| `POST` | `/api/pipeline/run` | Trigger pipeline (202) |
| `GET` | `/api/pipeline/status` | Pipeline status |
| `POST` | `/api/backtest/run` | Start backtest (202) |
| `GET` | `/api/backtest/{run_id}` | Backtest progress/results |

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Coverage (80% threshold enforced)
pytest --cov=tradeagent --cov-report=term-missing
```

## Disclaimer

This software is for **paper trading and educational purposes only**. It does not constitute financial advice. Trading involves risk — past performance does not guarantee future results. The system connects only to Trading 212's Practice (demo) environment.
