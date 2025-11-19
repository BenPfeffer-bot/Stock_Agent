import numpy as np


class Backtester:
    """Backtest trained agent"""

    def __init__(self, env, agent):
        self.env = env
        self.agent = agent

    def run_backtest(self, start_date: str, end_date: str) -> dict:
        """
        Run backtest over date range
        Returns comprehensive performance metrics
        """
        self.env.start_date = start_date
        self.env.end_date = end_date

        state = self.env.reset()
        done = False

        results = {
            "dates": [],
            "portfolio_values": [],
            "returns": [],
            "actions": [],
            "holdings": [],
        }

        while not done:
            action = self.agent.select_action(state, deterministic=True)
            state, reward, done, info = self.env.step(action)

            results["dates"].append(info["date"])
            results["portfolio_values"].append(info["portfolio_value"])
            results["returns"].append(info["return"])
            results["actions"].append(action)

        # Compute metrics
        metrics = self._compute_metrics(results)

        return results, metrics

    def _compute_metrics(self, results: dict) -> dict:
        """Compute performance metrics"""
        returns = np.array(results["returns"])

        return {
            "total_return": np.prod(1 + returns) - 1,
            "sharpe_ratio": np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(52),
            "max_drawdown": self._compute_max_drawdown(results["portfolio_values"]),
            "win_rate": np.sum(returns > 0) / len(returns),
            "avg_return": np.mean(returns),
            "volatility": np.std(returns) * np.sqrt(52),
        }
