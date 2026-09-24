"""
Volatility Models & Analytics Engine.
Provides Historical Volatility Estimators (Close-Close, Parkinson, Garman-Klass),
Volatility Smile/Skew Curve analysis, and 3D Volatility Surface Generation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional

TRADING_DAYS = 252.0

def calculate_close_to_close_hv(prices: pd.Series, window: int = 20) -> pd.Series:
    """
    Standard Historical Volatility (Close-to-Close).
    HV = std(log(P_t / P_{t-1})) * sqrt(252)
    """
    log_returns = np.log(prices / prices.shift(1))
    rolling_std = log_returns.rolling(window=window).std()
    return rolling_std * np.sqrt(TRADING_DAYS)

def calculate_parkinson_hv(high: pd.Series, low: pd.Series, window: int = 20) -> pd.Series:
    """
    Parkinson High-Low Volatility estimator (captures intraday extremes).
    HV = sqrt( (1 / (4 * ln(2) * N)) * sum( (ln(H/L))^2 ) ) * sqrt(252)
    """
    log_hl = np.log(high / low) ** 2
    factor = 1.0 / (4.0 * np.log(2.0))
    rolling_variance = log_hl.rolling(window=window).mean() * factor
    return np.sqrt(rolling_variance * TRADING_DAYS)

def calculate_garman_klass_hv(
    open_p: pd.Series, 
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    window: int = 20
) -> pd.Series:
    """
    Garman-Klass Volatility estimator (combines Open, High, Low, Close).
    Captures both intraday range and overnight gap jumps.
    """
    log_hl = 0.5 * (np.log(high / low) ** 2)
    log_co = (2.0 * np.log(2.0) - 1.0) * (np.log(close / open_p) ** 2)
    daily_var = log_hl - log_co
    rolling_var = daily_var.rolling(window=window).mean()
    return np.sqrt(np.maximum(0.0, rolling_var * TRADING_DAYS))

def generate_volatility_surface_mesh(
    strikes: np.ndarray, 
    days_to_expiry: np.ndarray, 
    base_iv: float = 0.18, 
    spot_price: float = 24000.0,
    skew_slope: float = 0.00008,
    convexity: float = 0.00000005,
    term_slope: float = 0.0003
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate 2D meshgrids (Strike, DTE, IV) for 3D Volatility Surface rendering.
    Simulates real market volatility smile + term structure dynamics.
    """
    K_mesh, DTE_mesh = np.meshgrid(strikes, days_to_expiry)
    
    # Moneyness: log(K / S)
    moneyness = np.log(K_mesh / spot_price)
    
    # Typical equity skew: OTM puts (K < S) have higher IV than OTM calls (K > S)
    # Smile curvature: quadratic convexity
    # Term structure: IV typically slopes upward or mean-reverts with maturity
    iv_surface = (
        base_iv 
        - skew_slope * (K_mesh - spot_price)
        + convexity * ((K_mesh - spot_price) ** 2)
        + term_slope * np.sqrt(DTE_mesh)
    )
    
    # Clamp IV to realistic market bounds [0.08, 0.90]
    iv_surface = np.clip(iv_surface, 0.08, 0.90) * 100.0 # Return as percentage
    
    return K_mesh, DTE_mesh, iv_surface

def fit_volatility_smile(df_option_chain: pd.DataFrame, spot_price: float) -> pd.DataFrame:
    """
    Extract and process IV smile from an option chain DataFrame.
    """
    if "strike_price" not in df_option_chain.columns or "implied_volatility" not in df_option_chain.columns:
        return pd.DataFrame()

    df = df_option_chain.copy()
    df["moneyness"] = df["strike_price"] / spot_price
    df["iv_pct"] = df["implied_volatility"] * 100.0 if df["implied_volatility"].max() <= 2.0 else df["implied_volatility"]
    
    return df.sort_values(by="strike_price")
