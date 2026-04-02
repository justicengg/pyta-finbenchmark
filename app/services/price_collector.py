"""
Price data collector with AKShare → Tushare → yfinance fallback chain.
Returns price direction for a given ticker on a target date.
"""

from __future__ import annotations

import logging
import queue
import threading
from datetime import date, timedelta

logger = logging.getLogger(__name__)

FLAT_THRESHOLD = 0.005  # ±0.5% counts as flat
FETCH_TIMEOUT_SECONDS = 8.0


def get_price_direction(
    ticker: str,
    market: str,
    target_date: date,
) -> dict | None:
    """
    Return price info for ticker on target_date.
    Falls back across sources; returns None if all sources fail.

    Return shape:
        {
            "open": float,
            "close": float,
            "change_pct": float,        # e.g. 1.87 means +1.87%
            "direction": "up"|"down"|"flat",
            "source": "akshare"|"tushare"|"yfinance",
        }
    """
    for fetch_fn in (_fetch_akshare, _fetch_yfinance):
        result = _run_fetch_with_timeout(fetch_fn, ticker, market, target_date)
        if result:
            return result
    return None


def cross_verify(ticker: str, market: str, target_date: date) -> dict | None:
    """
    Fetch from all available sources and cross-verify.
    Returns result with needs_review=True if sources disagree by >0.3%.
    """
    results = []
    for fetch_fn in (_fetch_akshare, _fetch_yfinance):
        result = _run_fetch_with_timeout(fetch_fn, ticker, market, target_date)
        if result:
            results.append(result)

    if not results:
        return None

    primary = results[0]
    needs_review = False

    if len(results) > 1:
        changes = [r["change_pct"] for r in results]
        spread = max(changes) - min(changes)
        if spread > 0.3:
            needs_review = True
            logger.info("Price source disagreement for %s on %s: spread=%.3f%%", ticker, target_date, spread)

    primary["needs_review"] = needs_review
    return primary


def _run_fetch_with_timeout(fetch_fn, ticker: str, market: str, target_date: date) -> dict | None:
    result_queue: queue.Queue[tuple[str, dict | None] | tuple[str, BaseException]] = queue.Queue(maxsize=1)

    def _worker() -> None:
        try:
            result_queue.put(("result", fetch_fn(ticker, market, target_date)))
        except BaseException as exc:  # pragma: no cover - defensive path
            result_queue.put(("error", exc))

    thread = threading.Thread(
        target=_worker,
        name=f"price-fetch-{fetch_fn.__name__}",
        daemon=True,
    )
    thread.start()

    try:
        kind, payload = result_queue.get(timeout=FETCH_TIMEOUT_SECONDS)
    except queue.Empty:
        logger.warning(
            "Price fetch timeout (%s) for %s %s on %s",
            fetch_fn.__name__,
            ticker,
            market,
            target_date,
        )
        return None

    if kind == "error":
        logger.warning("Price fetch failed (%s): %s", fetch_fn.__name__, payload)
        return None

    return payload


# ── AKShare ────────────────────────────────────────────────────────────────────

def _fetch_akshare(ticker: str, market: str, target_date: date) -> dict | None:
    import akshare as ak  # type: ignore

    date_str = target_date.strftime("%Y%m%d")
    prev_str = (target_date - timedelta(days=5)).strftime("%Y%m%d")

    try:
        if market in ("HK",):
            symbol = ticker.replace(".HK", "").zfill(5)
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            df = df[df["date"] == target_date.strftime("%Y-%m-%d")]
        elif market in ("A", "CN"):
            symbol = ticker.split(".")[0]
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=prev_str,
                end_date=date_str,
                adjust="qfq",
            )
            df = df[df["日期"] == target_date.strftime("%Y-%m-%d")]
        else:
            return None

        if df.empty:
            return None

        row = df.iloc[0]
        open_price = float(row.get("开盘") or row.get("open", 0))
        close_price = float(row.get("收盘") or row.get("close", 0))
        if open_price == 0:
            return None
        change_pct = (close_price - open_price) / open_price * 100
        return {
            "open": open_price,
            "close": close_price,
            "change_pct": round(change_pct, 4),
            "direction": _to_direction(change_pct),
            "source": "akshare",
        }
    except Exception:
        return None


# ── yfinance ───────────────────────────────────────────────────────────────────

def _fetch_yfinance(ticker: str, market: str, target_date: date) -> dict | None:
    import yfinance as yf  # type: ignore

    yf_ticker = _to_yfinance_ticker(ticker, market)
    start = target_date
    end = target_date + timedelta(days=1)
    df = yf.download(yf_ticker, start=start, end=end, progress=False)

    if df.empty:
        return None

    row = df.iloc[0]
    open_price = float(row["Open"])
    close_price = float(row["Close"])
    if open_price == 0:
        return None
    change_pct = (close_price - open_price) / open_price * 100
    return {
        "open": open_price,
        "close": close_price,
        "change_pct": round(change_pct, 4),
        "direction": _to_direction(change_pct),
        "source": "yfinance",
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_direction(change_pct: float) -> str:
    if change_pct > FLAT_THRESHOLD * 100:
        return "up"
    if change_pct < -FLAT_THRESHOLD * 100:
        return "down"
    return "flat"


def _to_yfinance_ticker(ticker: str, market: str) -> str:
    if market == "HK":
        code = ticker.replace(".HK", "").zfill(4)
        return f"{code}.HK"
    if market in ("A", "CN"):
        if ticker.startswith("6"):
            return f"{ticker}.SS"
        return f"{ticker}.SZ"
    return ticker
