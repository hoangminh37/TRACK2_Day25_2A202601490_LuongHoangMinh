"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # --- Extension 4: Reasoning Budget & Energy Impact ---
    reasoning_stats = pricing.evaluate_reasoning_impact(rows, MODEL_PRICES)
    reasoning_sim = pricing.simulate_reasoning_cap(rows, MODEL_PRICES, target_reasoning_rate=0.05)


    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        # Extension 4 Output
        print("\n" + "=" * 65)
        print("  EXTENSION 4: Reasoning Traffic Footprint & Budget Governance")
        print("=" * 65)
        print(f"Traffic Breakdown (Reasoning vs Standard):")
        print(f"  • Requests:  {reasoning_stats['reasoning_requests']:,} reasoning ({reasoning_stats['reasoning_req_pct']}%) vs {reasoning_stats['normal_requests']:,} standard")
        print(f"  • Tokens:    {reasoning_stats['reasoning_tokens']:,} ({reasoning_stats['reasoning_tok_pct']}%) vs {reasoning_stats['normal_tokens']:,} standard")
        print(f"  • Cost:      ${reasoning_stats['reasoning_cost_usd']:,.2f}/day ({reasoning_stats['reasoning_cost_pct']}%) vs ${reasoning_stats['normal_cost_usd']:,.2f}/day")
        print(f"  • Energy:    {reasoning_stats['reasoning_energy_wh']/1000:,.2f} kWh/day ({reasoning_stats['reasoning_energy_pct']}%) vs {reasoning_stats['normal_energy_wh']/1000:,.2f} kWh/day")
        print(f"\nReasoning Policy Simulation (Cap from {reasoning_stats['reasoning_req_pct']}% -> {reasoning_sim['target_reasoning_rate_pct']}%):")
        print(f"  • Daily Cost Saved:   ${reasoning_sim['daily_cost_saved']:,.2f}  (${reasoning_sim['monthly_cost_saved']:,.0f}/month)")
        print(f"  • Daily Energy Saved: {reasoning_sim['daily_kwh_saved']:,.2f} kWh  ({reasoning_sim['daily_kwh_saved']*30:,.1f} kWh/month)")
        print("=" * 65)

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_impact": reasoning_stats,
        "reasoning_governance": reasoning_sim,
    }


if __name__ == "__main__":
    run()

