import importlib.machinery
import math
import unittest

import _voledge_native as native
from voledge.american import american_crr_price
from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)


ABS_TOLERANCE = 1e-10
REL_TOLERANCE = 1e-10


CASES = (
    ("one-step call", "call", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 1),
    ("one-step put", "put", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 1),
    ("early-exercise put", "put", 40.0, 50.0, 1.0, 0.10, 0.0, 0.20, 100),
    ("no-dividend call", "call", 100.0, 100.0, 1.0, 0.05, 0.0, 0.20, 2000),
    ("dividend call", "call", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 200),
    ("expiry call", "call", 110.0, 100.0, 0.0, 0.05, 0.02, 0.20, 7),
    ("expiry put", "put", 90.0, 100.0, 0.0, 0.05, 0.02, 0.20, 7),
    ("zero-vol put", "put", 80.0, 100.0, 1.0, 0.10, 0.0, 0.0, 4),
)


def build_python_inputs(kind, spot, strike, maturity, rate, dividend, volatility):
    option = Option(
        OptionType(kind),
        ExerciseStyle.AMERICAN,
        strike,
        maturity,
        "USD",
    )
    return (
        option,
        MarketState(spot, rate, dividend),
        ModelParameters(volatility),
    )


def build_native_inputs(kind, spot, strike, maturity, rate, dividend, volatility):
    option_type = (
        native.OptionType.call if kind == "call" else native.OptionType.put
    )
    option = native.Option(
        option_type,
        native.ExerciseStyle.american,
        strike,
        maturity,
    )
    return (
        option,
        native.MarketState(spot, rate, dividend),
        native.ModelParameters(volatility),
    )


def assert_error_matches_python(test_case, python_call, native_call, error_type, message):
    with test_case.assertRaises(error_type) as python_error:
        python_call()
    test_case.assertIn(message, str(python_error.exception))
    with test_case.assertRaises(error_type) as native_error:
        native_call()
    test_case.assertIn(message, str(native_error.exception))


def main():
    test_case = unittest.TestCase()
    module_path = native.__file__
    if not any(
        module_path.endswith(suffix)
        for suffix in importlib.machinery.EXTENSION_SUFFIXES
    ):
        raise AssertionError(
            f"Expected compiled extension, loaded {module_path}"
        )

    largest_difference = 0.0
    for label, kind, spot, strike, maturity, rate, dividend, volatility, steps in CASES:
        python_inputs = build_python_inputs(
            kind, spot, strike, maturity, rate, dividend, volatility
        )
        native_inputs = build_native_inputs(
            kind, spot, strike, maturity, rate, dividend, volatility
        )
        expected = american_crr_price(*python_inputs, steps)
        actual = native.price_american_crr(*native_inputs, steps)
        difference = abs(expected - actual)
        largest_difference = max(largest_difference, difference)
        if not math.isclose(
            actual,
            expected,
            rel_tol=REL_TOLERANCE,
            abs_tol=ABS_TOLERANCE,
        ):
            raise AssertionError(
                f"{label}: binding={actual}, Python={expected}"
            )

    european_python = Option(
        OptionType.CALL,
        ExerciseStyle.EUROPEAN,
        100.0,
        1.0,
        "USD",
    )
    european_native = native.Option(
        native.OptionType.call,
        native.ExerciseStyle.european,
        100.0,
        1.0,
    )
    market = MarketState(100.0, 0.05, 0.0)
    model = ModelParameters(0.20)
    native_market = native.MarketState(100.0, 0.05, 0.0)
    native_model = native.ModelParameters(0.20)
    assert_error_matches_python(
        test_case,
        lambda: american_crr_price(european_python, market, model, 10),
        lambda: native.price_american_crr(
            european_native, native_market, native_model, 10
        ),
        ValueError,
        "American exercise",
    )

    american_call = Option(
        OptionType.CALL,
        ExerciseStyle.AMERICAN,
        100.0,
        1.0,
        "USD",
    )
    native_call = native.Option(
        native.OptionType.call,
        native.ExerciseStyle.american,
        100.0,
        1.0,
    )
    for steps in (0, -1):
        assert_error_matches_python(
            test_case,
            lambda steps=steps: american_crr_price(
                american_call, market, model, steps
            ),
            lambda steps=steps: native.price_american_crr(
                native_call, native_market, native_model, steps
            ),
            ValueError,
            "steps",
        )
    assert_error_matches_python(
        test_case,
        lambda: american_crr_price(
            american_call, market, model, 10_001
        ),
        lambda: native.price_american_crr(
            native_call, native_market, native_model, 10_001
        ),
        ValueError,
        "steps",
    )
    for steps in (True, False):
        assert_error_matches_python(
            test_case,
            lambda steps=steps: american_crr_price(
                american_call, market, model, steps
            ),
            lambda steps=steps: native.price_american_crr(
                native_call, native_market, native_model, steps
            ),
            TypeError,
            "steps must be an integer",
        )
    assert_error_matches_python(
        test_case,
        lambda: american_crr_price(
            american_call, market, model, 1.5
        ),
        lambda: native.price_american_crr(
            native_call, native_market, native_model, 1.5
        ),
        TypeError,
        "steps must be an integer",
    )

    invalid_probability_market = MarketState(100.0, 0.5, 0.0)
    native_invalid_probability_market = native.MarketState(100.0, 0.5, 0.0)
    low_volatility = ModelParameters(0.01)
    native_low_volatility = native.ModelParameters(0.01)
    assert_error_matches_python(
        test_case,
        lambda: american_crr_price(
            american_call, invalid_probability_market, low_volatility, 1
        ),
        lambda: native.price_american_crr(
            native_call,
            native_invalid_probability_market,
            native_low_volatility,
            1,
        ),
        ValueError,
        "probability is outside [0, 1]",
    )

    overflow_market = MarketState(100.0, -1000.0, 0.0)
    native_overflow_market = native.MarketState(100.0, -1000.0, 0.0)
    assert_error_matches_python(
        test_case,
        lambda: american_crr_price(
            american_call, overflow_market, model, 1
        ),
        lambda: native.price_american_crr(
            native_call, native_overflow_market, native_model, 1
        ),
        ArithmeticError,
        "discount factor",
    )

    print(
        f"PASS: compiled binding {module_path}; {len(CASES)} American CRR "
        f"price comparisons (atol={ABS_TOLERANCE:g}, "
        f"rtol={REL_TOLERANCE:g}); largest absolute difference="
        f"{largest_difference:.17g}; matching error types for exercise, "
        "steps, booleans, floats, probability rejection, and overflow"
    )


if __name__ == "__main__":
    main()
