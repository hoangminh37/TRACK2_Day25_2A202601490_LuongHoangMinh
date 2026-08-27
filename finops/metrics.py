"""Efficiency metrics — the numbers that actually drive GPU cost.

Key teaching point (deck §5): nvidia-smi "GPU-Util %" is a *time-active* clock,
not an efficiency metric. A GPU can read 100% util while its MFU is ~20% — you
are paying the full GPU-hour for a fraction of the FLOPs you rented.
"""
from __future__ import annotations


def compute_mfu(achieved_tflops: float, peak_tflops: float) -> float:
    """Model FLOPs Utilization = achieved / peak (clamped to 0..1).

    Good training MFU is ~0.35-0.45; >0.50 is excellent. Returns 0 if peak<=0.
    """
    if peak_tflops <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_tflops / peak_tflops))


def compute_mbu(achieved_bw_tbs: float, peak_bw_tbs: float) -> float:
    """Model Bandwidth Utilization = achieved HBM BW / peak BW (clamped 0..1).

    The right metric for memory-bound decode; target ~0.60 on H100-80GB batch-1.
    """
    if peak_bw_tbs <= 0:
        return 0.0
    return max(0.0, min(1.0, achieved_bw_tbs / peak_bw_tbs))


def arithmetic_intensity(flops: float, bytes_moved: float) -> float:
    """FLOP / byte for a workload (the x-axis of the roofline model)."""
    if bytes_moved <= 0:
        return 0.0
    return flops / bytes_moved


def roofline_regime(intensity: float, ridge_point: float) -> str:
    """Below the ridge point a workload is memory-bound; at/above it is compute-bound.

    H100 ridge ~295 FLOP/byte (BF16). LLM decode (~1-2) is memory-bound; prefill
    (~455) is compute-bound — which is *why* prefill/decode disaggregation pays off.
    """
    return "compute-bound" if intensity >= ridge_point else "memory-bound"


def flag_util_lies(rows, util_threshold: float = 0.90, mfu_threshold: float = 0.30):
    """Return the rows where GPU-Util is high but MFU is low — money leaking.

    `rows` is an iterable of dicts each having 'gpu_util_pct' (0-100) and 'mfu' (0-1).
    These are GPUs you are billed full-rate for while they do little real compute.
    """
    out = []
    for r in rows:
        util = float(r.get("gpu_util_pct", 0)) / 100.0
        mfu = float(r.get("mfu", 0))
        if util >= util_threshold and mfu < mfu_threshold:
            out.append(r)
    return out


def idle_waste_usd(idle_hours: float, on_demand_hr: float) -> float:
    """Dollars burned by a GPU left running idle (training done, instance up)."""
    return max(0.0, idle_hours) * max(0.0, on_demand_hr)


def vram_cost_per_gb(on_demand_hr: float, hbm_gb: float) -> float:
    """Cost per GB of VRAM per hour ($/GB-hr). Lower is better for memory-capacity-bound tasks."""
    if hbm_gb <= 0:
        return 0.0
    return max(0.0, on_demand_hr) / hbm_gb


def recommend_mbu_rightsize(
    current_gpu_type: str,
    achieved_bw_tbs: float,
    catalog: dict,
    headroom: float = 1.20,
) -> dict:
    """Recommend a cheaper GPU that satisfies the memory bandwidth requirement.

    For memory-bound workloads (like LLM decode or low-concurrency inference),
    the bottleneck is memory bandwidth, not compute FLOPs. If a cheaper GPU has
    sufficient peak_bw_tbs >= achieved_bw_tbs * headroom, we can rightsize down.

    Returns dict with candidate info, hourly delta, and percent saved.
    """
    if current_gpu_type not in catalog:
        return {
            "current_gpu": current_gpu_type,
            "current_cost_hr": 0.0,
            "achieved_bw_tbs": achieved_bw_tbs,
            "required_bw_tbs": achieved_bw_tbs * headroom,
            "recommended_gpu": current_gpu_type,
            "recommended_cost_hr": 0.0,
            "hourly_savings": 0.0,
            "savings_pct": 0.0,
            "is_rightsized": False,
        }

    curr_spec = catalog[current_gpu_type]
    curr_cost = float(curr_spec["on_demand_hr"])
    required_bw = achieved_bw_tbs * headroom

    cheapest_type = current_gpu_type
    cheapest_cost = curr_cost

    for gtype, spec in catalog.items():
        cost = float(spec["on_demand_hr"])
        peak_bw = float(spec["peak_bw_tbs"])
        if cost < cheapest_cost and peak_bw >= required_bw:
            cheapest_type = gtype
            cheapest_cost = cost

    savings = curr_cost - cheapest_cost
    savings_pct = (savings / curr_cost * 100.0) if curr_cost > 0 else 0.0

    return {
        "current_gpu": current_gpu_type,
        "current_cost_hr": curr_cost,
        "achieved_bw_tbs": round(achieved_bw_tbs, 3),
        "required_bw_tbs": round(required_bw, 3),
        "recommended_gpu": cheapest_type,
        "recommended_cost_hr": cheapest_cost,
        "hourly_savings": round(savings, 4),
        "savings_pct": round(savings_pct, 1),
        "is_rightsized": cheapest_type != current_gpu_type,
    }

