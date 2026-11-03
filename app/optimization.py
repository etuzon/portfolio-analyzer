"""Constrained mean–variance portfolios from explicit annual model inputs.

The model is long-only and fully invested. No cash, prices, portfolio records,
or external services are read or changed here. Rates enter as decimal annual
quantities; reported return and volatility are percentages.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog, lsq_linear, minimize


MAX_ASSETS = 30
OBJECTIVES = {"min_variance", "max_sharpe", "target_return"}
# Relative numerical rank threshold, shared by covariance classification,
# null-space feasibility checks, and the decision to report a finite Sharpe.
COVARIANCE_ZERO_TOL = 1e-12


class OptimizationError(ValueError):
    """A public error code; solver internals never enter user-facing errors."""


def _scalar(value, code="optimization_invalid_inputs"):
    if isinstance(value, (bool, np.bool_)):
        raise OptimizationError(code)
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise OptimizationError(code) from None
    if not math.isfinite(number) or abs(number) > 1e12:
        raise OptimizationError(code)
    return number


def _inputs(expected_returns, covariance):
    try:
        if isinstance(expected_returns, (str, bytes)) or isinstance(covariance, (str, bytes)):
            raise ValueError
        mu = np.asarray([_scalar(x) for x in expected_returns], dtype=float)
        rows = [[_scalar(x) for x in row] for row in covariance]
        cov = np.asarray(rows, dtype=float)
    except (ValueError, TypeError, OverflowError):
        raise OptimizationError("optimization_invalid_inputs") from None
    n = len(mu)
    if not 2 <= n <= MAX_ASSETS or mu.shape != (n,) or cov.shape != (n, n):
        raise OptimizationError("optimization_invalid_dimensions")
    scale = float(np.max(np.abs(cov)))
    if scale == 0:
        return mu, cov, 0.0, "singular"
    if float(np.max(np.abs(cov - cov.T))) > scale * 1e-10:
        raise OptimizationError("optimization_invalid_covariance")
    # Average symmetric roundoff only, without a ridge or statistical shrinkage.
    cov = (cov + cov.T) * 0.5
    eigenvalues = np.linalg.eigvalsh(cov)
    if float(eigenvalues[0]) < -scale * 1e-10:
        raise OptimizationError("optimization_invalid_covariance")
    state = "singular" if float(eigenvalues[0]) <= scale * COVARIANCE_ZERO_TOL else "positive_definite"
    return mu, cov, scale, state


def portfolio_metrics(weights, expected_returns, covariance, risk_free_rate=0.0):
    """Model metrics, recomputed from the supplied covariance without a ridge."""
    w, mu, cov = np.asarray(weights, dtype=float), np.asarray(expected_returns, dtype=float), np.asarray(covariance, dtype=float)
    variance = float(w @ cov @ w)
    scale = float(np.max(np.abs(cov)))
    if not math.isfinite(variance) or variance < -max(scale, 1e-300) * 1e-10:
        raise OptimizationError("optimization_solver_failed")
    volatility = math.sqrt(max(variance, 0.0))
    expected = float(mu @ w)
    # Cancellation in a singular quadratic form can leave a tiny positive
    # variance. Preserve its computed volatility but do not divide by numerical
    # noise and publish an enormous, apparently finite Sharpe ratio.
    sharpe = (expected - risk_free_rate) / volatility if variance > scale * COVARIANCE_ZERO_TOL else None
    return {"weights": [float(x) for x in w], "expected_return_percent": expected * 100,
            "volatility_percent": volatility * 100, "sharpe": float(sharpe) if sharpe is not None else None}


def _extreme(mu, cap, *, maximum=True):
    order = sorted(range(len(mu)), key=lambda i: (-mu[i] if maximum else mu[i], i))
    w = np.zeros(len(mu))
    remaining = 1.0
    for i in order:
        w[i] = min(cap, remaining)
        remaining = max(0.0, remaining - w[i])
    return w


def _positive_excess_null_portfolio(mu, cov, cap, rf):
    """Whether a feasible numerically zero-risk portfolio has positive excess.

    Positive-eigenvalue projections must be zero. This is a linear feasibility
    problem over fully invested, capped, long-only weights, so it establishes
    the unbounded-ratio case before a fractional optimizer can mistake roundoff
    risk for a large finite optimum.
    """
    eigenvalues, vectors = np.linalg.eigh(cov)
    directions = vectors[:, eigenvalues > COVARIANCE_ZERO_TOL].T
    if len(directions) == len(mu):
        return False
    excess = mu - rf
    objective_scale = max(float(np.max(np.abs(excess))), 1e-12)
    result = linprog(-excess / objective_scale,
                     A_eq=np.vstack((np.ones(len(mu)), directions)),
                     b_eq=np.concatenate(([1.0], np.zeros(len(directions)))),
                     bounds=[(0.0, cap)] * len(mu), method="highs",
                     options={"primal_feasibility_tolerance": 1e-9, "dual_feasibility_tolerance": 1e-9})
    if result.status == 2:  # No fully invested long-only portfolio in the null space.
        return False
    if not result.success or result.x is None:
        raise OptimizationError("optimization_solver_failed")
    w = _clean_weights(result.x, [(0.0, cap)] * len(mu), mu, None)
    if directions.size and float(np.max(np.abs(directions @ w))) > 1e-8:
        raise OptimizationError("optimization_solver_failed")
    return float(excess @ w) > 1e-12


def _endpoint_bounds(mu, cap):
    """Exact maximum-return face, avoiding a redundant active return constraint."""
    bounds = [(0.0, 0.0)] * len(mu)
    remaining = 1.0
    for value in sorted(set(mu.tolist()), reverse=True):
        group = np.flatnonzero(mu == value)
        if remaining <= 1e-12:
            break
        capacity = len(group) * cap
        if remaining >= capacity - 1e-12:
            for i in group:
                bounds[i] = (cap, cap)
            remaining = max(0.0, remaining - capacity)
        else:
            for i in group:
                bounds[i] = (0.0, cap)
            break
    return bounds


def _linear_minimum(coefficients, mu, target, bounds):
    result = linprog(coefficients, A_eq=np.ones((1, len(mu))), b_eq=[1.0],
                     A_ub=None if target is None else [-mu],
                     b_ub=None if target is None else [-target], bounds=bounds, method="highs")
    if not result.success or result.x is None or not np.all(np.isfinite(result.x)):
        raise OptimizationError("optimization_solver_failed")
    return result.x


def _clean_weights(weights, bounds, mu, target):
    w = np.asarray(weights, dtype=float).copy()
    if w.shape != mu.shape or not np.all(np.isfinite(w)):
        raise OptimizationError("optimization_solver_failed")
    low, high = np.array(bounds).T
    if np.min(w - low) < -1e-7 or np.min(high - w) < -1e-7 or abs(float(w.sum()) - 1) > 1e-7:
        raise OptimizationError("optimization_solver_failed")
    w = np.clip(w, low, high)
    # Reconcile only floating-point dust. Do not normalize away a violated cap.
    remaining = 1.0 - float(w.sum())
    for i in range(len(w)):
        change = min(remaining, high[i] - w[i]) if remaining > 0 else max(remaining, low[i] - w[i])
        w[i] += change
        remaining -= change
        if abs(remaining) < 1e-14:
            break
    if abs(float(w.sum()) - 1) > 1e-10:
        raise OptimizationError("optimization_solver_failed")
    if target is not None and float(mu @ w) < target - 1e-8:
        raise OptimizationError("optimization_solver_failed")
    return w


def _tie_break(w, mu, cov, bounds, target):
    """Select highest mean among equal-risk optima when covariance is singular."""
    eigenvalues, vectors = np.linalg.eigh(cov)
    positive = eigenvalues > float(np.max(np.abs(cov))) * COVARIANCE_ZERO_TOL
    if bool(np.all(positive)):
        return w
    directions = vectors[:, positive].T
    result = linprog(-mu, A_eq=np.vstack((np.ones(len(mu)), directions)),
                     b_eq=np.concatenate(([1.0], directions @ w)),
                     A_ub=None if target is None else [-mu], b_ub=None if target is None else [-target],
                     bounds=bounds, method="highs")
    if result.success and result.x is not None:
        candidate = _clean_weights(result.x, bounds, mu, target)
        # Never call a materially different variance an equal-risk tie.
        if abs(float(candidate @ cov @ candidate - w @ cov @ w)) <= 1e-10:
            return candidate
    return w


def _minimum_variance(mu, cov, cap, target=None, max_return=None):
    bounds = [(0.0, cap)] * len(mu)
    actual_target = target
    if target is not None and max_return is not None and abs(target - max_return) <= 1e-12:
        bounds = _endpoint_bounds(mu, cap)
        actual_target = None
    free = [i for i, (low, high) in enumerate(bounds) if high - low > 1e-14]
    if len(free) <= 1:
        w = np.array([low for low, _ in bounds])
        if free:
            w[free[0]] = 1.0 - float(w.sum())
        return _clean_weights(w, bounds, mu, target)
    initial = _linear_minimum(np.zeros(len(mu)), mu, actual_target, bounds)
    constraints = [{"type": "eq", "fun": lambda w: float(w.sum() - 1), "jac": lambda w: np.ones(len(mu))}]
    if actual_target is not None:
        mean_scale = max(float(np.max(np.abs(mu))), abs(actual_target), 1e-8)
        constraints.append({"type": "ineq", "fun": lambda w: float((mu @ w - actual_target) / mean_scale),
                            "jac": lambda w: mu / mean_scale})
    result = minimize(lambda w: float(w @ cov @ w), initial, jac=lambda w: 2 * cov @ w,
                      method="SLSQP", bounds=bounds, constraints=constraints,
                      options={"ftol": 1e-12, "maxiter": 1500})
    if not result.success:
        raise OptimizationError("optimization_solver_failed")
    w = _clean_weights(result.x, bounds, mu, target)
    # For a convex quadratic, this linear directional gap certifies global
    # first-order stationarity over the same feasible polytope.
    gradient = 2 * cov @ w
    certificate = _linear_minimum(gradient, mu, actual_target, bounds)
    gap = float(gradient @ (w - certificate))
    if gap > 2e-6 * max(1.0, abs(float(w @ cov @ w))):
        raise OptimizationError("optimization_solver_failed")
    return _tie_break(w, mu, cov, bounds, actual_target)


def _maximum_sharpe(mu, cov, cap, rf, max_weights):
    excess = mu - rf
    scale = float(np.max(np.abs(excess)))
    direction = excess / scale
    # Convex homogenization: w=z/sum(z), direction'z=1. Position caps
    # become cap*sum(z)-z_i >= 0. This avoids a local ratio optimization.
    initial = max_weights / float(direction @ max_weights)
    constraints = [
        {"type": "eq", "fun": lambda z: float(direction @ z - 1), "jac": lambda z: direction},
        {"type": "ineq", "fun": lambda z: cap * z.sum() - z,
         "jac": lambda z: cap * np.ones((len(mu), len(mu))) - np.eye(len(mu))},
    ]
    result = minimize(lambda z: float(z @ cov @ z), initial, jac=lambda z: 2 * cov @ z,
                      method="SLSQP", bounds=[(0.0, None)] * len(mu), constraints=constraints,
                      options={"ftol": 1e-12, "maxiter": 1500})
    if not result.success or result.x is None or not np.all(np.isfinite(result.x)):
        raise OptimizationError("optimization_solver_failed")
    z = result.x
    total = float(z.sum())
    if total <= 0 or abs(float(direction @ z) - 1) > 1e-7 or np.min(z) < -1e-7:
        raise OptimizationError("optimization_solver_failed")
    w = _clean_weights(z / total, [(0.0, cap)] * len(mu), mu, None)
    # Nonnegative active inequality multipliers and one free equality
    # multiplier provide a scaled KKT residual for the convex problem.
    columns = []
    for i in range(len(mu)):
        if z[i] <= 1e-7 * max(total, 1):
            unit = np.zeros(len(mu)); unit[i] = -1
            columns.append(unit)
        if cap * total - z[i] <= 1e-7 * max(total, 1):
            column = -cap * np.ones(len(mu)); column[i] += 1
            columns.append(column)
    columns.append(direction)
    gradient = 2 * cov @ z
    multipliers = lsq_linear(np.column_stack(columns), -gradient,
                             bounds=([0.0] * (len(columns) - 1) + [-np.inf], [np.inf] * len(columns)), tol=1e-12)
    if np.linalg.norm(multipliers.fun, ord=np.inf) > 2e-5 * max(1.0, float(np.linalg.norm(gradient, ord=np.inf))):
        raise OptimizationError("optimization_solver_failed")
    return w


def solve_portfolio(expected_returns, covariance, *, objective="min_variance", max_weight=1.0,
                    risk_free_rate=0.0, target_return=None, frontier_points=21):
    """Return constrained weights and the efficient upper frontier.

    Target return is a lower bound, so a target below the global minimum-
    variance portfolio's return keeps that portfolio. Maximum Sharpe requires
    a positive feasible excess return and a finite, nonzero-risk solution.
    """
    mu, cov, scale, covariance_status = _inputs(expected_returns, covariance)
    if not isinstance(objective, str) or objective not in OBJECTIVES:
        raise OptimizationError("optimization_invalid_objective")
    cap = _scalar(max_weight, "optimization_invalid_weight")
    if not 0 < cap <= 1:
        raise OptimizationError("optimization_invalid_weight")
    rf = _scalar(risk_free_rate)
    target = _scalar(target_return) if target_return is not None else None
    if objective == "target_return" and target is None:
        raise OptimizationError("optimization_target_required")
    if type(frontier_points) is not int or not 2 <= frontier_points <= 51:
        raise OptimizationError("optimization_invalid_frontier")
    result = {"status": "unavailable", "selected": None, "minimum_variance": None,
              "frontier": [], "feasible_return_range": None, "covariance_status": covariance_status}
    if len(mu) * cap < 1 - 1e-12:
        return {**result, "reason": "optimization_infeasible_weights"}
    max_weights, min_weights = _extreme(mu, cap), _extreme(mu, cap, maximum=False)
    highest, lowest = float(mu @ max_weights), float(mu @ min_weights)
    result["feasible_return_range"] = {"min_percent": lowest * 100, "max_percent": highest * 100}
    if scale == 0:
        return {**result, "reason": "optimization_degenerate_covariance"}
    if objective == "target_return" and target > highest + 1e-10:
        return {**result, "reason": "optimization_infeasible_target"}
    if objective == "max_sharpe" and highest <= rf + 1e-12:
        return {**result, "reason": "optimization_no_positive_excess_return"}
    scaled_cov = cov / scale
    try:
        if objective == "max_sharpe" and covariance_status == "singular" \
                and _positive_excess_null_portfolio(mu, scaled_cov, cap, rf):
            return {**result, "reason": "optimization_zero_risk_excess_return"}
        minimum = _minimum_variance(mu, scaled_cov, cap, max_return=highest)
        minimum_metrics = portfolio_metrics(minimum, mu, cov, rf)
        result["minimum_variance"] = minimum_metrics
        if objective == "min_variance" or objective == "target_return" and target <= float(mu @ minimum) + 1e-12:
            selected = minimum
        elif objective == "target_return":
            selected = _minimum_variance(mu, scaled_cov, cap, target=min(target, highest), max_return=highest)
        else:
            selected = _maximum_sharpe(mu, scaled_cov, cap, rf, max_weights)
            if portfolio_metrics(selected, mu, cov, rf)["sharpe"] is None:
                return {**result, "reason": "optimization_zero_risk_excess_return"}
        result["selected"] = portfolio_metrics(selected, mu, cov, rf)
        lower = float(mu @ minimum)
        targets = [lower] if highest - lower <= 1e-12 else np.linspace(lower, highest, frontier_points)
        for index, point_target in enumerate(targets):
            point = minimum if index == 0 else _minimum_variance(mu, scaled_cov, cap, target=float(point_target), max_return=highest)
            result["frontier"].append({"id": f"frontier-{index}", "target_return_percent": float(point_target) * 100,
                                       **portfolio_metrics(point, mu, cov, rf)})
    except OptimizationError:
        raise
    except Exception as exc:
        raise OptimizationError("optimization_solver_failed") from exc
    result["status"] = "ok"
    return result
