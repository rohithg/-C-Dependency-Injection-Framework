"""Price data access with a local CSV cache.

Uses yfinance (free, no key) for adjusted closes. The cache lets the
backtest and tests run offline once data has been fetched once.
"""
from __future__ import annotations

from pathlib import Path
import datetime as dt

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"


def load_closes(symbols: list[str], start: str = "1993-01-01", end: str | None = None,
                cache_dir: Path = CACHE_DIR, refresh: bool = False) -> pd.DataFrame:
    """Adjusted close prices, one column per symbol, business-day index."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for sym in symbols:
        path = cache_dir / f"{sym.replace('^', '_')}.csv"
        if path.exists() and not refresh and _is_fresh(path):
            s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        else:
            s = _download(sym, start, end)
            s.to_csv(path, header=["close"])
        frames.append(s.rename(sym))
    closes = pd.concat(frames, axis=1).sort_index()
    if end:
        closes = closes.loc[:end]
    return closes.loc[start:]


def _is_fresh(path: Path, max_age_hours: float = 12) -> bool:
    age = dt.datetime.now() - dt.datetime.fromtimestamp(path.stat().st_mtime)
    return age < dt.timedelta(hours=max_age_hours)


def _download(sym: str, start: str, end: str | None) -> pd.Series:
    import yfinance as yf  # imported lazily so offline/cached runs don't need it

    df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"no data returned for {sym}")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna()


OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def load_ohlcv(symbol: str, start: str = "2000-01-01", end: str | None = None,
               cache_dir: Path = CACHE_DIR, refresh: bool = False) -> pd.DataFrame:
    """Daily adjusted OHLCV bars (columns open/high/low/close/volume) for one
    symbol; used as the K-line input to the Kronos forecaster."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol.replace('^', '_')}_ohlcv.csv"
    if path.exists() and not refresh and _is_fresh(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if raw.empty:
            raise RuntimeError(f"no data returned for {symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw.rename(columns=str.lower)[OHLCV_COLS].astype(float)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.dropna()
        df.to_csv(path)
    if end:
        df = df.loc[:end]
    return df.loc[start:]


def tbill_daily_return(closes: pd.DataFrame, irx_col: str = "^IRX") -> pd.Series:
    """Approximate daily cash return from the 13-week T-bill yield (^IRX, in %)."""
    if irx_col not in closes:
        return pd.Series(0.0, index=closes.index)
    return (closes[irx_col].ffill() / 100.0 / 252.0).fillna(0.0)
