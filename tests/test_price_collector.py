import time
from datetime import date

from app.services import price_collector


def test_run_fetch_with_timeout_returns_none_for_slow_source():
    def slow_fetch(_ticker: str, _market: str, _target_date: date):
        time.sleep(0.2)
        return {"source": "slow"}

    original_timeout = price_collector.FETCH_TIMEOUT_SECONDS
    try:
        price_collector.FETCH_TIMEOUT_SECONDS = 0.05
        result = price_collector._run_fetch_with_timeout(slow_fetch, "688256.SH", "A", date(2026, 1, 16))
        assert result is None
    finally:
        price_collector.FETCH_TIMEOUT_SECONDS = original_timeout


def test_cross_verify_returns_first_available_result_when_other_source_times_out():
    original_timeout = price_collector.FETCH_TIMEOUT_SECONDS
    original_akshare = price_collector._fetch_akshare
    original_yfinance = price_collector._fetch_yfinance

    def slow_fetch(_ticker: str, _market: str, _target_date: date):
        time.sleep(0.2)
        return None

    def fast_fetch(_ticker: str, _market: str, _target_date: date):
        return {
            "open": 10.0,
            "close": 10.5,
            "change_pct": 5.0,
            "direction": "up",
            "source": "yfinance",
        }

    try:
        price_collector.FETCH_TIMEOUT_SECONDS = 0.05
        price_collector._fetch_akshare = slow_fetch
        price_collector._fetch_yfinance = fast_fetch

        result = price_collector.cross_verify("688256.SH", "A", date(2026, 1, 16))
        assert result is not None
        assert result["source"] == "yfinance"
        assert result["needs_review"] is False
    finally:
        price_collector.FETCH_TIMEOUT_SECONDS = original_timeout
        price_collector._fetch_akshare = original_akshare
        price_collector._fetch_yfinance = original_yfinance


def test_to_yfinance_ticker_normalizes_a_share_suffix():
    assert price_collector._to_yfinance_ticker("601398.SH", "A") == "601398.SS"
    assert price_collector._to_yfinance_ticker("000001.SZ", "A") == "000001.SZ"
