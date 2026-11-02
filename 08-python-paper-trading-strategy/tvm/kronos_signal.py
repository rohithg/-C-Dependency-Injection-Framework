"""Kronos K-line foundation model as a daily forecasting signal.

Kronos (https://github.com/shiyu-coder/Kronos, arXiv:2508.02739) is an
open-source decoder-only transformer pre-trained on ~12B OHLCV candles from
45 exchanges. Given a window of daily bars it samples plausible future
candles. We turn those samples into a small set of numbers per symbol:

    exp_ret      mean forecast return over `horizon` days
    std_ret      dispersion of that return across sampled paths
    p_up         fraction of sampled paths that finish higher
    exp_ret_1d   mean forecast return for the next bar only
    exp_min_low  mean of (lowest forecast low / last close - 1)  (path risk)

and map them to ETF weights with a deliberately simple rule (`kronos_weights`).

Honesty note: the public checkpoints were pre-trained on data through June
2024, so any backtest before July 2024 is not out-of-sample for the model.
`run_kronos_backtest.py` reports both windows separately.

Everything torch-related is imported lazily so the rest of the package (and
the test-suite) works without the ML dependencies installed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import TVMConfig, DEFAULT
from .data import OHLCV_COLS
from .strategy import State, target_weights

MODELS = {
    # variant: (tokenizer repo, model repo, max context)
    "mini": ("NeoQuasar/Kronos-Tokenizer-2k", "NeoQuasar/Kronos-mini", 2048),
    "small": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-small", 512),
    "base": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-base", 512),
}
FORECAST_COLS = ["exp_ret", "std_ret", "p_up", "exp_ret_1d", "exp_min_low"]
FORECAST_DIR = Path(__file__).resolve().parent.parent / "results"


@dataclass(frozen=True)
class KronosConfig:
    variant: str = "small"
    context: int = 400                  # daily bars fed to the model (<= max context)
    horizon: int = 5                    # forecast length in trading days
    samples: int = 8                    # Monte-Carlo paths per symbol
    temperature: float = 1.0
    top_p: float = 0.9
    symbols: tuple[str, ...] = ("SPY", "QQQ")
    # decision rule ------------------------------------------------------
    rule: str = "direction"             # direction | confidence | tvm-veto
    min_edge: float = 0.0               # go long only if exp_ret exceeds this
    confidence_scale: float = 1.0       # exposure = scale * exp_ret/std_ret   (confidence rule)
    veto_p_up: float = 0.35             # tvm-veto: cut to cash when p_up below this
    max_leverage: float = 1.0
    portfolio_band: float = 0.10        # live trader: rebalance when L1 drift from target exceeds this
    seed: int | None = 0                # fixed seed -> reproducible paper-trading decisions

    def forecast_cache(self, cache_dir: Path = FORECAST_DIR) -> Path:
        return cache_dir / f"kronos_forecasts_{self.variant}_c{self.context}_h{self.horizon}_s{self.samples}.csv"


# --------------------------------------------------------------------------- model

@lru_cache(maxsize=2)
def load_predictor(variant: str = "small", max_context: int | None = None):
    """Download (once, cached by huggingface_hub) and load a Kronos checkpoint on CPU."""
    import torch
    from .kronos_vendor import Kronos, KronosTokenizer, KronosPredictor

    tok_repo, model_repo, ctx = MODELS[variant]
    tokenizer = KronosTokenizer.from_pretrained(tok_repo)
    model = Kronos.from_pretrained(model_repo)
    model.eval()
    return KronosPredictor(model, tokenizer, device="cpu", max_context=max_context or ctx)


def future_timestamps(last: pd.Timestamp, horizon: int) -> pd.Series:
    """Next `horizon` weekdays after `last` (the model only reads weekday/day/month)."""
    return pd.Series(pd.bdate_range(last + pd.Timedelta(days=1), periods=horizon))


def forecast(predictor, bars: dict[str, pd.DataFrame], cfg: KronosConfig) -> pd.DataFrame:
    """One forecast per symbol from the last `cfg.context` bars of each frame.

    All symbols x samples go through the model as a single batch (each row a
    single-sample path) so we can measure dispersion as well as the mean.
    Returns a DataFrame indexed by symbol with FORECAST_COLS.
    """
    import torch

    if cfg.seed is not None:
        torch.manual_seed(cfg.seed)
    dfs, xts, yts, last_close, order = [], [], [], [], []
    for sym in cfg.symbols:
        x = bars[sym][OHLCV_COLS].dropna().iloc[-cfg.context:]
        if len(x) < cfg.context:
            raise ValueError(f"{sym}: need {cfg.context} bars, have {len(x)}")
        xt = pd.Series(x.index)
        yt = future_timestamps(x.index[-1], cfg.horizon)
        for _ in range(cfg.samples):
            dfs.append(x); xts.append(xt); yts.append(yt); order.append(sym)
        last_close.append(float(x["close"].iloc[-1]))
    preds = predictor.predict_batch(dfs, xts, yts, pred_len=cfg.horizon, T=cfg.temperature,
                                    top_k=0, top_p=cfg.top_p, sample_count=1, verbose=False)
    rows = {}
    for i, sym in enumerate(cfg.symbols):
        paths = preds[i * cfg.samples:(i + 1) * cfg.samples]
        lc = last_close[i]
        rets = np.array([p["close"].iloc[-1] / lc - 1.0 for p in paths])
        rows[sym] = {
            "exp_ret": float(rets.mean()),
            "std_ret": float(rets.std(ddof=0)),
            "p_up": float((rets > 0).mean()),
            "exp_ret_1d": float(np.mean([p["close"].iloc[0] / lc - 1.0 for p in paths])),
            "exp_min_low": float(np.mean([p["low"].min() / lc - 1.0 for p in paths])),
        }
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=FORECAST_COLS)


# --------------------------------------------------------------------------- walk-forward

def load_forecasts(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "symbol", *FORECAST_COLS])
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def walk_forward(bars: dict[str, pd.DataFrame], dates: pd.DatetimeIndex, cfg: KronosConfig,
                 cache_path: Path | None = None, log=print, flush_every: int = 20) -> pd.DataFrame:
    """Forecast at every close in `dates` using only bars up to and including
    that day. Results are appended to a CSV cache so a long run can resume."""
    cache_path = cache_path or cfg.forecast_cache()
    done = load_forecasts(cache_path)
    have = set(pd.to_datetime(done["date"]).dt.normalize()) if len(done) else set()
    todo = [d for d in dates if d.normalize() not in have]
    if not todo:
        return done
    predictor = load_predictor(cfg.variant)
    new_rows = []
    for n, d in enumerate(todo, 1):
        window = {s: bars[s].loc[:d] for s in cfg.symbols}
        if any(len(window[s]) < cfg.context for s in cfg.symbols):
            continue
        fc = forecast(predictor, window, cfg)
        for sym, r in fc.iterrows():
            new_rows.append({"date": d.normalize(), "symbol": sym, **r.to_dict()})
        if n % flush_every == 0 or n == len(todo):
            done = pd.concat([done, pd.DataFrame(new_rows)], ignore_index=True)
            new_rows = []
            done = done.sort_values(["date", "symbol"]).reset_index(drop=True)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            done.to_csv(cache_path, index=False)
            log(f"kronos walk-forward {n}/{len(todo)} ({d.date()})")
    return done


def forecasts_wide(long: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """{column: DataFrame(date x symbol)} view of the long cache."""
    out = {}
    for col in FORECAST_COLS:
        out[col] = long.pivot(index="date", columns="symbol", values=col).sort_index()
    return out


def calibrate(long: pd.DataFrame, window: int = 126, min_periods: int = 40) -> pd.DataFrame:
    """Add `z_ret`: today's exp_ret relative to the model's own recent forecasts
    for that symbol ((x - rolling mean) / rolling std, using *prior* days only).

    Zero-shot Kronos has a persistent bearish drift on trending US index data
    (it forecasts prices reverting toward the context-window mean), so the raw
    sign of exp_ret is rarely positive. Comparing each forecast with the
    model's own recent baseline strips that drift out without any look-ahead.
    """
    df = long.sort_values(["symbol", "date"]).copy()
    g = df.groupby("symbol")["exp_ret"]
    mu = g.transform(lambda s: s.shift(1).rolling(window, min_periods=min_periods).mean())
    sd = g.transform(lambda s: s.shift(1).rolling(window, min_periods=min_periods).std())
    df["z_ret"] = (df["exp_ret"] - mu) / sd.replace(0.0, np.nan)
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


# --------------------------------------------------------------------------- decision rules

RULES = ("direction", "calibrated", "relative", "confidence", "tvm-veto")


def kronos_weights(fc: pd.DataFrame, cfg: KronosConfig, tvm: TVMConfig = DEFAULT,
                   tvm_weights: dict[str, float] | None = None) -> dict[str, float]:
    """Map one day's forecasts (index = symbol) to ETF weights.

    direction   100% in the symbol with the highest raw expected return if it
                clears `min_edge`, otherwise 100% cash ETF.
    calibrated  same, but on `z_ret` (forecast vs the model's own recent
                forecasts, see `calibrate`); `min_edge` is then in z units.
    relative    always invested; Kronos only picks SPY vs QQQ.
    confidence  like calibrated, sized by z_ret * confidence_scale and capped
                at `max_leverage` (>1x uses the 2x ETF).
    tvm-veto    take the TVM ensemble's weights (`tvm_weights`) but move to
                cash when Kronos sees fewer than `veto_p_up` paths finishing up
                for the asset TVM wants to hold.
    """
    fc = fc.reindex(list(cfg.symbols)).dropna(subset=["exp_ret"])
    cash = {tvm.cash_symbol: 1.0}
    if fc.empty:
        return tvm_weights or cash
    if cfg.rule == "tvm-veto":
        if not tvm_weights:
            return cash
        inv_lev = {v: k for k, v in tvm.leveraged_2x.items()}
        held = {inv_lev.get(s, s) for s, w in tvm_weights.items() if s != tvm.cash_symbol and w > 0}
        if held and all(float(fc.loc[a, "p_up"]) < cfg.veto_p_up for a in held if a in fc.index):
            return cash
        return tvm_weights
    if cfg.rule not in RULES:
        raise ValueError(f"unknown rule {cfg.rule!r}")
    score_col = "exp_ret" if cfg.rule in ("direction", "relative") else "z_ret"
    if score_col not in fc or fc[score_col].isna().all():
        return cash                      # calibration still warming up
    best = str(fc[score_col].idxmax())
    edge = float(fc.loc[best, score_col])
    if cfg.rule == "relative":
        exposure = 1.0
    elif edge <= cfg.min_edge:
        return cash
    elif cfg.rule == "confidence":
        exposure = min(cfg.max_leverage, cfg.confidence_scale * edge)
    else:
        exposure = 1.0
    tvm2 = replace(tvm, max_leverage=max(tvm.max_leverage, cfg.max_leverage))
    return target_weights(State(asset=best, exposure=exposure, days_held=0, risk_on=True), tvm2)


def rule_targets(long: pd.DataFrame, cfg: KronosConfig, tvm: TVMConfig = DEFAULT,
                 tvm_targets: pd.DataFrame | None = None) -> pd.DataFrame:
    """Daily target weights (date x tradable ETF) for one rule over the whole
    forecast history. `tvm_targets` (date x ETF) is needed for `tvm-veto`."""
    from .adaptive import tradable_symbols

    long = calibrate(long) if "z_ret" not in long else long
    cols = tradable_symbols(tvm)
    rows, idx = [], []
    for d, fc in long.groupby("date"):
        fc = fc.set_index("symbol")
        tw = None
        if tvm_targets is not None:
            if d not in tvm_targets.index or tvm_targets.loc[d].isna().any():
                continue
            tw = {s: float(w) for s, w in tvm_targets.loc[d].items() if w > 0}
        rows.append(kronos_weights(fc, cfg, tvm, tw)); idx.append(d)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx)).reindex(columns=cols).fillna(0.0)
