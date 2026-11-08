"""Fee-aware structural edge bot for Polymarket and Kalshi.

The strategies in this package do not forecast who wins. They buy packages
whose worst-case payout is $1 when the market is offering that package for
less than $1 after fees.
"""

__version__ = "0.1.0"
