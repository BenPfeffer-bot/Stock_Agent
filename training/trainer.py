import numpy as np
from typing import List
from evaluation.backtester import Backtester
from agents.ppo_agent import PPOAgent
from environment.trading_env import TradingEnvironment

from utils.logging import setup_logging


class Trainer:
    """Main training loop"""

    def __init__(self, env, agent, config):
        self.env = env
        self.agent = agent
        self.config = config

        # Logging
        self.logger = setup_logging(config["log_dir"])
        self.wandb_enabled = config.get("use_wandb", False)

        # Callbacks
        # self.callbacks = [
        #     CheckpointCallback(config["checkpoint_dir"]),
        #     EvaluationCallback(config["eval_env"]),
        #     TensorBoardCallback(config["tb_dir"]),
        # ]

    def train(self, n_episodes: int):
        """Main training loop"""
        for episode in range(n_episodes):
            # Collect trajectories
            trajectories = self._collect_trajectories()

            # Update agent
            metrics = self.agent.update(trajectories)

            # Logging
            self._log_metrics(episode, metrics)

            # Callbacks
            for callback in self.callbacks:
                callback.on_episode_end(episode, metrics)

    def _collect_trajectories(self):
        """Collect rollout data"""
        trajectories = []
        state = self.env.reset()
        done = False

        while not done:
            action = self.agent.select_action(state)
            next_state, reward, done, info = self.env.step(action)

            trajectories.append(
                {
                    "state": state,
                    "action": action,
                    "reward": reward,
                    "next_state": next_state,
                    "done": done,
                    "info": info,
                }
            )

            state = next_state

        return trajectories
