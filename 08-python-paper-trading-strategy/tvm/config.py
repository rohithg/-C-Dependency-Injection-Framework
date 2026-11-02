"""Strategy parameters for Trend-gated Volatility-targeted Momentum (TVM).

All values are plain data so they can be overridden from JSON / CLI without
touching the signal code. Defaults are the ones validated in the backtest
report (see README). Resist the urge to tune them per-year: the edge comes
from the structure (trend gate + vol sizing + leverage), not from precision.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import json
from pathlib import Path


@dataclass(frozen=True)
class TVMConfig:
    # Universe -------------------------------------------------------------
    trend_symbol: str = "SPY"            # broad-market series used for the regime gate
    risk_assets: tuple[str, ...] = ("SPY", "QQQ")
    leveraged_2x: dict[str, str] = field(default_factory=lambda: {"SPY": "SSO", "QQQ": "QLD"})
    cash_symbol: str = "BIL"             # 1-3 month T-bill ETF
    benchmark_symbol: str = "VOO"

    # Signals ---------------------------------------------------------------
    sma_window: int = 200                # trend gate: price > SMA(200) => risk-on
    momentum_window: int = 126           # ~6 months of trading days
    min_hold_days: int = 21              # re-evaluate asset pick at most monthly
    vol_window: int = 20                 # realized-vol lookback (trading days)
    target_vol: float = 0.20             # annualized
    max_leverage: float = 2.0            # hard cap; 2x ETFs make this implementable
    rebalance_band: float = 0.10         # trade only if |target - current| exposure > band

    # Cost model (backtest only) ------------------------------------------
    cost_bps: float = 2.0                # one-way cost per unit of notional traded
    lev_etf_expense: float = 0.009       # annual expense ratio of 2x ETFs
    borrow_spread: float = 0.005         # financing spread over T-bills inside 2x ETFs

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "TVMConfig":
        raw = json.loads(Path(path).read_text())
        if "risk_assets" in raw:
            raw["risk_assets"] = tuple(raw["risk_assets"])
        return cls(**raw)


DEFAULT = TVMConfig()
