# Portfolio Analyzer

Dockerized HTTPS dashboard for analyzing a local portfolio database with fundamentals, dividends, price ranges, support/resistance, moving averages, volumes, screeners, FX display, and daily alerts. An external portfolio system can be used as an optional import source; after import, the app reads and analyzes its own local data.

## Run

```bash
cp config.example.yaml config.yaml
docker compose up --build
```

Open `https://localhost:6443`. The container generates a local self-signed certificate if `./certs/server.crt` and `./certs/server.key` do not exist.

Keep `config.yaml` private because it may include external provider credentials or optional import credentials.

## Data Sources

The dashboard reads holdings, transactions, account records, pension/fund records, and manual prices from the local SQLite portfolio database. External portfolio data is imported only when the Sync import action is run. Dividends, income, company profit, market cap, long price history, profile data, and non-portfolio stock screening come from configured market-data APIs:

- Alpha Vantage: adjusted daily prices, dividends in adjusted time series, income statements, overview, and FX.
- Financial Modeling Prep: historical prices, statements, profiles, dividends, symbol search, and screeners.

Set `ALPHA_VANTAGE_API_KEY` or `FMP_API_KEY` before `docker compose up -d --build`. Yahoo and Google Finance are intentionally disabled by default: Yahoo is unofficial/rate-limited, and Google Finance is a Sheets function rather than a supported backend API.

Market API responses are cached in `data/market-cache.sqlite3`. Configure the cache cap with `market_data.max_cache_mb`; the default is `300`.

The top banner is configured with `dashboard.banner_items`. Currency pairs use the no-key Frankfurter FX adapter by default; indexes, gold, and other quote symbols use the configured quote provider when available.

The Market Screener window searches stocks outside the portfolio through Financial Modeling Prep when `FMP_API_KEY` is set.
