"""Apply target allocation with bar delay and slippage at next bar open."""

from typing import Optional, Tuple

import pandas as pd

from backtest.trade import Trade


def delayed_rebalance_trade(
    *,
    symbol: str,
    bars: pd.DataFrame,
    global_idx: int,
    fill_delay: int,
    total_bars: int,
    equity: float,
    cash: float,
    shares: float,
    prev_allocation: float,
    target_allocation: float,
    slippage_pct: float,
    regime_state,
) -> Tuple[float, float, float, Optional[Trade]]:
    """Resize to ``target_allocation`` at ``open`` after ``fill_delay`` bars with slippage.

    Returns:
        ``(new_cash, new_shares, allocation_after, trade)``. If the fill index is past the
        series end, returns the prior cash, shares, allocation, and ``None`` for ``trade``.
    """
    fill_idx = global_idx + fill_delay
    if fill_idx >= total_bars:
        return cash, shares, prev_allocation, None

    fill_price = float(bars.iloc[fill_idx]["open"])
    slip = fill_price * slippage_pct
    fill_price += slip

    target_shares = int(equity * target_allocation / fill_price)
    delta = target_shares - shares
    cost = delta * fill_price
    slippage_cost = abs(delta) * slip

    new_cash = cash - cost
    new_shares = float(target_shares)
    trade = Trade(
        bar_index=fill_idx,
        timestamp=bars.index[fill_idx],
        symbol=symbol,
        prev_allocation=prev_allocation,
        new_allocation=target_allocation,
        price=fill_price,
        regime=regime_state.label,
        regime_prob=regime_state.probability,
        slippage_cost=slippage_cost,
    )
    return new_cash, new_shares, target_allocation, trade
