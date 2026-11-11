
"""European option pricing with continuous dividend yield."""

from math import erfc, exp, isfinite, log, pi, sqrt

from voledge.contracts import (
    ExerciseStyle,
    Greeks,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)


def normal_cdf(x: float) -> float:
    """Standard normal cumulative probability."""
    return 0.5 * erfc(-x / sqrt(2.0))


def bsm_greeks(
    option: Option,
    market: MarketState,
    model: ModelParameters,
) -> Greeks | None:
    """Return European BSM Greeks per underlying unit.

    Vega and rho are per 1.0 change in annualized volatility and rate;
    multiply them by 0.01 for a one-percentage-point change. Theta is
    calendar-time decay per year (-dV/dT). Greeks are unavailable at
    expiry or zero volatility and are returned as None.
    """
    if not isinstance(option, Option):
        raise TypeError("option must be an Option")
    if not isinstance(market, MarketState):
        raise TypeError("market must be a MarketState")
    if not isinstance(model, ModelParameters):
        raise TypeError("model must be ModelParameters")

    if option.exercise_style is not ExerciseStyle.EUROPEAN:
        raise ValueError("BSM pricing requires European exercise")

    spot = market.spot
    strike = option.strike
    maturity = option.maturity_years
    volatility = model.volatility
    rate = market.rate
    dividend = market.dividend_yield

    if maturity == 0 or volatility == 0:
        return None

    try:
        sqrt_maturity = sqrt(maturity)
        total_volatility = volatility * sqrt_maturity
        if total_volatility == 0:
            raise ArithmeticError("Volatility-time scale underflow")

        d1 = (
            log(spot) - log(strike)
            + (rate - dividend) * maturity
        ) / total_volatility + 0.5 * total_volatility
        d2 = d1 - total_volatility
        discounted_spot = spot * exp(-dividend * maturity)
        discounted_strike = strike * exp(-rate * maturity)
        density = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
        discounted_density = exp(-dividend * maturity) * density

        if not all(isfinite(x) for x in (
            d1, d2, discounted_spot, discounted_strike,
            density, discounted_density,
        )):
            raise ArithmeticError("Nonfinite intermediate value")

        gamma = discounted_density / (spot * total_volatility)
        vega = spot * discounted_density * sqrt_maturity
        diffusion_theta = (
            -spot * discounted_density * volatility
            / (2.0 * sqrt_maturity)
        )

        if option.option_type is OptionType.CALL:
            delta = exp(-dividend * maturity) * normal_cdf(d1)
            theta = (
                diffusion_theta
                + dividend * discounted_spot * normal_cdf(d1)
                - rate * discounted_strike * normal_cdf(d2)
            )
            rho = strike * maturity * exp(-rate * maturity) * normal_cdf(d2)
        else:
            delta = -exp(-dividend * maturity) * normal_cdf(-d1)
            theta = (
                diffusion_theta
                - dividend * discounted_spot * normal_cdf(-d1)
                + rate * discounted_strike * normal_cdf(-d2)
            )
            rho = -strike * maturity * exp(-rate * maturity) * normal_cdf(-d2)

    except (OverflowError, ZeroDivisionError) as error:
        raise ArithmeticError(
            "Inputs exceed the supported numerical range"
        ) from error

    if not all(isfinite(x) for x in (delta, gamma, vega, theta, rho)):
        raise ArithmeticError("Greek calculation produced an invalid result")

    return Greeks(delta, gamma, vega, theta, rho)


def bsm_price(
    option: Option,
    market: MarketState,
    model: ModelParameters,
) -> float:
    """Return option value per underlying unit.

    Rates and volatility are annual decimals.
    Maturity is measured in years.
    American exercise requires a separate numerical pricer.
    """
    if not isinstance(option, Option):
        raise TypeError("option must be an Option")
    if not isinstance(market, MarketState):
        raise TypeError("market must be a MarketState")
    if not isinstance(model, ModelParameters):
        raise TypeError("model must be ModelParameters")

    if option.exercise_style is not ExerciseStyle.EUROPEAN:
        raise ValueError("BSM pricing requires European exercise")

    spot = market.spot
    strike = option.strike
    maturity = option.maturity_years
    volatility = model.volatility
    rate = market.rate
    dividend = market.dividend_yield

    if maturity == 0:
        if option.option_type is OptionType.CALL:
            return max(spot - strike, 0.0)
        return max(strike - spot, 0.0)

    try:
        discounted_spot = spot * exp(-dividend * maturity)
        discounted_strike = strike * exp(-rate * maturity)

        if volatility == 0:
            if option.option_type is OptionType.CALL:
                price = max(discounted_spot - discounted_strike, 0.0)
            else:
                price = max(discounted_strike - discounted_spot, 0.0)
        else:
            total_volatility = volatility * sqrt(maturity)

            if total_volatility == 0:
                raise ArithmeticError("Volatility-time scale underflow")

            d1 = (
                log(spot) - log(strike)
                + (rate - dividend) * maturity
            ) / total_volatility + 0.5 * total_volatility
            d2 = d1 - total_volatility

            if not all(isfinite(x) for x in (
                discounted_spot, discounted_strike, d1, d2
            )):
                raise ArithmeticError("Nonfinite intermediate value")

            if option.option_type is OptionType.CALL:
                price = (
                    discounted_spot * normal_cdf(d1)
                    - discounted_strike * normal_cdf(d2)
                )
            else:
                price = (
                    discounted_strike * normal_cdf(-d2)
                    - discounted_spot * normal_cdf(-d1)
                )

    except (OverflowError, ZeroDivisionError) as error:
        raise ArithmeticError(
            "Inputs exceed the supported numerical range"
        ) from error

    if not isfinite(price) or price < 0:
        raise ArithmeticError("Pricing produced an invalid result")

    return price
