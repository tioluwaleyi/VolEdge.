"""American option pricing with a Cox-Ross-Rubinstein binomial tree."""

from math import exp, isfinite, log, sqrt

from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)


MAX_CRR_STEPS = 10_000


def _intrinsic(option_type: OptionType, spot: float, strike: float) -> float:
    if option_type is OptionType.CALL:
        return max(spot - strike, 0.0)
    return max(strike - spot, 0.0)


def _finite_exp(exponent: float, name: str) -> float:
    try:
        value = exp(exponent)
    except OverflowError as error:
        raise ArithmeticError(
            f"Inputs exceed the supported numerical range ({name})"
        ) from error
    if not isfinite(value) or value <= 0.0:
        raise ArithmeticError(
            f"Inputs exceed the supported numerical range ({name})"
        )
    return value


def american_crr_price(
    option: Option,
    market: MarketState,
    model: ModelParameters,
    steps: int,
) -> float:
    """Return an American option value per underlying unit using CRR.

    The tree uses u=exp(sigma*sqrt(dt)), d=1/u, risk-neutral probability
    p=(exp((r-q)*dt)-d)/(u-d), and per-step discounting exp(-r*dt).
    Exercise is permitted at every tree date. ``steps`` must be an integer
    from 1 through ``MAX_CRR_STEPS``. Probabilities outside [0, 1] are
    rejected rather than clipped.

    Expiry returns intrinsic value. At zero volatility, a deterministic
    risk-neutral spot path is rolled back with exercise allowed at each of
    the requested dates; no binomial probability is needed. Greeks are not
    calculated.
    """
    if not isinstance(option, Option):
        raise TypeError("option must be an Option")
    if not isinstance(market, MarketState):
        raise TypeError("market must be a MarketState")
    if not isinstance(model, ModelParameters):
        raise TypeError("model must be ModelParameters")
    if option.exercise_style is not ExerciseStyle.AMERICAN:
        raise ValueError("CRR pricing requires American exercise")
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise TypeError("steps must be an integer")
    if steps < 1:
        raise ValueError("steps must be at least 1")
    if steps > MAX_CRR_STEPS:
        raise ValueError(f"steps cannot exceed {MAX_CRR_STEPS}")

    spot = market.spot
    strike = option.strike
    maturity = option.maturity_years
    rate = market.rate
    dividend = market.dividend_yield
    volatility = model.volatility

    if maturity == 0.0:
        return _intrinsic(option.option_type, spot, strike)

    dt = maturity / steps
    if not isfinite(dt) or dt <= 0.0:
        raise ArithmeticError("Tree time step is outside the supported range")

    discount = _finite_exp(-rate * dt, "discount factor")
    log_spot = log(spot)

    if volatility == 0.0:
        deterministic_spots = [spot]
        for time_step in range(1, steps + 1):
            drift_time = (rate - dividend) * dt * time_step
            node_spot = _finite_exp(log_spot + drift_time, "deterministic spot")
            deterministic_spots.append(node_spot)

        value = _intrinsic(option.option_type, deterministic_spots[-1], strike)
        for time_step in range(steps - 1, -1, -1):
            continuation = discount * value
            value = max(
                _intrinsic(
                    option.option_type,
                    deterministic_spots[time_step],
                    strike,
                ),
                continuation,
            )
            if not isfinite(value):
                raise ArithmeticError("CRR pricing produced a nonfinite result")
        return value

    log_up = volatility * sqrt(dt)
    if not isfinite(log_up) or log_up <= 0.0:
        raise ArithmeticError("CRR up-move is outside the supported range")

    up = _finite_exp(log_up, "up factor")
    down = _finite_exp(-log_up, "down factor")
    if up == down:
        raise ArithmeticError("CRR up and down factors are indistinguishable")

    growth = _finite_exp((rate - dividend) * dt, "risk-neutral growth")
    probability = (growth - down) / (up - down)
    if not isfinite(probability):
        raise ArithmeticError("CRR probability is nonfinite")
    if not 0.0 <= probability <= 1.0:
        raise ValueError(
            "CRR risk-neutral probability is outside [0, 1]; "
            "adjust inputs or increase steps"
        )

    values = []
    for up_moves in range(steps + 1):
        node_spot = _finite_exp(
            log_spot + (2 * up_moves - steps) * log_up,
            "terminal spot",
        )
        values.append(_intrinsic(option.option_type, node_spot, strike))

    down_probability = 1.0 - probability
    for time_step in range(steps - 1, -1, -1):
        next_values = []
        for up_moves in range(time_step + 1):
            continuation = discount * (
                probability * values[up_moves + 1]
                + down_probability * values[up_moves]
            )
            node_spot = _finite_exp(
                log_spot + (2 * up_moves - time_step) * log_up,
                "node spot",
            )
            value = max(
                _intrinsic(option.option_type, node_spot, strike),
                continuation,
            )
            if not isfinite(value):
                raise ArithmeticError("CRR pricing produced a nonfinite result")
            next_values.append(value)
        values = next_values

    return values[0]


def american_crr_greeks(
    option: Option,
    market: MarketState,
    model: ModelParameters,
    steps: int,
    relative_spot_bump: float = 1e-3,
) -> tuple[float, float] | None:
    """Estimate American CRR delta and gamma with centered spot bumps.

    The default absolute bump is 0.1% of spot. Delta uses the centered
    two-point difference and gamma the centered three-point difference, with
    all prices computed using the same tree step count. The returned tuple is
    ``(delta, gamma)``. Estimates are unavailable at expiry or zero
    volatility. A bump that makes the lower spot nonpositive is rejected.

    Finite-tree estimates can be unstable near exercise boundaries and need
    not converge monotonically as the bump or step count changes.
    """
    if (
        isinstance(relative_spot_bump, bool)
        or not isinstance(relative_spot_bump, (int, float))
    ):
        raise TypeError("relative_spot_bump must be a number")
    try:
        relative_spot_bump = float(relative_spot_bump)
    except OverflowError as error:
        raise ValueError("relative_spot_bump must be finite") from error
    if not isfinite(relative_spot_bump):
        raise ValueError("relative_spot_bump must be finite")
    if relative_spot_bump <= 0.0:
        raise ValueError("relative_spot_bump must be positive")

    center_price = american_crr_price(option, market, model, steps)
    if option.maturity_years == 0.0 or model.volatility == 0.0:
        return None

    spot = market.spot
    bump = spot * relative_spot_bump
    if not isfinite(bump) or bump <= 0.0:
        raise ArithmeticError("Spot bump is outside the supported range")
    down_spot = spot - bump
    up_spot = spot + bump
    if down_spot <= 0.0:
        raise ValueError("relative_spot_bump makes the lower spot nonpositive")
    if not isfinite(up_spot):
        raise ArithmeticError("Bumped spot is outside the supported range")
    bump_squared = bump * bump
    if (
        down_spot == spot
        or up_spot == spot
        or not isfinite(bump_squared)
        or bump_squared <= 0.0
    ):
        raise ValueError("relative_spot_bump is too small for this spot")

    up_price = american_crr_price(
        option,
        MarketState(up_spot, market.rate, market.dividend_yield),
        model,
        steps,
    )
    down_price = american_crr_price(
        option,
        MarketState(down_spot, market.rate, market.dividend_yield),
        model,
        steps,
    )

    delta = (up_price - down_price) / (2.0 * bump)
    gamma = (up_price - 2.0 * center_price + down_price) / bump_squared
    if not isfinite(delta) or not isfinite(gamma):
        raise ArithmeticError("CRR Greek estimate is nonfinite")
    return delta, gamma
