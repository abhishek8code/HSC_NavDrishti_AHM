"""
Emission analytics module for calculating CO2 savings from route optimization.
"""

def calculate_emission_savings(time_original: float, time_optimized: float) -> float:
    """
    Calculates CO2 emission savings based on time difference between routes.
    
    Formula: ΔF_j = Δt
    Where:
        ΔF_j = Emission savings (CO2 reduction)
        Δt = Time difference (time_original - time_optimized)
    
    A shorter route (time_optimized < time_original) results in positive CO2 saving
    because Δt > 0, meaning time is saved and emissions are reduced.
    
    Args:
        time_original (float): Travel time for the original route (in hours)
        time_optimized (float): Travel time for the optimized/shorter route (in hours)
    
    Returns:
        float: CO2 emission savings (positive value when shorter route is identified)
               Returns 0 if optimized route is not shorter
    """
    # Validate inputs: negative or zero original time, or negative optimized time are invalid
    if time_original <= 0 or time_optimized < 0:
        return 0.0

    delta_t = time_original - time_optimized

    # Only return positive savings if the optimized route is shorter
    if delta_t > 0:
        # Round to avoid floating-point representation issues in tests
        return round(delta_t, 10)
    else:
        return 0.0  # No savings if route is not shorter

