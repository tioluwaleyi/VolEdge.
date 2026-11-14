"""Validated inputs for VolEdge pricing models."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


class ExerciseStyle(Enum):
    EUROPEAN = "european"
    AMERICAN = "american"


def validate_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")

    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class Option:
    option_type: OptionType
    exercise_style: ExerciseStyle
    strike: float
    maturity_years: float
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.option_type, OptionType):
            raise TypeError("option_type must be an OptionType")

        if not isinstance(self.exercise_style, ExerciseStyle):
            raise TypeError("exercise_style must be an ExerciseStyle")

        validate_number("strike", self.strike)
        validate_number("maturity_years", self.maturity_years)

        if self.strike <= 0:
            raise ValueError("strike must be positive")

        if self.maturity_years < 0:
            raise ValueError("maturity_years cannot be negative")

        if not isinstance(self.currency, str):
            raise TypeError("currency must be a string")

        if not self.currency.strip():
            raise ValueError("currency cannot be empty")


@dataclass(frozen=True)
class MarketState:
    spot: float
    rate: float
    dividend_yield: float

    def __post_init__(self) -> None:
        validate_number("spot", self.spot)
        validate_number("rate", self.rate)
        validate_number("dividend_yield", self.dividend_yield)

        if self.spot <= 0:
            raise ValueError("spot must be positive")


@dataclass(frozen=True)
class ModelParameters:
    volatility: float

    def __post_init__(self) -> None:
        validate_number("volatility", self.volatility)

        if self.volatility < 0:
            raise ValueError("volatility cannot be negative")


@dataclass(frozen=True)
class Greeks:
    """Per-unit BSM sensitivities; vega and rho are per absolute unit."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float

    def __post_init__(self) -> None:
        for name in ("delta", "gamma", "vega", "theta", "rho"):
            validate_number(name, getattr(self, name))
