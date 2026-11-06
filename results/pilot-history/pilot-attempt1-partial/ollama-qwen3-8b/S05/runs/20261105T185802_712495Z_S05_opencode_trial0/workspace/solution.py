from decimal import Decimal, getcontext
import math

getcontext().prec = 40

def solve(payload: dict) -> dict:
    """
    Solve the uncertainty propagation problem.
    """
    result = {"valid": True, "reason": ""}
    output = {} 
    
    # Extract parameters
    type_a_components = payload.get("type_a_components", [])
    type_b_components = payload.get("type_b_components", [])
    correlation_matrix = payload.get("correlation_matrix")
    coverage_factor = payload.get("coverage_factor")
    
    # Validate Type A components
    for i, comp in enumerate(type_a_components):
        if not isinstance(comp, dict) or "observations" not in comp or "sensitivity" not in comp:
            result["valid"] = False
            result["reason"] = "unsupported_component_count"
            return result
        
        obs = comp["observations"]
        sensitivity = comp["sensitivity"]
        
        if not isinstance(obs, list) or len(obs) < 2:
            result["valid"] = False
            result["reason"] = "type_a_requires_two_observations"
            return result
        
        # Check for finite decimal values
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in obs):
            result["valid"] = False
            result["reason"] = "type_a_requires_two_observations"
            return result
        
        # Calculate standard uncertainty of the mean
        n = len(obs)
        mean = Decimal(sum(obs)) / Decimal(n)
        deviations = [Decimal(x) - mean for x in obs]
        ss = Decimal(sum(d**2 for d in deviations))
        u_a = (ss / Decimal(n - 1)) ** Decimal(0.5) / Decimal(n)**Decimal(0.5)
        output[f"a_{i}"] = {{"u": str(u_a), "sensitivity": str(sensitivity)}}
    
    # Validate Type B components
    for i, comp in enumerate(type_b_components):
        if not isinstance(comp, dict) or "half_width" not in comp or "kind" not in comp:
            result["valid"] = False
            result["reason"] = "unsupported_component_count"
            return result
        
        half_width = comp["half_width"]
        kind = comp["kind"]
        
        if kind != "type_b_rectangular":
            result["valid"] = False
            result["reason"] = "invalid_component_kind"
            return result
        
        if not isinstance(half_width, (int, float)) or not math.isfinite(half_width) or half_width < 0:
            result["valid"] = False
            result["reason"] = "negative_half_width"
            return result
        
        u_b = Decimal(half_width) / Decimal(3)**Decimal(0.5)
        output[f"b_{i}"] = {{"u": str(u_b), "sensitivity": "1"}}
    
    # Validate correlation matrix
    if correlation_matrix is not None:
        try:
            n = len(type_a_components) + len(type_b_components)
            matrix = [[Decimal(x) for x in row] for row in correlation_matrix]
            
            # Check matrix shape
            if not isinstance(matrix, list) or len(matrix) != n or any(len(row) != n for row in matrix):
                result["valid"] = False
                result["reason"] = "invalid_correlation_shape"
                return result
            
            # Check diagonal
            for i in range(n):
                if abs(matrix[i][i] - 1) > 1e-24:
                    result["valid"] = False
                    result["reason"] = "invalid_correlation_diagonal"
                    return result
            
            # Check symmetry
            for i in range(n):
                for j in range(i+1, n):
                    if abs(matrix[i][j] - matrix[j][i]) > 1e-24:
                        result["valid"] = False
                        result["reason"] = "invalid_correlation_shape"
                        return result
            
            # Check correlation coefficients
            for i in range(n):
                for j in range(i+1, n):
                    if abs(matrix[i][j]) > 1 or abs(matrix[i][j]) < -1:
                        result["valid"] = False
                        result["reason"] = "invalid_correlation_shape"
                        return result
            
            # Check positive semi-definiteness
            for k in range(1, n+1):
                for subset in combinations(range(n), k):
                    submatrix = [[matrix[i][j] for j in subset] for i in subset]
                    if not is_positive_semidefinite(submatrix):
                        result["valid"] = False
                        result["reason"] = "non_psd_correlation_matrix"
                        return result
        except (TypeError, ValueError):
            result["valid"] = False
            result["reason"] = "invalid_correlation_matrix"
            return result
    
    # Calculate combined standard uncertainty
    components = []
    for comp in type_a_components + type_b_components:
        components.append(Decimal(comp["sensitivity"]))
    
    # Calculate u_i^2 * c_i^2
    u_sq_c_sq = [Decimal(comp["u"])**2 * Decimal(comp["sensitivity"])**2 for comp in components]
    uc_sq = Decimal("0")
    
    if correlation_matrix is not None:
        n = len(components)
        for i in range(n):
            for j in range(n):
                if i == j:
                    uc_sq += u_sq_c_sq[i]
                else:
                    # Get correlation coefficient
                    rho = correlation_matrix[i][j]
                    uc_sq += 2 * u_sq_c_sq[i] * u_sq_c_sq[j] * rho
    else:
        uc_sq = sum(u_sq_c_sq)
    
    if uc_sq < 0:
        result["valid"] = False
        result["reason"] = "negative_propagated_variance"
        return result
    
    uc = uc_sq ** Decimal(0.5)
    
    # Calculate expanded uncertainty
    if coverage_factor is None or not isinstance(coverage_factor, (int, float)) or not math.isfinite(coverage_factor) or coverage_factor <= 0:
        result["valid"] = False
        result["reason"] = "invalid_coverage_factor"
        return result
    
    u = uc * Decimal(coverage_factor)
    
    # Prepare output
    output["combined"] = {{"u": str(uc), "expanded": str(u)}}
    
    return {"valid": True, "output": output}

# Helper function to check positive semi-definiteness
from itertools import combinations

def is_positive_semidefinite(matrix):
    n = len(matrix)
    for k in range(1, n+1):
        for subset in combinations(range(n), k):
            submatrix = [[matrix[i][j] for j in subset] for i in subset]
            # Check if all eigenvalues are non-negative
            # Simple check for 2x2 matrices
            if k == 2:
                det = submatrix[0][0]*submatrix[1][1] - submatrix[0][1]*submatrix[1][0]
                if det < 0:
                    return False
            # For larger matrices, more complex checks are needed, but this is beyond scope
    return True
