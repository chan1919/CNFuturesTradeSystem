from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto


class CommissionType(Enum):
    RATIO = auto()
    FIXED = auto()


class CommissionRule(Enum):
    CLOSE_TODAY_AS_CLOSE = auto()
    CLOSE_TODAY_HIGHER = auto()
    CLOSE_TODAY_LOWER = auto()


def _open_label(rule: CommissionRule) -> str:
    return "开仓"


def _close_label(rule: CommissionRule) -> str:
    return "平仓"


def _close_today_label(rule: CommissionRule) -> str:
    if rule == CommissionRule.CLOSE_TODAY_AS_CLOSE:
        return "平仓"
    return "平今"


@dataclass
class CommissionRate:
    ctype: CommissionType
    value: Decimal

    def calculate(self, price: Decimal, multiplier: int, volume: int) -> Decimal:
        if self.ctype == CommissionType.FIXED:
            return self.value * volume
        return price * multiplier * volume * self.value

    def __repr__(self):
        if self.ctype == CommissionType.FIXED:
            return f"{self.value}元/手"
        return f"{self.value * 10000:.2f}万分之"


@dataclass
class CommissionModel:
    open_commission: CommissionRate
    close_commission: CommissionRate
    close_today_commission: CommissionRate
    rule: CommissionRule = CommissionRule.CLOSE_TODAY_AS_CLOSE

    def cost(self, direction: str, price: Decimal, multiplier: int, volume: int) -> Decimal:
        if direction == "open":
            return self.open_commission.calculate(price, multiplier, volume)
        close_cr = self.close_today_commission if direction == "close_today" else self.close_commission
        return close_cr.calculate(price, multiplier, volume)

    def estimate_cost(self, direction: str, price: Decimal, multiplier: int, volume: int) -> Decimal:
        return self.cost(direction, price, multiplier, volume)