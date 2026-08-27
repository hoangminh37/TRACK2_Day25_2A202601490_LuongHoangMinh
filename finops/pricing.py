"""Pricing & purchasing economics — measure in $/1M-token, not $/GPU-hr.

Figures are June-2026 as-of snapshots from the deck's RESEARCH dossier; treat
live prices as fast-moving (re-baseline before each cohort).
"""
from __future__ import annotations


def request_cost(
    input_tok: int,
    output_tok: int,
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in: int = 0,
    cache_discount: float = 0.10,   # Anthropic cached-read ~0.1x (=-90%)
    batch: bool = False,
    batch_discount: float = 0.50,   # Batch API ~ -50%
) -> float:
    """USD cost of a single request. Cached input billed at cache_discount x price."""
    cached_in = min(max(0, cached_in), input_tok)
    uncached_in = input_tok - cached_in
    cost = (
        (uncached_in / 1e6) * price_in_per_m
        + (cached_in / 1e6) * price_in_per_m * cache_discount
        + (output_tok / 1e6) * price_out_per_m
    )
    if batch:
        cost *= batch_discount
    return cost


def dollars_per_million(total_cost_usd: float, total_tokens: int) -> float:
    """Aggregate unit economics: $ per 1,000,000 tokens served."""
    if total_tokens <= 0:
        return 0.0
    return total_cost_usd / (total_tokens / 1e6)


def discount_stack(
    batch: bool = False,
    cache_hit_frac: float = 0.0,
    batch_discount: float = 0.50,
    cache_discount: float = 0.10,
) -> float:
    """Effective fraction of the naive bill after stacking discounts (input-heavy view).

    Discounts MULTIPLY: cache applies to the cached share of input, batch to the
    whole bill. batch + 100% cache-hit -> 0.5 * 0.1 = 0.05 (~95% off).
    """
    cache_mult = cache_hit_frac * cache_discount + (1.0 - cache_hit_frac)
    batch_mult = batch_discount if batch else 1.0
    return cache_mult * batch_mult


def break_even_utilization(discount_frac: float) -> float:
    """Utilization at which a commitment pays off ~= 1 - discount.

    A 45% reserved discount needs ~55% utilization (~13.2h/day) to beat on-demand.
    """
    return max(0.0, min(1.0, 1.0 - discount_frac))


def recommend_tier(hours_per_day: float, interruptible: bool, reserved_discount: float = 0.45) -> str:
    """Pick a purchasing tier from a workload's duty cycle + interruptibility.

    DOCUMENTED simple policy (instructor extension point — swap in your own):
      - interruptible & not 24/7  -> 'spot'      (checkpoint and ride the discount)
      - duty cycle >= break-even  -> 'reserved'  (steady, high utilization)
      - otherwise                 -> 'on_demand' (spiky / low duty)
    """
    duty = max(0.0, hours_per_day) / 24.0
    be = break_even_utilization(reserved_discount)
    if interruptible and hours_per_day < 24:
        return "spot"
    if duty >= be:
        return "reserved"
    return "on_demand"


def spot_checkpoint_cost(
    job_hours: float,
    spot_hr: float,
    on_demand_hr: float,
    interrupt_rate: float = 0.05,      # per-hour chance (H100 spot ~<5%)
    ckpt_overhead_frac: float = 0.03,  # steady cost of writing checkpoints
    rework_hours_per_interrupt: float = 0.5,
) -> dict:
    """Effective cost of running a checkpointable job on spot vs on-demand.

    Interruptions waste the compute since the last checkpoint (rework); checkpointing
    adds a small steady overhead. Spot still wins for interruptible jobs.
    """
    expected_interrupts = job_hours * interrupt_rate
    rework_hours = expected_interrupts * rework_hours_per_interrupt
    effective_hours = job_hours * (1.0 + ckpt_overhead_frac) + rework_hours
    spot_cost = effective_hours * spot_hr
    on_demand_cost = job_hours * on_demand_hr
    savings_pct = (1.0 - spot_cost / on_demand_cost) * 100.0 if on_demand_cost > 0 else 0.0
    return {
        "spot_effective_hours": round(effective_hours, 2),
        "spot_cost": round(spot_cost, 2),
        "on_demand_cost": round(on_demand_cost, 2),
        "savings_pct": round(savings_pct, 1),
    }


def evaluate_reasoning_impact(
    rows,
    model_prices: dict,
    wh_per_1k_tokens: float = 0.30,
    reasoning_energy_mult: float = 80.0,
) -> dict:
    """Evaluate financial ($) and energy (Wh) footprint of reasoning traffic vs normal traffic.

    Reasoning models (CoT / o1 / Gemini Thinking) generate many internal reasoning tokens
    and consume ~74-86x more energy per query.
    """
    stats = {
        "total_requests": len(rows),
        "reasoning_requests": 0,
        "normal_requests": 0,
        "reasoning_tokens": 0,
        "normal_tokens": 0,
        "total_tokens": 0,
        "reasoning_cost_usd": 0.0,
        "normal_cost_usd": 0.0,
        "total_cost_usd": 0.0,
        "reasoning_energy_wh": 0.0,
        "normal_energy_wh": 0.0,
        "total_energy_wh": 0.0,
    }

    for r in rows:
        inp = int(float(r.get("input_tokens", 0)))
        out = int(float(r.get("output_tokens", 0)))
        cached = int(float(r.get("cached_input_tokens", 0)))
        is_batch = bool(int(float(r.get("is_batch", 0))))
        is_reasoning = bool(int(float(r.get("is_reasoning", 0))))
        route_tier = str(r.get("route_tier", "small"))

        tokens = inp + out
        pin, pout = model_prices.get(route_tier, (0.20, 0.40))
        cost = request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

        base_wh = (tokens / 1000.0) * wh_per_1k_tokens
        wh = base_wh * (reasoning_energy_mult if is_reasoning else 1.0)

        stats["total_tokens"] += tokens
        stats["total_cost_usd"] += cost
        stats["total_energy_wh"] += wh

        if is_reasoning:
            stats["reasoning_requests"] += 1
            stats["reasoning_tokens"] += tokens
            stats["reasoning_cost_usd"] += cost
            stats["reasoning_energy_wh"] += wh
        else:
            stats["normal_requests"] += 1
            stats["normal_tokens"] += tokens
            stats["normal_cost_usd"] += cost
            stats["normal_energy_wh"] += wh

    n = max(1, stats["total_requests"])
    tot_tok = max(1, stats["total_tokens"])
    tot_cost = max(1e-9, stats["total_cost_usd"])
    tot_wh = max(1e-9, stats["total_energy_wh"])

    stats["reasoning_req_pct"] = round(stats["reasoning_requests"] / n * 100.0, 1)
    stats["reasoning_tok_pct"] = round(stats["reasoning_tokens"] / tot_tok * 100.0, 1)
    stats["reasoning_cost_pct"] = round(stats["reasoning_cost_usd"] / tot_cost * 100.0, 1)
    stats["reasoning_energy_pct"] = round(stats["reasoning_energy_wh"] / tot_wh * 100.0, 1)
    stats["reasoning_cost_usd"] = round(stats["reasoning_cost_usd"], 2)
    stats["normal_cost_usd"] = round(stats["normal_cost_usd"], 2)
    stats["total_cost_usd"] = round(stats["total_cost_usd"], 2)
    stats["reasoning_energy_wh"] = round(stats["reasoning_energy_wh"], 1)
    stats["normal_energy_wh"] = round(stats["normal_energy_wh"], 1)
    stats["total_energy_wh"] = round(stats["total_energy_wh"], 1)
    return stats


def simulate_reasoning_cap(
    rows,
    model_prices: dict,
    target_reasoning_rate: float = 0.05,
    wh_per_1k_tokens: float = 0.30,
    reasoning_energy_mult: float = 80.0,
) -> dict:

    """Simulate a governed reasoning policy capping reasoning traffic to `target_reasoning_rate`.

    Excess reasoning queries are routed to standard (non-reasoning) prompts or distilled models.
    """
    initial = evaluate_reasoning_impact(rows, model_prices, wh_per_1k_tokens, reasoning_energy_mult)
    current_rate = initial["reasoning_requests"] / max(1, initial["total_requests"])

    if current_rate <= target_reasoning_rate:
        reduction_fraction = 0.0
    else:
        reduction_fraction = (current_rate - target_reasoning_rate) / current_rate

    saved_reasoning_cost = initial["reasoning_cost_usd"] * reduction_fraction * 0.70  # standard prompt still costs ~30%
    saved_reasoning_wh = initial["reasoning_energy_wh"] * reduction_fraction * (1.0 - 1.0 / reasoning_energy_mult)

    new_cost = initial["total_cost_usd"] - saved_reasoning_cost
    new_wh = initial["total_energy_wh"] - saved_reasoning_wh

    return {
        "initial_cost_daily": initial["total_cost_usd"],
        "governed_cost_daily": round(new_cost, 2),
        "daily_cost_saved": round(saved_reasoning_cost, 2),
        "monthly_cost_saved": round(saved_reasoning_cost * 30, 2),
        "initial_kwh_daily": round(initial["total_energy_wh"] / 1000.0, 2),
        "governed_kwh_daily": round(new_wh / 1000.0, 2),
        "daily_kwh_saved": round(saved_reasoning_wh / 1000.0, 2),
        "target_reasoning_rate_pct": round(target_reasoning_rate * 100.0, 1),
    }

