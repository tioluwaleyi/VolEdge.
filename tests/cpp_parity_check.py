import math
import subprocess
import sys

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


def run_native(executable, kind, style, spot, strike, maturity, rate, dividend, volatility):
    return subprocess.run(
        [
            executable,
            kind,
            style,
            str(spot),
            str(strike),
            str(maturity),
            str(rate),
            str(dividend),
            str(volatility),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def compare_to_python(executable, kind, values):
    spot, strike, maturity, rate, dividend, volatility = values
    option_type = OptionType(kind)
    option = Option(
        option_type,
        ExerciseStyle.EUROPEAN,
        strike,
        maturity,
        "USD",
    )
    market = MarketState(spot, rate, dividend)
    model = ModelParameters(volatility)
    expected_price = bsm_price(option, market, model)
    expected_greeks = bsm_greeks(option, market, model)

    result = run_native(
        executable, kind, "european", spot, strike, maturity, rate,
        dividend, volatility,
    )
    if result.returncode != 0:
        raise AssertionError(f"Native pricer failed: {result.stderr.strip()}")

    fields = result.stdout.strip().split(",")
    if not fields or len(fields) not in (2, 7):
        raise AssertionError(f"Unexpected native output: {result.stdout!r}")
    actual_price = float(fields[0])
    if not math.isclose(
        actual_price,
        expected_price,
        rel_tol=REL_TOLERANCE,
        abs_tol=ABS_TOLERANCE,
    ):
        raise AssertionError(
            f"{kind} price mismatch: native={actual_price}, "
            f"python={expected_price}"
        )

    expected_available = expected_greeks is not None
    actual_available = fields[1] == "1"
    if actual_available != expected_available:
        raise AssertionError(
            f"{kind} Greek availability mismatch: native={actual_available}, "
            f"python={expected_available}"
        )
    if expected_greeks is None:
        if len(fields) != 2:
            raise AssertionError("Native boundary result must omit Greeks")
        return
    if len(fields) != 7:
        raise AssertionError("Native interior result must include five Greeks")

    for name, actual, expected in zip(
        ("delta", "gamma", "vega", "theta", "rho"),
        map(float, fields[2:]),
        (
            expected_greeks.delta,
            expected_greeks.gamma,
            expected_greeks.vega,
            expected_greeks.theta,
            expected_greeks.rho,
        ),
    ):
        if not math.isclose(
            actual,
            expected,
            rel_tol=REL_TOLERANCE,
            abs_tol=ABS_TOLERANCE,
        ):
            raise AssertionError(
                f"{kind} {name} mismatch: native={actual}, python={expected}"
            )


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: cpp_parity_check.py NATIVE_EXECUTABLE")
    executable = sys.argv[1]
    scenarios = (
        (100.0, 100.0, 1.0, 0.05, 0.02, 0.20),
        (95.0, 100.0, 2.0, -0.01, 0.015, 0.30),
        (110.0, 100.0, 0.0, 0.05, 0.02, 0.20),
        (100.0, 100.0, 1.0, 0.05, 0.0, 0.0),
    )
    comparisons = 0
    for kind in ("call", "put"):
        for values in scenarios:
            compare_to_python(executable, kind, values)
            comparisons += 1

    american = run_native(
        executable, "put", "american", 100.0, 100.0, 1.0,
        0.05, 0.02, 0.20,
    )
    if american.returncode == 0 or "requires European exercise" not in american.stderr:
        raise AssertionError("American exercise was not explicitly rejected")

    invalid = run_native(
        executable, "call", "european", 0.0, 100.0, 1.0,
        0.05, 0.0, 0.20,
    )
    if invalid.returncode == 0 or "spot must be positive" not in invalid.stderr:
        raise AssertionError("Invalid spot was not explicitly rejected")

    print(
        f"PASS: {comparisons} price/Greek comparisons and American/invalid-input "
        f"rejection (atol={ABS_TOLERANCE:g}, rtol={REL_TOLERANCE:g})"
    )


if __name__ == "__main__":
    main()
