"""Versioned, deterministic financial-comparison policy (not a fitted model)."""

OUTLOOK_MODEL_VERSION = "report-outlook-v5"
OUTLOOK_EVALUATION_VERSION = "peer-revenue-margin-v1"
OUTLOOK_FISCAL_ALIGNMENT_DAYS = 120
OUTLOOK_MINIMUM_PEERS = 2
OUTLOOK_MINIMUM_RANK_WEIGHT = 32

# Weights retain their financial proportions; context and evidence counts do
# not add points. Unobserved weights are never redistributed to other metrics.
OUTLOOK_METRICS = (
    ("revenue_growth_percent", 12, 20, False),
    ("net_income_growth_percent", 10, 30, False),
    ("profit_margin_percent", 10, 20, False),
    ("free_cash_flow_margin_percent", 5, 15, False),
    ("debt_to_revenue_percent", 2, 30, True),
    ("current_ratio", 1, 0.8, False),
    ("net_margin_change_percent", 5, 5, False),
)
OUTLOOK_TOTAL_WEIGHT = sum(metric[1] for metric in OUTLOOK_METRICS)


def evaluation_contract() -> dict:
    return {
        "version": OUTLOOK_EVALUATION_VERSION,
        "target": "peer_relative_revenue_growth_and_net_margin",
        "minimum_peers": OUTLOOK_MINIMUM_PEERS,
        "require_full_cohort": True,
        "revenue_tolerance_pp": 1.0,
        "margin_tolerance_pp": 0.5,
        "report_selection": "next_annual",
        "fiscal_alignment_days": OUTLOOK_FISCAL_ALIGNMENT_DAYS,
        "baseline_comparable": True,
    }
