import torch
from agents.networks import PolicyNetwork, ValueNetwork
from typing import List


class PPOAgent:
    """PPO implementation for stock selection"""

    def __init__(self, config):
        self.policy = PolicyNetwork(
            config["n_stocks"], config["n_features"], config["hidden_dim"]
        )
        self.value = ValueNetwork(
            config["n_stocks"], config["n_features"], config["hidden_dim"]
        )

        self.policy_optimizer = torch.optim.Adam(
            self.policy.parameters(), lr=config["policy_lr"]
        )
        self.value_optimizer = torch.optim.Adam(
            self.value.parameters(), lr=config["value_lr"]
        )

        self.clip_epsilon = config["clip_epsilon"]
        self.gamma = config["gamma"]
        self.gae_lambda = config["gae_lambda"]

    def select_action(self, state, deterministic=False):
        """Select action given state"""
        with torch.no_grad():
            logits = self.policy(state)
            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                dist = torch.distributions.Categorical(logits=logits)
                action = dist.sample()
        return action

    def update(self, trajectories):
        """Update policy and value networks"""
        # Compute advantages using GAE
        advantages = self._compute_advantages(trajectories)

        # PPO update loop
        for epoch in range(self.config["ppo_epochs"]):
            # Update policy
            policy_loss = self._compute_policy_loss(trajectories, advantages)
            self.policy_optimizer.zero_grad()
            policy_loss.backward()
            torch.nn.utils.clip_grad_norm_(
                self.policy.parameters(), self.config["max_grad_norm"]
            )
            self.policy_optimizer.step()

            # Update value
            value_loss = self._compute_value_loss(trajectories)
            self.value_optimizer.zero_grad()
            value_loss.backward()
            torch.nn.utils.clip_grad_norm_(
                self.value.parameters(), self.config["max_grad_norm"]
            )
            self.value_optimizer.step()
