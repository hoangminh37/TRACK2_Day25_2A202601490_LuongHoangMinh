"""Unit tests for Lab 25 Extensions:
- Extension 2: MBU-based Right-sizing
- Extension 4: Reasoning Traffic Economics & Budget Governance
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finops import metrics, pricing


# --- Tests for Extension 2 (MBU Right-Sizing) ---

def test_vram_cost_per_gb():
    # H100: $2.50 / 80GB = 0.03125 $/GB-hr
    assert abs(metrics.vram_cost_per_gb(2.50, 80) - 0.03125) < 1e-5
    # Guard against zero/negative VRAM
    assert metrics.vram_cost_per_gb(2.50, 0) == 0.0
    assert metrics.vram_cost_per_gb(-1.0, 80) == 0.0


def test_recommend_mbu_rightsize():
    mock_catalog = {
        "H100": {"on_demand_hr": "2.50", "peak_bw_tbs": "3.35", "hbm_gb": "80"},
        "A100": {"on_demand_hr": "1.79", "peak_bw_tbs": "2.00", "hbm_gb": "80"},
        "A10G": {"on_demand_hr": "1.00", "peak_bw_tbs": "0.60", "hbm_gb": "24"},
        "L4": {"on_demand_hr": "0.80", "peak_bw_tbs": "0.30", "hbm_gb": "24"},
    }

    # Case 1: A100 achieving 0.40 TB/s (400 GB/s) -> with 20% headroom requires 0.48 TB/s.
    # A10G has 0.60 TB/s at $1.00/hr (< $1.79). Should rightsize to A10G.
    rec = metrics.recommend_mbu_rightsize("A100", 0.40, mock_catalog, headroom=1.20)
    assert rec["is_rightsized"] is True
    assert rec["recommended_gpu"] == "A10G"
    assert abs(rec["hourly_savings"] - 0.79) < 1e-4
    assert rec["savings_pct"] > 40.0

    # Case 2: A10G achieving 0.15 TB/s -> with 20% headroom requires 0.18 TB/s.
    # L4 has 0.30 TB/s at $0.80/hr (< $1.00). Should rightsize to L4.
    rec_l4 = metrics.recommend_mbu_rightsize("A10G", 0.15, mock_catalog, headroom=1.20)
    assert rec_l4["is_rightsized"] is True
    assert rec_l4["recommended_gpu"] == "L4"
    assert abs(rec_l4["hourly_savings"] - 0.20) < 1e-4

    # Case 3: Workload already on the cheapest capable GPU (L4 achieving 0.20 TB/s)
    rec_same = metrics.recommend_mbu_rightsize("L4", 0.20, mock_catalog, headroom=1.20)
    assert rec_same["is_rightsized"] is False
    assert rec_same["recommended_gpu"] == "L4"
    assert rec_same["hourly_savings"] == 0.0


# --- Tests for Extension 4 (Reasoning Economics & Governance) ---

def test_evaluate_reasoning_impact():
    prices = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
    sample_rows = [
        {"input_tokens": 1000, "output_tokens": 500, "route_tier": "small", "is_reasoning": 0, "is_batch": 0},
        {"input_tokens": 1000, "output_tokens": 500, "route_tier": "small", "is_reasoning": 0, "is_batch": 0},
        {"input_tokens": 1000, "output_tokens": 500, "route_tier": "small", "is_reasoning": 1, "is_batch": 0},
    ]

    stats = pricing.evaluate_reasoning_impact(sample_rows, prices, wh_per_1k_tokens=0.30, reasoning_energy_mult=80.0)
    assert stats["total_requests"] == 3
    assert stats["reasoning_requests"] == 1
    assert stats["normal_requests"] == 2
    assert abs(stats["reasoning_req_pct"] - 33.3) < 0.1

    # Energy: Reasoning query consumes 80x more energy
    normal_query_wh = (1500 / 1000) * 0.30 * 1.0  # 0.45 Wh
    reasoning_query_wh = (1500 / 1000) * 0.30 * 80.0  # 36.0 Wh
    assert abs(stats["normal_energy_wh"] - (normal_query_wh * 2)) < 1e-2
    assert abs(stats["reasoning_energy_wh"] - reasoning_query_wh) < 1e-2
    # Reasoning represents >97% of total energy in this sample
    assert stats["reasoning_energy_pct"] > 95.0


def test_simulate_reasoning_cap():
    prices = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
    # 20 requests: 5 reasoning (25%), 15 normal
    rows = []
    for i in range(15):
        rows.append({"input_tokens": 1000, "output_tokens": 500, "route_tier": "small", "is_reasoning": 0, "is_batch": 0})
    for i in range(5):
        rows.append({"input_tokens": 1000, "output_tokens": 1000, "route_tier": "large", "is_reasoning": 1, "is_batch": 0})

    # Cap reasoning to 10%
    sim = pricing.simulate_reasoning_cap(rows, prices, target_reasoning_rate=0.10)
    assert sim["daily_cost_saved"] > 0
    assert sim["daily_kwh_saved"] > 0
    assert sim["governed_cost_daily"] < sim["initial_cost_daily"]
