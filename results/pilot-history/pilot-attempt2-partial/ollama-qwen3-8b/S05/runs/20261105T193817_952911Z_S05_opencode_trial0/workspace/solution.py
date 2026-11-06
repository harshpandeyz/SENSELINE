import json
import numpy as np
from decimal import Decimal, getcontext
getcontext().prec = 40

def solve(payload: dict) -> dict:
    components = payload.get('components', [])
    correlation_matrix = payload.get('correlation_matrix')
    coverage_factor = payload.get('coverage_factor')
    
    # Validate components
    valid = True
    component_errors = []
    u_list = []
    c_list = []
    
    for comp in components:
        if not ('kind' in comp and 'sensitivity_coefficient' in comp):
            valid = False
            component_errors.append('invalid_component_count')
            continue
        
        kind = comp['kind']
        c = Decimal(str(comp['sensitivity_coefficient']))
        c_list.append(c)
        
        if kind == 'type_a':
            observations = comp.get('observations', [])
            if len(observations) < 2:
                valid = False
                component_errors.append('type_a_requires_two_observations')
                continue
            
            # Calculate standard deviation
            obs_decimals = [Decimal(str(obs)) for obs in observations]
            mean = Decimal(sum(obs_decimals)) / Decimal(len(obs_decimals))
            deviations = [Decimal(abs(obs - mean)) for obs in obs_decimals]
            
            # Sample standard deviation (ddof=1)
            sum_sq_dev = Decimal(sum([d**2 for d in deviations]))
            n = Decimal(len(observations))
            std_dev = (sum_sq_dev / (n - 1)).sqrt()
            
            # Standard uncertainty of the mean
            u = std_dev / n**0.5
            u_list.append(u)
        elif kind == 'type_b_rectangular':
            half_width = comp.get('half_width', 0)
            if half_width < 0:
                valid = False
                component_errors.append('negative_half_width')
                continue
            
            u = Decimal(str(half_width)) / Decimal(3)**0.5
            u_list.append(u)
        else:
            valid = False
            component_errors.append('invalid_component_kind')
            continue
        
    if not valid:
        return {'valid': False, 'reason': component_errors[0] if component_errors else 'unsupported_component_count'}
    
    # Validate correlation matrix
    if correlation_matrix is not None:
        try:
            mat = np.array(correlation_matrix, dtype=np.float64)
            if not np.allclose(mat, mat.T):
                valid = False
                component_errors.append('invalid_correlation_shape')
            elif not np.allclose(np.diag(mat), np.ones_like(np.diag(mat))):
                valid = False
                component_errors.append('invalid_correlation_diagonal')
            elif not np.allclose(mat, np.clip(mat, -1, 1)):
                valid = False
                component_errors.append('invalid_correlation_matrix')
            elif not np.all(np.linalg.eigvalsh(mat) >= -1e-24):
                valid = False
                component_errors.append('non_psd_correlation_matrix')
        except:
            valid = False
            component_errors.append('invalid_correlation_matrix')
    
    if not valid:
        return {'valid': False, 'reason': component_errors[0] if component_errors else 'invalid_correlation_matrix'}
    
    # Calculate uc²
    uc_sq = Decimal(0)
    n = len(c_list)
    
    for i in range(n):
        uc_sq += c_list[i]**2 * u_list[i]**2
        
    if correlation_matrix is not None:
        for i in range(n):
            for j in range(i+1, n):
                rho = Decimal(str(correlation_matrix[i][j]))
                cov = rho * u_list[i] * u_list[j]
                uc_sq += 2 * c_list[i] * c_list[j] * cov
    
    if uc_sq < 0:
        return {'valid': False, 'reason': 'negative_propagated_variance'}
    
    uc = uc_sq.sqrt()
    U = Decimal(str(coverage_factor)) * uc
    
    if coverage_factor <= 0:
        return {'valid': False, 'reason': 'invalid_coverage_factor'}
    
    return {
        'valid': True,
        'standard_uncertainties': [str(u) for u in u_list],
        'combined_standard_uncertainty': str(uc),
        'expanded_uncertainty': str(U)
    }