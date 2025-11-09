"""Utilities for downloading stock price data and persisting it to CSV files."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Iterable, Sequence

import requests


YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"


class StockPriceFetchError(RuntimeError):
    """Raised when the price data cannot be retrieved from the remote service."""


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    unique: list[str] = []
    for symbol in symbols:
        symbol = symbol.strip().upper()
        if not symbol:
            continue
        if symbol not in unique:
            unique.append(symbol)
    if not unique:
        raise ValueError("At least one ticker symbol must be provided")
    return unique


def fetch_and_save_stock_prices(symbols: Sequence[str], csv_path: str | Path) -> Path:
    """Fetch latest stock price quotes for *symbols* and store them in *csv_path*.

    Parameters
    ----------
    symbols:
        A sequence of ticker symbols to fetch. Symbols are automatically
        normalized to uppercase and deduplicated. An error is raised if the
        resulting list is empty.
    csv_path:
        Destination path for the CSV file. Parent directories are created on
        demand.

    Returns
    -------
    pathlib.Path
        The absolute path to the written CSV file.

    Raises
    ------
    StockPriceFetchError
        If the remote API does not return a successful response.
    """

    tickers = _normalize_symbols(symbols)

    response = requests.get(YAHOO_QUOTE_URL, params={"symbols": ",".join(tickers)}, timeout=10)
    if response.status_code != 200:
        raise StockPriceFetchError(
            f"Failed to fetch stock data (status={response.status_code}): {response.text[:200]}"
        )

    payload = response.json()
    result = payload.get("quoteResponse", {}).get("result", [])
    if not result:
        raise StockPriceFetchError("No quote data returned for the requested symbols")

    records = []
    fetched_at = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for entry in result:
        price = entry.get("regularMarketPrice")
        if price is None:
            continue
        records.append(
            {
                "symbol": entry.get("symbol"),
                "price": price,
                "currency": entry.get("currency"),
                "exchange": entry.get("fullExchangeName"),
                "fetched_at": fetched_at,
            }
        )

    if not records:
        raise StockPriceFetchError("No usable price records returned for the requested symbols")

    csv_path = Path(csv_path).expanduser().resolve()
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["symbol", "price", "currency", "exchange", "fetched_at"])
        writer.writeheader()
        writer.writerows(records)

    return csv_path


__all__ = ["fetch_and_save_stock_prices", "StockPriceFetchError"]
