import math
import subprocess
import sys

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


def run_native(
    executable,
    kind,
    spot,
    strike,
    maturity,
    rate,
    dividend,
    volatility,
    steps,
):
    return subprocess.run(
        [
            executable,
            kind,
            "american",
            str(spot),
            str(strike),
            str(maturity),
            str(rate),
            str(dividend),
            str(volatility),
            str(steps),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def compare_case(
    executable,
    label,
    kind,
    spot,
    strike,
    maturity,
    rate,
    dividend,
    volatility,
    steps,
):
    option = Option(
        OptionType(kind),
        ExerciseStyle.AMERICAN,
        strike,
        maturity,
        "USD",
    )
    market = MarketState(spot, rate, dividend)
    model = ModelParameters(volatility)
    python_price = american_crr_price(option, market, model, steps)

    result = run_native(
        executable, kind, spot, strike, maturity, rate, dividend, volatility,
        steps,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"{label}: C++ CRR failed: {result.stderr.strip()}"
        )
    try:
        cpp_price = float(result.stdout.strip())
    except ValueError as error:
        raise AssertionError(
            f"{label}: invalid C++ price output {result.stdout!r}"
        ) from error

    if not math.isclose(
        cpp_price,
        python_price,
        rel_tol=REL_TOLERANCE,
        abs_tol=ABS_TOLERANCE,
    ):
        raise AssertionError(
            f"{label}: price mismatch C++={cpp_price}, Python={python_price}"
        )
    return abs(cpp_price - python_price)


def assert_native_error(executable, label, args, expected_message):
    result = subprocess.run(
        [executable, *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0 or expected_message not in result.stderr:
        raise AssertionError(
            f"{label}: expected error containing {expected_message!r}; "
            f"returncode={result.returncode}, stderr={result.stderr!r}"
        )


def assert_python_error(label, function, expected_type, expected_message):
    try:
        function()
    except expected_type as error:
        if expected_message not in str(error):
            raise AssertionError(
                f"{label}: unexpected Python error {error!r}"
            ) from error
    else:
        raise AssertionError(f"{label}: expected {expected_type.__name__}")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: american_crr_parity_check.py EXECUTABLE")
    executable = sys.argv[1]
    cases = (
        ("one-step call", "call", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 1),
        ("one-step put", "put", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 1),
        ("early-exercise put", "put", 40.0, 50.0, 1.0, 0.10, 0.0, 0.20, 100),
        ("no-dividend call", "call", 100.0, 100.0, 1.0, 0.05, 0.0, 0.20, 2000),
        ("dividend call", "call", 100.0, 100.0, 1.0, 0.05, 0.02, 0.20, 200),
        ("expiry call", "call", 110.0, 100.0, 0.0, 0.05, 0.02, 0.20, 7),
        ("expiry put", "put", 90.0, 100.0, 0.0, 0.05, 0.02, 0.20, 7),
        ("zero-vol put", "put", 80.0, 100.0, 1.0, 0.10, 0.0, 0.0, 4),
    )

    largest_difference = 0.0
    for case in cases:
        largest_difference = max(
            largest_difference,
            compare_case(executable, *case),
        )

    invalid_case = [
        "call", "american", "100", "100", "1", "0.05", "0", "0.2",
    ]
    american_call = Option(
        OptionType.CALL,
        ExerciseStyle.AMERICAN,
        100.0,
        1.0,
        "USD",
    )
    market = MarketState(100.0, 0.05, 0.0)
    model = ModelParameters(0.20)
    for invalid_steps in ("0", "-1", "10001", "1.5"):
        assert_native_error(
            executable,
            f"invalid step count {invalid_steps}",
            [*invalid_case, invalid_steps],
            "steps",
        )
        python_steps = 1.5 if invalid_steps == "1.5" else int(invalid_steps)
        assert_python_error(
            f"Python invalid step count {invalid_steps}",
            lambda: american_crr_price(
                american_call,
                market,
                model,
                python_steps,
            ),
            (TypeError, ValueError),
            "steps",
        )

    invalid_probability_market = MarketState(100.0, 0.5, 0.0)
    assert_native_error(
        executable,
        "invalid tree probability",
        ["call", "american", "100", "100", "1", "0.5", "0", "0.01", "1"],
        "probability is outside [0, 1]",
    )
    assert_python_error(
        "Python invalid tree probability",
        lambda: american_crr_price(
            american_call,
            invalid_probability_market,
            ModelParameters(0.01),
            1,
        ),
        ValueError,
        "probability is outside [0, 1]",
    )

    print(
        f"PASS: {len(cases)} Python/C++ American CRR price comparisons "
        f"(atol={ABS_TOLERANCE:g}, rtol={REL_TOLERANCE:g}); "
        f"largest absolute difference={largest_difference:.17g}; "
        "invalid steps/probability rejected"
    )


if __name__ == "__main__":
    main()
