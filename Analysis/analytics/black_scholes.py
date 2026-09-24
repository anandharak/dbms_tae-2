"""
Black-Scholes-Merton (BSM) Quantitative Analytics Engine.
Calculates theoretical option prices, analytical Greeks (Delta, Gamma, Vega, Theta, Rho),
and numerical Implied Volatility (IV) with Newton-Raphson and Brent/Bisection safeguards.
"""

import math
import numpy as np
from scipy.stats import norm
from typing import Dict, Union, Tuple

# Standard annual trading days
TRADING_DAYS_PER_YEAR = 365.0
RISK_FREE_RATE_DEFAULT = 0.065  # 6.5% standard benchmark rate

def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float]:
    """Calculate d1 and d2 parameters of Black-Scholes formula."""
    if T <= 0.0 or sigma <= 0.0 or S <= 0.0 or K <= 0.0:
        return 0.0, 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(d1), float(d2)

def calculate_option_price(
    S: float, 
    K: float, 
    T: float, 
    r: float = RISK_FREE_RATE_DEFAULT, 
    sigma: float = 0.20, 
    option_type: str = "CE"
) -> float:
    """
    Calculate theoretical option price using Black-Scholes formula.
    S: Spot Price
    K: Strike Price
    T: Time to Expiration in Years
    r: Risk-free Interest Rate (annualized)
    sigma: Volatility (annualized, e.g. 0.20 for 20%)
    option_type: 'CE' (Call) or 'PE' (Put)
    """
    option_type = option_type.upper()
    if T <= 0.0001:
        # At expiration: intrinsic value
        if option_type == "CE":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)

    if sigma <= 0.0:
        sigma = 0.0001

    d1, d2 = _d1_d2(S, K, T, r, sigma)

    if option_type == "CE":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "PE":
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        raise ValueError(f"Unknown option_type '{option_type}'. Must be 'CE' or 'PE'.")

    return max(0.0, float(price))

def calculate_greeks(
    S: float, 
    K: float, 
    T: float, 
    r: float = RISK_FREE_RATE_DEFAULT, 
    sigma: float = 0.20, 
    option_type: str = "CE"
) -> Dict[str, float]:
    """
    Calculate full suite of analytical Greeks.
    Delta: dV/dS (sensitivity to spot price)
    Gamma: d2V/dS2 (sensitivity of delta to spot price)
    Vega:  dV/dSigma (sensitivity to 1% change in IV, expressed per 1.0 vol and per 1% vol)
    Theta: dV/dt (daily time decay of option price)
    Rho:   dV/dr (sensitivity to 1% change in interest rate)
    """
    option_type = option_type.upper()
    if T <= 0.0001 or sigma <= 0.0:
        # Intrinsic boundary conditions
        if option_type == "CE":
            delta = 1.0 if S > K else (0.5 if S == K else 0.0)
        else:
            delta = -1.0 if S < K else (-0.5 if S == K else 0.0)
        return {
            "delta": delta,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0
        }

    d1, d2 = _d1_d2(S, K, T, r, sigma)
    pdf_d1 = norm.pdf(d1)
    sqrt_T = np.sqrt(T)

    # Gamma is identical for Call and Put
    gamma = pdf_d1 / (S * sigma * sqrt_T)

    # Vega is identical for Call and Put (dV / dSigma)
    # Scaled to represent change per 1% change in volatility
    vega_1pct = (S * pdf_d1 * sqrt_T) / 100.0

    if option_type == "CE":
        delta = norm.cdf(d1)
        # Theta annualized, divided by 365 for daily decay
        theta_annual = -(S * pdf_d1 * sigma) / (2 * sqrt_T) - r * K * np.exp(-r * T) * norm.cdf(d2)
        theta_daily = theta_annual / TRADING_DAYS_PER_YEAR
        rho_1pct = (K * T * np.exp(-r * T) * norm.cdf(d2)) / 100.0
    else:
        delta = norm.cdf(d1) - 1.0
        theta_annual = -(S * pdf_d1 * sigma) / (2 * sqrt_T) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        theta_daily = theta_annual / TRADING_DAYS_PER_YEAR
        rho_1pct = (-K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100.0

    return {
        "delta": round(float(delta), 4),
        "gamma": round(float(gamma), 6),
        "theta": round(float(theta_daily), 4),
        "vega": round(float(vega_1pct), 4),
        "rho": round(float(rho_1pct), 4)
    }

def calculate_implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float = RISK_FREE_RATE_DEFAULT,
    option_type: str = "CE",
    max_iterations: int = 100,
    tolerance: float = 1e-5
) -> float:
    """
    Invert Black-Scholes formula to solve for Implied Volatility (IV) given market price.
    Uses Newton-Raphson method with Brent/Bisection bracket fallback.
    Returns annualized volatility as decimal (e.g., 0.225 for 22.5%).
    """
    option_type = option_type.upper()
    if T <= 0.0001 or market_price <= 0.0:
        return 0.0

    # Intrinsic value bounds check
    intrinsic = max(0.0, S - K) if option_type == "CE" else max(0.0, K - S)
    if market_price < intrinsic:
        return 0.01  # Arbitrage floor

    # Initial guess using Brenner-Subrahmanyam approximation
    sigma = np.sqrt(2 * np.pi / T) * (market_price / S) if S > 0 else 0.20
    sigma = max(0.05, min(sigma, 2.5))

    # Newton-Raphson iteration
    for _ in range(max_iterations):
        price = calculate_option_price(S, K, T, r, sigma, option_type)
        diff = price - market_price

        if abs(diff) < tolerance:
            return round(float(sigma), 4)

        d1, _ = _d1_d2(S, K, T, r, sigma)
        vega = S * norm.pdf(d1) * np.sqrt(T)

        if vega < 1e-6:
            break

        sigma -= diff / vega
        if sigma <= 0.001 or sigma > 5.0:
            break

    # Fallback: Binary search / bisection
    low_sigma, high_sigma = 0.001, 5.0
    for _ in range(60):
        mid_sigma = 0.5 * (low_sigma + high_sigma)
        mid_price = calculate_option_price(S, K, T, r, mid_sigma, option_type)
        diff = mid_price - market_price

        if abs(diff) < tolerance:
            return round(float(mid_sigma), 4)

        if diff > 0:
            high_sigma = mid_sigma
        else:
            low_sigma = mid_sigma

    return round(float(0.5 * (low_sigma + high_sigma)), 4)
