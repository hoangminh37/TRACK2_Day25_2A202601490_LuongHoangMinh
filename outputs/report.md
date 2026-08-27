# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Unit Economics ($/1M-Token)

- **Baseline:** $6.488 / 1M-token
- **Optimized:** $1.126 / 1M-token
- **Unit Cost Reduction:** 82.6%

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Extension 2: MBU Right-Sizing Analysis

- **Total MBU Right-Sizing Monthly Savings:** $3,924
- **Memory-Bound GPUs Right-Sized:** 9 instances
  - `gpu-h100-0` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-h100-1` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-h100-2` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-h100-3` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-h100-4` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-h100-5` (H100) -> `A100`: Save $511/mo (28.4%)
  - `gpu-a100-1` (A100) -> `A10G`: Save $569/mo (44.1%)
  - `gpu-a10g-0` (A10G) -> `L4`: Save $144/mo (20.0%)
  - `gpu-a10g-1` (A10G) -> `L4`: Save $144/mo (20.0%)

## Extension 4: Reasoning Traffic Governance

- **Reasoning Traffic Policy:** Cap at 5.0% of total requests
- **Estimated Additional Savings:** $12/month
- **Energy Saved:** 355.5 kWh/month

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._