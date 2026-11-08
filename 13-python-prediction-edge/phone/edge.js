// Settlement probability matches edge/crypto15m.py. The fee matches
// polymarket_taker_fee for one share: rate * p * (1 - p), half-up to 0.00001.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Edge = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const PRINTS = 60;

  function erf(x) {
    const sign = x < 0 ? -1 : 1;
    const a1 = 0.254829592;
    const a2 = -0.284496736;
    const a3 = 1.421413741;
    const a4 = -1.453152027;
    const a5 = 1.061405429;
    const p = 0.3275911;
    const t = 1 / (1 + p * Math.abs(x));
    const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
    return sign * y;
  }

  function normCdf(x) {
    return 0.5 * (1 + erf(x / Math.SQRT2));
  }

  function polyFee(price, rate) {
    const p = Number(price);
    const r = Number(rate);
    if (!(p > 0 && p < 1 && r > 0)) return 0;
    const raw = r * p * (1 - p);
    return Math.round(raw * 100000) / 100000;
  }

  function settlementUpProb(spot, strike, sigma, minsLeft) {
    if (!(spot > 0 && strike > 0 && sigma > 0)) return null;
    const left = Math.max(0, Number(minsLeft));
    const nFuture = Math.max(1, Math.min(PRINTS, Math.round(left * 60)));
    const sigma1s = sigma / Math.sqrt(60);
    const var_ = (spot * sigma1s) ** 2 * (nFuture * (nFuture + 1) * (2 * nFuture + 1) / 6) / (PRINTS ** 2);
    if (!(var_ > 0)) return null;
    return Math.min(1, Math.max(0, normCdf((spot - strike) / Math.sqrt(var_))));
  }

  function sigma1m(closes, window) {
    const n = window || 30;
    if (!closes || closes.length < n + 1) return null;
    const tail = closes.slice(-(n + 1));
    const rets = [];
    for (let i = 1; i < tail.length; i += 1) {
      if (tail[i - 1] > 0) rets.push(tail[i] / tail[i - 1] - 1);
    }
    if (rets.length < n) return null;
    const mean = rets.reduce((sum, value) => sum + value, 0) / rets.length;
    const var_ = rets.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (rets.length - 1);
    if (!(var_ > 0)) return null;
    return Math.sqrt(var_);
  }

  function decide(quote) {
    const prob = settlementUpProb(quote.spot, quote.strike, quote.sigma, 1);
    if (prob == null) return null;
    const rate = quote.rate == null ? 0.07 : quote.rate;
    const scored = [];
    function push(side, ask, chance) {
      if (!(ask > 0.01 && ask < 0.99)) return;
      const fee = polyFee(ask, rate);
      scored.push({ side, ask, fee, edge: chance * 100 - ask * 100 - fee * 100 });
    }
    push("up", quote.yesAsk, prob);
    if (quote.noAsk != null) push("down", quote.noAsk, 1 - prob);
    if (!scored.length) return null;
    scored.sort((a, b) => b.edge - a.edge);
    const best = scored[0];
    return {
      side: best.side,
      ask: best.ask,
      fee: best.fee,
      edgeCents: Math.round(best.edge * 100) / 100,
      upProb: prob,
      take: best.edge >= 2 && best.edge <= 3,
    };
  }

  function cycleDecision(input) {
    const left = Math.trunc(Number(input.secondsLeft));
    const base = {
      inWindow: left > 0 && left <= 60,
      take: false,
      side: null,
      edgeCents: null,
      fee: null,
      upProb: null,
      note: "",
    };
    if (left <= 0) {
      base.note = "Window closed.";
      return base;
    }
    if (!base.inWindow) {
      const minutes = Math.floor(left / 60);
      const seconds = String(left % 60).padStart(2, "0");
      base.note = minutes + "m " + seconds + "s left. The check runs in the last minute.";
      return base;
    }
    const decision = decide(input);
    if (!decision) {
      base.note = "Last minute. The book has no usable ask.";
      return base;
    }
    base.side = decision.side;
    base.edgeCents = decision.edgeCents;
    base.fee = decision.fee;
    base.upProb = decision.upProb;
    base.take = decision.take;
    const side = decision.side === "up" ? "Up" : "Down";
    base.note = decision.take
      ? "Last minute. " + side + " is " + decision.edgeCents.toFixed(1) + "¢ after the fee. One contract."
      : "Last minute. " + side + " is " + decision.edgeCents.toFixed(1) + "¢ after the fee, outside 2–3¢.";
    return base;
  }

  return { normCdf, polyFee, settlementUpProb, sigma1m, decide, cycleDecision };
});
