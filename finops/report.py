"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(
    baseline_usd: float,
    optimized_usd: float,
    levers: dict,
    sustainability: dict | None = None,
    period: str = "monthly",
    unit_economics: dict | None = None,
    extensions: dict | None = None,
) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
    ]

    if unit_economics:
        lines += [
            "## Unit Economics ($/1M-Token)",
            "",
            f"- **Baseline:** ${unit_economics.get('baseline_per_m', 0):.3f} / 1M-token",
            f"- **Optimized:** ${unit_economics.get('optimized_per_m', 0):.3f} / 1M-token",
            f"- **Unit Cost Reduction:** {unit_economics.get('savings_pct', 0):.1f}%",
            "",
        ]

    lines += [
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")

    if extensions:
        if "mbu_rightsizing" in extensions:
            mbu = extensions["mbu_rightsizing"]
            lines += [
                "",
                "## Extension 2: MBU Right-Sizing Analysis",
                "",
                f"- **Total MBU Right-Sizing Monthly Savings:** ${mbu.get('mbu_monthly_savings', 0):,.0f}",
                f"- **Memory-Bound GPUs Right-Sized:** {len(mbu.get('mbu_rightsizing', []))} instances",
            ]
            for r in mbu.get("mbu_rightsizing", []):
                sav_mo = r["hourly_savings"] * 24 * 30
                lines.append(f"  - `{r['gpu_id']}` ({r['current_gpu']}) -> `{r['recommended_gpu']}`: Save ${sav_mo:,.0f}/mo ({r['savings_pct']}%)")

        if "reasoning_governance" in extensions:
            rg = extensions["reasoning_governance"]
            lines += [
                "",
                "## Extension 4: Reasoning Traffic Governance",
                "",
                f"- **Reasoning Traffic Policy:** Cap at {rg.get('target_reasoning_rate_pct', 8)}% of total requests",
                f"- **Estimated Additional Savings:** ${rg.get('monthly_cost_saved', 0):,.0f}/month",
                f"- **Energy Saved:** {rg.get('daily_kwh_saved', 0)*30:,.1f} kWh/month",
            ]

    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd"]
    bars = ax.bar(names, vals, color=colors[:len(names)])
    ax.set_ylabel("Savings (USD / month)", fontsize=11, fontweight="bold")
    ax.set_title("GPU Cost Savings by FinOps Lever (NimbusAI)", fontsize=13, fontweight="bold", pad=15)
    ax.set_ylim(0, max(vals) * 1.15)
    plt.xticks(rotation=15, ha="right", fontsize=10)
    plt.grid(axis="y", linestyle="--", alpha=0.5)


    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"${height:,.0f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path

