"""Market rules shared by the Python twin and the NEAR contract.

The contract (contract/src/lib.rs) encodes the same constants. Change both
together and update fixtures/scenarios.json if a payout number changes.
"""

REP_INIT = 1000
REP_SOLVE_BASE = 40
REP_CONF_DIV = 200
REP_HELPER = 20
REP_FAIL = 60
MAX_BIDS = 8
MAX_SHARE_BPS = 5000
MAX_SIDE = 30
MAX_STRING = 2000
MAX_TASKS = 128
MIN_WINDOW = 2
MAX_WINDOW = 10_000

# Offline sim uses these units. On testnet the same integers are yoctoNEAR.
DEFAULT_BOUNTY = 1_000_000
DEFAULT_STAKE = 100_000
DEFAULT_MAX_STAKE = 1_000_000_000


def solve_bonus(confidence_bps: int) -> int:
    return REP_SOLVE_BASE + (confidence_bps // REP_CONF_DIV)


def bid_score(confidence_bps: int, reputation: int, price: int) -> int:
    if price <= 0:
        raise ValueError("price must be positive")
    return (confidence_bps * reputation) // price


def helper_cut(price: int, share_bps: int) -> int:
    return (price * share_bps) // 10_000
