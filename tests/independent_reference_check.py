"""Reproduce approved reference fixtures without importing VolEdge code."""

from math import exp, isclose, log, pi, sqrt
from statistics import NormalDist


_NORMAL = NormalDist()

BSM_REFERENCES = (
    (100.0, 100.0, 1.0, 0.05, 0.0, 0.20, "call",
     (10.4505835721856, 0.636830651175619, 0.0187620173458469,
      37.5240346916938, -6.4140275464382, 53.2324815453763)),
    (100.0, 100.0, 1.0, 0.05, 0.0, 0.20, "put",
     (5.57352602225697, -0.363169348824381, 0.0187620173458469,
      37.5240346916938, -1.65788042393463, -41.8904609046951)),
    (100.0, 100.0, 1.0, 0.05, 0.02, 0.20, "call",
     (9.22700550815404, 0.586851146134764, 0.0189505787550087,
      37.9011575100174, -5.08931891399833, 49.4581091053224)),
    (100.0, 100.0, 1.0, 0.05, 0.02, 0.20, "put",
     (6.33008062754993, -0.393347527171991, 0.0189505787550087,
      37.9011575100174, -2.29356913810827, -45.6648333447491)),
    (100.0, 100.0, 1.0, -0.01, 0.0, 0.20, "call",
     (7.51305824360244, 0.519938805838372, 0.0199221957047382,
      39.8443914094764, -3.53963091754529, 44.4808223402348)),
    (100.0, 100.0, 1.0, -0.01, 0.0, 0.20, "put",
     (8.51807495201923, -0.480061194161628, 0.0199221957047382,
      39.8443914094764, -4.54968108462946, -56.524194368182)),
)

BOUNDARY_REFERENCES = (
    ("expiry call", 110.0, 100.0, 0.0, 0.05, 0.0, 0.20, "call", 10.0, 0.0, True),
    ("expiry put", 90.0, 100.0, 0.0, 0.05, 0.0, 0.20, "put", 10.0, 0.0, True),
    ("zero-vol call", 100.0, 100.0, 1.0, 0.0, 0.0, 0.0, "call", 0.0, 1e-12, False),
    ("zero-vol put", 80.0, 100.0, 1.0, 0.10, 0.0, 0.0, "put",
     10.48374180359596, 1e-10, False),
)

CRR_REFERENCES = (
    ("call", 12.1622849646239),
    ("put", 7.28522741469534),
)

GREEK_NAMES = ("price", "delta", "gamma", "vega", "theta", "rho")


def bsm_values(spot, strike, maturity, rate, dividend, volatility, kind):
    root_t = sqrt(maturity)
    total_volatility = volatility * root_t
    d1 = (
        log(spot / strike)
        + (rate - dividend + volatility * volatility / 2.0) * maturity
    ) / total_volatility
    d2 = d1 - total_volatility
    density = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
    discounted_spot = spot * exp(-dividend * maturity)
    discounted_strike = strike * exp(-rate * maturity)
    phi_d1 = density * exp(-dividend * maturity)

    if kind == "call":
        price = discounted_spot * _NORMAL.cdf(d1) - discounted_strike * _NORMAL.cdf(d2)
        delta = exp(-dividend * maturity) * _NORMAL.cdf(d1)
        theta = (
            -spot * phi_d1 * volatility / (2.0 * root_t)
            + dividend * discounted_spot * _NORMAL.cdf(d1)
            - rate * discounted_strike * _NORMAL.cdf(d2)
        )
        rho = strike * maturity * exp(-rate * maturity) * _NORMAL.cdf(d2)
    else:
        price = discounted_strike * _NORMAL.cdf(-d2) - discounted_spot * _NORMAL.cdf(-d1)
        delta = -exp(-dividend * maturity) * _NORMAL.cdf(-d1)
        theta = (
            -spot * phi_d1 * volatility / (2.0 * root_t)
            - dividend * discounted_spot * _NORMAL.cdf(-d1)
            + rate * discounted_strike * _NORMAL.cdf(-d2)
        )
        rho = -strike * maturity * exp(-rate * maturity) * _NORMAL.cdf(-d2)

    gamma = phi_d1 / (spot * total_volatility)
    vega = spot * phi_d1 * root_t
    return price, delta, gamma, vega, theta, rho


def expiry_price(spot, strike, kind):
    return max(spot - strike, 0.0) if kind == "call" else max(strike - spot, 0.0)


def zero_volatility_price(spot, strike, maturity, rate, dividend, kind):
    discounted_spot = spot * exp(-dividend * maturity)
    discounted_strike = strike * exp(-rate * maturity)
    if kind == "call":
        return max(discounted_spot - discounted_strike, 0.0)
    return max(discounted_strike - discounted_spot, 0.0)


def crr_one_step(kind):
    spot = strike = 100.0
    maturity = 1.0
    rate = 0.05
    dividend = 0.0
    volatility = 0.20
    up = exp(volatility * sqrt(maturity))
    down = 1.0 / up
    probability = (exp((rate - dividend) * maturity) - down) / (up - down)
    discount = exp(-rate * maturity)
    up_spot, down_spot = spot * up, spot * down
    if kind == "call":
        up_payoff = max(up_spot - strike, 0.0)
        down_payoff = max(down_spot - strike, 0.0)
        root_exercise = max(spot - strike, 0.0)
    else:
        up_payoff = max(strike - up_spot, 0.0)
        down_payoff = max(strike - down_spot, 0.0)
        root_exercise = max(strike - spot, 0.0)
    continuation = discount * (
        probability * up_payoff + (1.0 - probability) * down_payoff
    )
    return max(root_exercise, continuation)


def main():
    discrepancies = []
    checked = 0
    for case_number, case in enumerate(BSM_REFERENCES, 1):
        *inputs, expected = case
        actual = bsm_values(*inputs)
        for name, value, reference in zip(GREEK_NAMES, actual, expected):
            checked += 1
            if not isclose(value, reference, abs_tol=1e-10, rel_tol=1e-10):
                discrepancies.append(
                    f"BSM-{case_number} {name}: generated={value:.17g}, "
                    f"approved={reference:.17g}"
                )

    for name, spot, strike, maturity, rate, dividend, volatility, kind, expected, tolerance, exact in BOUNDARY_REFERENCES:
        actual = (
            expiry_price(spot, strike, kind)
            if maturity == 0.0
            else zero_volatility_price(spot, strike, maturity, rate, dividend, kind)
        )
        checked += 1
        matches = actual == expected if exact else isclose(
            actual, expected, abs_tol=tolerance, rel_tol=0.0
        )
        if not matches:
            discrepancies.append(
                f"{name}: generated={actual:.17g}, approved={expected:.17g}, "
                f"tolerance={'exact' if exact else tolerance}"
            )

    for kind, expected in CRR_REFERENCES:
        actual = crr_one_step(kind)
        checked += 1
        if not isclose(actual, expected, abs_tol=1e-12, rel_tol=0.0):
            discrepancies.append(
                f"early-P1 one-step CRR {kind}: generated={actual:.17g}, "
                f"approved={expected:.17g}, tolerance=1e-12"
            )

    print(f"Independent reference check: {checked} values; standard library only.")
    if discrepancies:
        print("DISCREPANCIES:")
        for discrepancy in discrepancies:
            print(f"- {discrepancy}")
        return 1
    print("All generated values match the approved fixture constants and tolerances.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
