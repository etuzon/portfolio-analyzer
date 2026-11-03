"""Independent analytic and grid checks for constrained mean–variance models."""
from types import SimpleNamespace

import numpy as np
import pytest

from app import optimization
from app.optimization import OptimizationError, portfolio_metrics, solve_portfolio


MU = np.array([0.08, 0.14])
COV = np.array([[0.04, 0.01], [0.01, 0.09]])


def assert_feasible(solution, n, cap=1.0):
    weights = np.array(solution["weights"])
    assert weights.shape == (n,)
    assert weights.sum() == pytest.approx(1, abs=1e-10)
    assert weights.min() >= -1e-12 and weights.max() <= cap + 1e-10
    assert np.all(np.isfinite(weights))


def test_two_asset_minimum_variance_matches_closed_form():
    result = solve_portfolio(MU, COV, risk_free_rate=0.02)
    solution = result["selected"]
    # (varB-covAB)/(varA+varB-2covAB), not a copied solver output.
    w = (0.09 - 0.01) / (0.04 + 0.09 - 2 * 0.01)
    assert solution["weights"] == pytest.approx([w, 1 - w], abs=1e-7)
    variance = w * w * 0.04 + (1 - w) ** 2 * 0.09 + 2 * w * (1 - w) * 0.01
    expected = 0.08 * w + 0.14 * (1 - w)
    assert solution["expected_return_percent"] == pytest.approx(expected * 100)
    assert solution["volatility_percent"] == pytest.approx(variance ** 0.5 * 100)
    assert solution["sharpe"] == pytest.approx((expected - 0.02) / variance ** 0.5)
    assert_feasible(solution, 2)


def test_binding_concentration_cap():
    solution = solve_portfolio(MU, COV, max_weight=0.6)["selected"]
    assert solution["weights"] == pytest.approx([0.6, 0.4], abs=1e-7)
    assert_feasible(solution, 2, 0.6)


def test_exact_equal_weight_cap_remains_feasible_for_all_objectives():
    for objective in ["min_variance", "max_sharpe", "target_return"]:
        result = solve_portfolio(MU, COV, objective=objective, max_weight=0.5, target_return=0.10)
        assert result["status"] == "ok"
        assert result["selected"]["weights"] == pytest.approx([0.5, 0.5])
        assert len(result["frontier"]) == 1


def test_target_is_minimum_bound_and_higher_target_changes_weights():
    low = solve_portfolio(MU, COV, objective="target_return", target_return=0.01)
    assert low["selected"] == low["minimum_variance"]
    high = solve_portfolio(MU, COV, objective="target_return", target_return=0.12)
    assert high["selected"]["weights"] == pytest.approx([1 / 3, 2 / 3], abs=1e-7)
    assert high["selected"]["expected_return_percent"] == pytest.approx(12)


def test_infeasible_targets_or_caps_never_emit_selected_weights():
    impossible_cap = solve_portfolio(MU, COV, max_weight=0.49)
    assert impossible_cap["status"] == "unavailable"
    assert impossible_cap["reason"] == "optimization_infeasible_weights"
    assert impossible_cap["selected"] is None
    target = solve_portfolio(MU, COV, objective="target_return", target_return=0.13, max_weight=0.6)
    assert target["reason"] == "optimization_infeasible_target"
    assert target["selected"] is None
    assert target["feasible_return_range"] == pytest.approx({"min_percent": 10.4, "max_percent": 11.6})


def test_analytic_interior_maximum_sharpe_and_risk_free_change():
    for rf in [0.0, 0.02, 0.06]:
        unnormalized = np.linalg.solve(COV, MU - rf)
        expected_weights = unnormalized / unnormalized.sum()
        result = solve_portfolio(MU, COV, objective="max_sharpe", risk_free_rate=rf)
        assert result["selected"]["weights"] == pytest.approx(expected_weights, abs=2e-6)
        assert result["selected"]["sharpe"] > 0
    assert solve_portfolio(MU, COV, objective="max_sharpe", risk_free_rate=0.02)["selected"]["weights"] == pytest.approx([0.5, 0.5], abs=2e-6)


def test_nonpositive_feasible_excess_return_is_explained():
    result = solve_portfolio(MU, COV, objective="max_sharpe", risk_free_rate=0.14)
    assert result["reason"] == "optimization_no_positive_excess_return"
    assert result["selected"] is None


def test_positive_excess_that_requires_shorting_is_not_treated_as_feasible():
    result = solve_portfolio([0.01, 0.1], np.diag([0.01, 0.04]), objective="max_sharpe", max_weight=0.5, risk_free_rate=0.06)
    assert result["reason"] == "optimization_no_positive_excess_return"


def test_zero_covariance_has_no_fabricated_sharpe_or_frontier():
    for objective in ["min_variance", "max_sharpe", "target_return"]:
        result = solve_portfolio(MU, np.zeros((2, 2)), objective=objective, target_return=0.1)
        assert result["reason"] == "optimization_degenerate_covariance"
        assert result["selected"] is None and result["frontier"] == []


def test_singular_identical_risks_selects_highest_return_equal_risk_point():
    result = solve_portfolio(MU, [[0.04, 0.04], [0.04, 0.04]])
    assert result["covariance_status"] == "singular"
    assert result["selected"]["weights"] == pytest.approx([0, 1])
    assert len(result["frontier"]) == 1
    assert result["frontier"][0]["volatility_percent"] == pytest.approx(20)


def test_zero_variance_hedge_stays_unregularized_and_has_no_finite_sharpe():
    cov = [[0.04, -0.04], [-0.04, 0.04]]
    minimum = solve_portfolio(MU, cov)
    assert minimum["selected"]["weights"] == pytest.approx([0.5, 0.5])
    assert minimum["selected"]["volatility_percent"] == pytest.approx(0, abs=1e-7)
    assert minimum["selected"]["sharpe"] is None
    result = solve_portfolio(MU, cov, objective="max_sharpe")
    assert result["reason"] == "optimization_zero_risk_excess_return"
    assert result["selected"] is None


def test_singular_zero_risk_portfolio_is_detected_before_ratio_optimization():
    mu = [.14886096968122506, .06759945315401975, .08188060152161536]
    cov = [[.01824244907380337, -.01374228337785342, -.00450016569594995],
           [-.01374228337785342, .026196327710921948, -.012454044333068527],
           [-.00450016569594995, -.012454044333068527, .016954210029018476]]
    # Every row sums to zero. Equal weights therefore have zero risk and a
    # strictly positive excess mean, even if float quadratic products are >0.
    result = solve_portfolio(mu, cov, objective="max_sharpe", risk_free_rate=.02, max_weight=.6, frontier_points=3)
    assert result["status"] == "unavailable"
    assert result["reason"] == "optimization_zero_risk_excess_return"
    assert result["selected"] is None
    assert portfolio_metrics([1 / 3] * 3, mu, cov, .02)["sharpe"] is None


def test_seeded_singular_models_never_publish_false_huge_sharpe_ratios():
    rng = np.random.default_rng(321)
    for n in [3, 5, 10, 30]:
        for _ in range(30):
            factor = rng.normal(size=(n - 1, n))
            factor -= factor.mean(axis=1, keepdims=True)
            cov = factor.T @ factor * .01
            mu = rng.uniform(.04, .15, n)
            equal = np.ones(n) / n
            assert np.linalg.norm(factor @ equal) < 1e-14
            result = solve_portfolio(mu, cov, objective="max_sharpe", risk_free_rate=.02,
                                     max_weight=.6 if n < 10 else .3, frontier_points=3)
            assert result["reason"] == "optimization_zero_risk_excess_return"
            assert result["selected"] is None
            assert portfolio_metrics(equal, mu, cov, .02)["sharpe"] is None


def test_singular_covariance_without_feasible_long_only_null_portfolio_is_usable():
    # Null vector (2,-1) requires a short position. No capped long-only
    # fully invested portfolio can remove the common factor's risk.
    result = solve_portfolio([.08, .14], [[.01, .02], [.02, .04]], objective="max_sharpe", risk_free_rate=.02)
    assert result["status"] == "ok"
    assert result["covariance_status"] == "singular"
    assert result["selected"]["sharpe"] == pytest.approx(.6)


def test_null_portfolio_with_nonpositive_excess_does_not_block_finite_maximum():
    # First asset has zero variance and no excess return. The second asset
    # supplies positive excess at positive risk; its finite optimum is valid.
    result = solve_portfolio([.01, .10], [[0, 0], [0, .04]], objective="max_sharpe", risk_free_rate=.02)
    assert result["status"] == "ok"
    assert result["selected"]["weights"] == pytest.approx([0, 1])
    assert result["selected"]["sharpe"] == pytest.approx(.4)


def test_equal_expected_returns_produces_one_frontier_point():
    result = solve_portfolio([0.1, 0.1], COV)
    assert len(result["frontier"]) == 1
    assert result["frontier"][0]["expected_return_percent"] == pytest.approx(10)


def test_frontier_upper_branch_is_feasible_and_monotone():
    mu = np.array([0.04, 0.11, 0.19])
    cov = np.array([[0.01, 0.002, -0.001], [0.002, 0.04, 0.01], [-0.001, 0.01, 0.09]])
    result = solve_portfolio(mu, cov, max_weight=0.6, frontier_points=15)
    assert len(result["frontier"]) == 15
    assert result["frontier"][0]["weights"] == result["minimum_variance"]["weights"]
    returns = [point["expected_return_percent"] for point in result["frontier"]]
    vol = [point["volatility_percent"] for point in result["frontier"]]
    assert all(a <= b + 1e-6 for a, b in zip(returns, returns[1:]))
    assert all(a <= b + 1e-6 for a, b in zip(vol, vol[1:]))
    assert returns[-1] == pytest.approx(0.6 * 19 + 0.4 * 11)
    for point in result["frontier"]:
        assert_feasible(point, 3, 0.6)
        assert point["expected_return_percent"] >= point["target_return_percent"] - 1e-6


def test_maximum_return_endpoint_minimizes_risk_with_tied_top_means():
    result = solve_portfolio([0.1, 0.1, 0.02], np.diag([0.01, 0.09, 0.04]), objective="target_return", target_return=0.1)
    assert result["selected"]["weights"] == pytest.approx([0.9, 0.1, 0], abs=2e-6)
    assert result["selected"]["expected_return_percent"] == pytest.approx(10)


def test_random_two_asset_solutions_dominate_independent_dense_grid():
    rng = np.random.default_rng(67821)
    for _ in range(12):
        data = rng.normal(size=(2, 2))
        cov = data @ data.T * 0.02 + np.eye(2) * 0.01
        mu = rng.uniform(0.03, 0.25, 2)
        cap = rng.uniform(0.55, 1)
        grid_x = np.linspace(1 - cap, cap, 10001)
        weights = np.column_stack((grid_x, 1 - grid_x))
        variances = np.einsum("ij,jk,ik->i", weights, cov, weights)
        solution = solve_portfolio(mu, cov, max_weight=cap, frontier_points=3)["selected"]
        assert (solution["volatility_percent"] / 100) ** 2 <= variances.min() + 1e-9
        sharpe = solve_portfolio(mu, cov, objective="max_sharpe", max_weight=cap, risk_free_rate=0.01, frontier_points=3)["selected"]
        grid_sharpe = (weights @ mu - 0.01) / np.sqrt(variances)
        assert sharpe["sharpe"] >= grid_sharpe.max() - 1e-7
        assert_feasible(sharpe, 2, cap)


def test_three_asset_target_solution_beats_feasible_grid():
    mu = np.array([0.04, 0.10, 0.18])
    cov = np.array([[0.015, 0.002, -0.001], [0.002, 0.04, 0.01], [-0.001, 0.01, 0.09]])
    solution = solve_portfolio(mu, cov, objective="target_return", target_return=0.12, max_weight=0.6)["selected"]
    variances = []
    for a in np.linspace(0, 0.6, 301):
        for b in np.linspace(max(0, 0.4 - a), min(0.6, 1 - a), 151):
            w = np.array([a, b, 1 - a - b])
            if min(w) >= 0 and max(w) <= 0.6 and w @ mu >= 0.12:
                variances.append(w @ cov @ w)
    assert (solution["volatility_percent"] / 100) ** 2 <= min(variances) + 1e-8


@pytest.mark.parametrize("kwargs,code", [
    ({"objective": []}, "optimization_invalid_objective"),
    ({"objective": "guess"}, "optimization_invalid_objective"),
    ({"max_weight": True}, "optimization_invalid_weight"),
    ({"max_weight": 0}, "optimization_invalid_weight"),
    ({"max_weight": 1.1}, "optimization_invalid_weight"),
    ({"risk_free_rate": float("nan")}, "optimization_invalid_inputs"),
    ({"risk_free_rate": True}, "optimization_invalid_inputs"),
    ({"target_return": float("inf")}, "optimization_invalid_inputs"),
    ({"objective": "target_return"}, "optimization_target_required"),
    ({"frontier_points": True}, "optimization_invalid_frontier"),
    ({"frontier_points": 1}, "optimization_invalid_frontier"),
    ({"frontier_points": 52}, "optimization_invalid_frontier"),
])
def test_invalid_controls_are_explicit(kwargs, code):
    with pytest.raises(OptimizationError, match=f"^{code}$"):
        solve_portfolio(MU, COV, **kwargs)


@pytest.mark.parametrize("mu,cov,code", [
    ([0.1], [[0.1]], "optimization_invalid_dimensions"),
    ([0.1] * 31, np.eye(31), "optimization_invalid_dimensions"),
    ([0.1, 0.2], [[0.1]], "optimization_invalid_dimensions"),
    ([True, 0.2], COV, "optimization_invalid_inputs"),
    ([0.1, float("nan")], COV, "optimization_invalid_inputs"),
    (MU, [[1, 2], [2, 1]], "optimization_invalid_covariance"),
    (MU, [[1, 0.2], [0.1, 1]], "optimization_invalid_covariance"),
    (MU, [[float("inf"), 0], [0, 1]], "optimization_invalid_inputs"),
    (MU, [[True, 0], [0, 1]], "optimization_invalid_inputs"),
    (None, COV, "optimization_invalid_inputs"),
])
def test_invalid_model_inputs_are_rejected(mu, cov, code):
    with pytest.raises(OptimizationError, match=f"^{code}$"):
        solve_portfolio(mu, cov)


def test_failed_solver_or_infeasible_success_never_returns_last_iterate(monkeypatch):
    monkeypatch.setattr(optimization, "minimize", lambda *a, **k: SimpleNamespace(success=False, x=np.array([0.5, 0.5])))
    with pytest.raises(OptimizationError, match="optimization_solver_failed"):
        solve_portfolio(MU, COV)
    monkeypatch.setattr(optimization, "minimize", lambda *a, **k: SimpleNamespace(success=True, x=np.array([0.9, 0.1])))
    with pytest.raises(OptimizationError, match="optimization_solver_failed"):
        solve_portfolio(MU, COV, max_weight=0.6)


def test_success_flag_without_optimality_is_not_enough(monkeypatch):
    monkeypatch.setattr(optimization, "minimize", lambda *a, **k: SimpleNamespace(success=True, x=np.array([0.1, 0.9])))
    with pytest.raises(OptimizationError, match="optimization_solver_failed"):
        solve_portfolio(MU, COV)


def test_solver_exception_is_sanitized(monkeypatch):
    def fail(*a, **k): raise RuntimeError("Solver internal diagnostic")
    monkeypatch.setattr(optimization, "minimize", fail)
    with pytest.raises(OptimizationError, match="^optimization_solver_failed$"):
        solve_portfolio(MU, COV)


def test_reported_metrics_keep_supplied_covariance_scale():
    for scale in [1e-12, 1, 1e12]:
        result = solve_portfolio(MU, COV * scale, frontier_points=3)
        assert result["selected"]["weights"] == pytest.approx([8 / 11, 3 / 11], abs=1e-7)
        metrics = portfolio_metrics(result["selected"]["weights"], MU, COV * scale)
        assert metrics == result["selected"]
        assert result["selected"]["volatility_percent"] == pytest.approx(17.837651700316894 * scale ** 0.5)
