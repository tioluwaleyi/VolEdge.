import importlib.machinery
import math
import sys
import unittest

import _voledge_native as native
from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.pricing import bsm_greeks, bsm_price


ABS_TOLERANCE = 1e-10
REL_TOLERANCE = 1e-10


def assert_close(name, actual, expected):
    if not math.isclose(
        actual,
        expected,
        rel_tol=REL_TOLERANCE,
        abs_tol=ABS_TOLERANCE,
    ):
        raise AssertionError(
            f"{name} mismatch: native={actual}, Python={expected}"
        )


def compare_to_python(kind, values):
    spot, strike, maturity, rate, dividend, volatility = values
    python_option_type = OptionType(kind)
    python_option = Option(
        python_option_type,
        ExerciseStyle.EUROPEAN,
        strike,
        maturity,
        "USD",
    )
    python_market = MarketState(spot, rate, dividend)
    python_model = ModelParameters(volatility)

    native_option = native.Option(
        native.OptionType.call if kind == "call" else native.OptionType.put,
        native.ExerciseStyle.european,
        strike,
        maturity,
    )
    native_result = native.price_european_bsm(
        native_option,
        native.MarketState(spot, rate, dividend),
        native.ModelParameters(volatility),
    )

    expected_price = bsm_price(python_option, python_market, python_model)
    expected_greeks = bsm_greeks(python_option, python_market, python_model)
    assert_close(f"{kind} price", native_result.price, expected_price)

    if expected_greeks is None:
        if native_result.greeks is not None:
            raise AssertionError("Native Greeks must be None at a boundary")
        return
    if native_result.greeks is None:
        raise AssertionError("Native Greeks are unexpectedly unavailable")

    for greek in ("delta", "gamma", "vega", "theta", "rho"):
        assert_close(
            f"{kind} {greek}",
            getattr(native_result.greeks, greek),
            getattr(expected_greeks, greek),
        )


def assert_invalid_inputs():
    option = native.Option(
        native.OptionType.call,
        native.ExerciseStyle.european,
        100.0,
        1.0,
    )
    test_case = unittest.TestCase()
    with test_case.assertRaisesRegex(TypeError, "spot must be a number"):
        native.MarketState(True, 0.05, 0.0)
    with test_case.assertRaisesRegex(TypeError, "spot must be a number"):
        MarketState(True, 0.05, 0.0)
    with test_case.assertRaisesRegex(
        ValueError, "spot must be positive"
    ):
        native.price_european_bsm(
            option,
            native.MarketState(0.0, 0.05, 0.0),
            native.ModelParameters(0.20),
        )

    american_option = native.Option(
        native.OptionType.put,
        native.ExerciseStyle.american,
        100.0,
        1.0,
    )
    with test_case.assertRaisesRegex(
        ValueError, "requires European exercise"
    ):
        native.price_european_bsm(
            american_option,
            native.MarketState(100.0, 0.05, 0.02),
            native.ModelParameters(0.20),
        )

    range_market = native.MarketState(100.0, -1000.0, 0.0)
    with test_case.assertRaisesRegex(
        ArithmeticError, "discounted strike"
    ):
        native.price_european_bsm(
            option,
            range_market,
            native.ModelParameters(0.20),
        )
    with test_case.assertRaises(ArithmeticError):
        bsm_price(
            Option(
                OptionType.CALL,
                ExerciseStyle.EUROPEAN,
                100.0,
                1.0,
                "USD",
            ),
            MarketState(100.0, -1000.0, 0.0),
            ModelParameters(0.20),
        )


def main():
    module_path = native.__file__
    extension_suffixes = importlib.machinery.EXTENSION_SUFFIXES
    if not any(module_path.endswith(suffix) for suffix in extension_suffixes):
        raise AssertionError(
            f"Expected compiled extension, loaded {module_path}"
        )
    if len(sys.argv) > 1:
        raise SystemExit("usage: pybind_parity_check.py")

    scenarios = (
        (100.0, 100.0, 1.0, 0.05, 0.02, 0.20),
        (95.0, 100.0, 2.0, -0.01, 0.015, 0.30),
        (110.0, 100.0, 0.0, 0.05, 0.02, 0.20),
        (100.0, 100.0, 1.0, 0.05, 0.0, 0.0),
    )
    comparisons = 0
    for kind in ("call", "put"):
        for values in scenarios:
            compare_to_python(kind, values)
            comparisons += 1

    assert_invalid_inputs()
    print(
        f"PASS: compiled binding {module_path}; {comparisons} price/Greek "
        f"comparisons and invalid-input/American rejection "
        f"(atol={ABS_TOLERANCE:g}, rtol={REL_TOLERANCE:g})"
    )


if __name__ == "__main__":
    main()
