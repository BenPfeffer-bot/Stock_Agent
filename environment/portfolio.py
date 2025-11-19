class Portfolio:
    """Tracks portfolio state and computes returns"""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {ticker: shares}
        self.history = []

    def rebalance(self, target_weights: dict, date: str, cost_bps: float) -> float:
        """
        Rebalance to target weights
        Returns total transaction cost
        """
        pass

    def update_to_date(self, date: str) -> float:
        """
        Update portfolio value to date, return period return
        """
        pass

    def compute_sharpe(self, window: int = 52) -> float:
        """Compute rolling Sharpe ratio"""
        pass
