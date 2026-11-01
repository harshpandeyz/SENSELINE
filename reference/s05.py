"""Known-correct uncertainty calculation, independent of oracle implementation."""
from decimal import Decimal, localcontext
from itertools import combinations
from .common import dec, fmt, invalid


def _det(matrix):
    n = len(matrix)
    if n == 1:
        return matrix[0][0]
    return sum(((-1) ** j) * matrix[0][j] * _det([row[:j] + row[j + 1:] for row in matrix[1:]]) for j in range(n))


def _psd(matrix):
    n = len(matrix)
    for size in range(1, n + 1):
        for indexes in combinations(range(n), size):
            minor = [[matrix[i][j] for j in indexes] for i in indexes]
            if _det(minor) < Decimal("-1e-24"):
                return False
    return True


def solve(payload: dict) -> dict:
    try:
        components = payload["components"]
        n = len(components)
        if not 1 <= n <= 3:
            return invalid("unsupported_component_count")
        uncertainties, sensitivities = [], []
        with localcontext() as ctx:
            ctx.prec = 40
            for component in components:
                kind = component["kind"]
                sensitivity = dec(component["sensitivity"])
                if kind == "type_a":
                    obs = [dec(v) for v in component["observations"]]
                    count = len(obs)
                    if count < 2:
                        return invalid("type_a_requires_two_observations")
                    mean = sum(obs) / Decimal(count)
                    ss = sum(((x - mean) ** 2 for x in obs), Decimal(0))
                    u = (ss / Decimal(count - 1) / Decimal(count)).sqrt()
                elif kind == "type_b_rectangular":
                    half_width = dec(component["half_width"])
                    if half_width < 0:
                        return invalid("negative_half_width")
                    u = half_width / Decimal(3).sqrt()
                else:
                    return invalid("invalid_component_kind")
                if u < 0:
                    return invalid("negative_uncertainty")
                uncertainties.append(u)
                sensitivities.append(sensitivity)
            if "correlation_matrix" in payload:
                corr = [[dec(v) for v in row] for row in payload["correlation_matrix"]]
                if len(corr) != n or any(len(row) != n for row in corr):
                    return invalid("invalid_correlation_shape")
                for i in range(n):
                    if corr[i][i] != 1:
                        return invalid("invalid_correlation_diagonal")
                    for j in range(n):
                        if abs(corr[i][j]) > 1 or corr[i][j] != corr[j][i]:
                            return invalid("invalid_correlation_matrix")
                if not _psd(corr):
                    return invalid("non_psd_correlation_matrix")
            else:
                corr = [[Decimal(int(i == j)) for j in range(n)] for i in range(n)]
            variance = Decimal(0)
            for i in range(n):
                variance += (sensitivities[i] * uncertainties[i]) ** 2
                for j in range(i + 1, n):
                    variance += 2 * sensitivities[i] * sensitivities[j] * corr[i][j] * uncertainties[i] * uncertainties[j]
            if variance < Decimal("-1e-24"):
                return invalid("negative_propagated_variance")
            uc = max(variance, Decimal(0)).sqrt()
            k = dec(payload["coverage_factor"])
            if k <= 0:
                return invalid("invalid_coverage_factor")
            return {"valid": True, "standard_uncertainties": [fmt(x) for x in uncertainties], "combined_standard_uncertainty": fmt(uc), "expanded_uncertainty": fmt(k * uc)}
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return invalid("invalid_parameters")
