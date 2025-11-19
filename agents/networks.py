import torch
import torch.nn as nn


class PolicyNetwork(nn.Module):
    """
    Policy network for stock selection
    Input: feature matrix (n_stocks x n_features)
    Output: action distribution
    """

    def __init__(self, n_stocks, n_features, hidden_dim=256):
        super().__init__()

        # Per-stock feature encoder
        self.stock_encoder = nn.Sequential(
            nn.Linear(n_features, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Cross-stock attention (optional but recommended)
        self.attention = nn.MultiheadAttention(hidden_dim, num_heads=8)

        # Policy head
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),  # Score per stock
        )

    def forward(self, state):
        """
        Args:
            state: (batch, n_stocks, n_features)
        Returns:
            action_logits: (batch, n_stocks)
        """
        batch_size, n_stocks, n_features = state.shape

        # Encode each stock
        state_flat = state.view(-1, n_features)
        encoded = self.stock_encoder(state_flat)
        encoded = encoded.view(batch_size, n_stocks, -1)

        # Apply attention
        encoded = encoded.transpose(0, 1)  # (n_stocks, batch, hidden)
        attended, _ = self.attention(encoded, encoded, encoded)
        attended = attended.transpose(0, 1)  # (batch, n_stocks, hidden)

        # Get scores
        scores = self.policy_head(attended).squeeze(-1)

        return scores


class ValueNetwork(nn.Module):
    """Value network for critic"""

    def __init__(self, n_stocks, n_features, hidden_dim=256):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(n_stocks * n_features, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, state):
        batch_size = state.shape[0]
        state_flat = state.view(batch_size, -1)
        return self.encoder(state_flat)

    def get_value_network(self, n_stocks, n_features, hidden_dim):
        return ValueNetwork(n_stocks, n_features, hidden_dim)
