import pandas as pd
import numpy as np
import yfinance as yf

# 1. Download weekly price data

def download_stock_data(tickers, start, end, interval='1wk'):
    data = {}
    for ticker in tickers:
        df = yf.download(ticker, start=start, end=end, interval=interval,
                         auto_adjust=True, progress=False)
        df['Ticker'] = ticker
        data[ticker] = df
    return pd.concat(data.values(), keys=data.keys())

# 2. Compute returns, volatility and momentum

def compute_features(df):
    df = df.copy()
    df['Return'] = df['Close'].pct_change()
    df['Volatility'] = df['Return'].rolling(window=4).std()
    df['Momentum'] = df['Close'].pct_change(periods=4)
    return df.dropna()

# 3. Placeholder for news sentiment

def fetch_news_sentiment(ticker, start_date, end_date):
    idx = pd.date_range(start=start_date, end=end_date, freq='W')
    return pd.Series(0.0, index=idx, name='sentiment')

# The following is a commented example of how you could set up a custom RL environment and train a PPO agent.

# from stable_baselines3 import PPO
# import gym
# from gym import spaces
#
# class StockSelectionEnv(gym.Env):
#     """A simple environment where the agent picks one stock from a universe each week."""
#     def __init__(self, price_data, sentiment_data):
#         super().__init__()
#         self.price_data = price_data
#         self.sentiment_data = sentiment_data
#         self.tickers = list(price_data.keys())
#         self.action_space = spaces.Discrete(len(self.tickers))
#         feature_size = price_data[self.tickers[0]].shape[1]
#         self.observation_space = spaces.Box(-np.inf, np.inf,
#                                             shape=(len(self.tickers), feature_size),
#                                             dtype=np.float32)
#         self.current_step = 0
#
#     def reset(self):
#         self.current_step = 0
#         return self._get_observation()
#
#     def _get_observation(self):
#         obs = []
#         for ticker in self.tickers:
#             obs.append(self.price_data[ticker].iloc[self.current_step].values)
#         return np.array(obs, dtype=np.float32)
#
#     def step(self, action):
#         chosen_ticker = self.tickers[action]
#         reward = self.price_data[chosen_ticker].iloc[self.current_step + 1]['Return']
#         self.current_step += 1
#         done = self.current_step >= min(len(df) for df in self.price_data.values()) - 1
#         return self._get_observation(), reward, done, {}
#
# def train_agent(env):
#     model = PPO('MlpPolicy', env, verbose=1)
#     model.learn(total_timesteps=10000)
#     return model
