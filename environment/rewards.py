import numpy as np
from typing import List


class RewardFunction:
    """Flexible reward function definitions"""

    @staticmethod
    def simple_return(portfolio_return: float, transaction_cost: float) -> float:
        return portfolio_return - transaction_cost

    @staticmethod
    def sharpe_ratio(portfolio_history: list) -> float:
        """Reward based on Sharpe ratio"""
        returns = np.array([h["return"] for h in portfolio_history])
        if len(returns) < 2:
            return 0.0
        return np.mean(returns) / (np.std(returns) + 1e-8)

    @staticmethod
    def sortino_ratio(portfolio_history: list) -> float:
        """Penalize downside volatility only"""
        returns = np.array([h["return"] for h in portfolio_history])
        downside = returns[returns < 0]
        if len(downside) == 0:
            return np.mean(returns)
        return np.mean(returns) / (np.std(downside) + 1e-8)
