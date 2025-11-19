import gym
from gym import spaces
import numpy as np
from environment.portfolio import Portfolio

from environment.portfolio import Portfolio
from environment.rewards import RewardFunction


class TradingEnvironment(gym.Env):
    """
    Weekly stock selection environment
    """

    def __init__(self, config):
        super().__init__()

        self.config = config
        self.data_manager = config["data_manager"]
        self.feature_pipeline = config["feature_pipeline"]
        self.universe_manager = config["universe_manager"]

        # Episode parameters
        self.start_date = config["start_date"]
        self.end_date = config["end_date"]
        self.rebalance_freq = config["rebalance_freq"]  # 'weekly'

        # Portfolio parameters
        self.initial_capital = config["initial_capital"]
        self.transaction_cost_bps = config["transaction_cost_bps"]
        self.max_position_size = config["max_position_size"]

        # State: features for all stocks in universe
        self.n_features = config["n_features"]
        self.max_stocks = config["max_stocks"]

        # Action space: either discrete (select top k) or continuous (weights)
        if config["action_type"] == "discrete":
            self.action_space = spaces.MultiDiscrete(
                [self.max_stocks] * config["portfolio_size"]
            )
        else:
            self.action_space = spaces.Box(
                low=0, high=1, shape=(self.max_stocks,), dtype=np.float32
            )

        # Observation space: feature matrix
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.max_stocks, self.n_features),
            dtype=np.float32,
        )

        self.portfolio = None
        self.current_date = None
        self.trading_dates = None
        self.date_idx = 0

    def reset(self):
        """Reset environment to start of episode"""
        self.portfolio = Portfolio(self.initial_capital)
        self.trading_dates = self._get_trading_dates()
        self.date_idx = 0
        self.current_date = self.trading_dates[0]

        return self._get_observation()

    def step(self, action):
        """
        Execute one trading step

        Args:
            action: Stock selection/weights

        Returns:
            observation, reward, done, info
        """
        # Get current universe
        universe = self.universe_manager.get_universe_at_date(self.current_date)

        # Convert action to target portfolio
        target_weights = self._action_to_weights(action, universe)

        # Execute rebalancing with transaction costs
        transaction_cost = self.portfolio.rebalance(
            target_weights, self.current_date, self.transaction_cost_bps
        )

        # Move to next period
        self.date_idx += 1
        next_date = self.trading_dates[self.date_idx]

        # Get returns for holding period
        period_return = self.portfolio.update_to_date(next_date)

        # Compute reward
        reward = self._compute_reward(period_return, transaction_cost)

        # Update state
        self.current_date = next_date
        done = self.date_idx >= len(self.trading_dates) - 1

        obs = self._get_observation()
        info = {
            "date": self.current_date,
            "portfolio_value": self.portfolio.total_value,
            "return": period_return,
            "transaction_cost": transaction_cost,
            "sharpe": self.portfolio.compute_sharpe(),
        }

        return obs, reward, done, info

    def _get_observation(self) -> np.ndarray:
        """
        Construct state observation
        Returns feature matrix for all stocks in current universe
        """
        universe = self.universe_manager.get_universe_at_date(self.current_date)

        features = []
        for ticker in universe[: self.max_stocks]:
            ticker_features = self.feature_pipeline.compute_features(
                ticker, self.current_date
            )
            features.append(ticker_features)

        # Pad if necessary
        while len(features) < self.max_stocks:
            features.append(np.zeros(self.n_features))

        return np.array(features, dtype=np.float32)

    def _compute_reward(self, period_return: float, transaction_cost: float) -> float:
        """
        Compute reward signal
        Options: raw return, Sharpe ratio, risk-adjusted return
        """
        # Simple version: return minus costs
        reward = period_return - transaction_cost

        # Can add risk penalty
        if self.config["penalize_risk"]:
            volatility = self.portfolio.get_recent_volatility()
            reward -= self.config["risk_penalty"] * volatility

        return reward
