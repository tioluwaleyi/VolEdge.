import unittest
from math import isclose

from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.pricing import bsm_greeks, bsm_price


BSM_REFERENCES = (
    (100.0, 100.0, 1.0, 0.05, 0.0, 0.20, OptionType.CALL,
     (10.4505835721856, 0.636830651175619, 0.0187620173458469,
      37.5240346916938, -6.4140275464382, 53.2324815453763)),
    (100.0, 100.0, 1.0, 0.05, 0.0, 0.20, OptionType.PUT,
     (5.57352602225697, -0.363169348824381, 0.0187620173458469,
      37.5240346916938, -1.65788042393463, -41.8904609046951)),
    (100.0, 100.0, 1.0, 0.05, 0.02, 0.20, OptionType.CALL,
     (9.22700550815404, 0.586851146134764, 0.0189505787550087,
      37.9011575100174, -5.08931891399833, 49.4581091053224)),
    (100.0, 100.0, 1.0, 0.05, 0.02, 0.20, OptionType.PUT,
     (6.33008062754993, -0.393347527171991, 0.0189505787550087,
      37.9011575100174, -2.29356913810827, -45.6648333447491)),
    (100.0, 100.0, 1.0, -0.01, 0.0, 0.20, OptionType.CALL,
     (7.51305824360244, 0.519938805838372, 0.0199221957047382,
      39.8443914094764, -3.53963091754529, 44.4808223402348)),
    (100.0, 100.0, 1.0, -0.01, 0.0, 0.20, OptionType.PUT,
     (8.51807495201923, -0.480061194161628, 0.0199221957047382,
      39.8443914094764, -4.54968108462946, -56.524194368182)),
)


class P0ReferenceTests(unittest.TestCase):
    def test_independent_bsm_prices_and_greeks(self):
        names = ("price", "delta", "gamma", "vega", "theta", "rho")
        for case in BSM_REFERENCES:
            spot, strike, maturity, rate, dividend, volatility, kind, expected = case
            with self.subTest(kind=kind, rate=rate, dividend=dividend):
                option = Option(kind, ExerciseStyle.EUROPEAN, strike, maturity, "USD")
                market = MarketState(spot, rate, dividend)
                model = ModelParameters(volatility)
                greeks = bsm_greeks(option, market, model)
                self.assertIsNotNone(greeks)
                actual = (
                    bsm_price(option, market, model),
                    *(getattr(greeks, name) for name in names[1:]),
                )
                for label, value, reference in zip(names, actual, expected):
                    with self.subTest(output=label):
                        self.assertTrue(
                            isclose(
                                value,
                                reference,
                                abs_tol=1e-10,
                                rel_tol=1e-10,
                            ),
                            f"{label}: {value} != {reference}",
                        )

    def test_expiry_payoffs_exact_and_greeks_unavailable(self):
        cases = ((110.0, OptionType.CALL, 10.0), (90.0, OptionType.PUT, 10.0))
        for spot, kind, expected in cases:
            with self.subTest(kind=kind):
                option = Option(kind, ExerciseStyle.EUROPEAN, 100.0, 0.0, "USD")
                market = MarketState(spot, 0.05, 0.0)
                model = ModelParameters(0.20)
                self.assertEqual(bsm_price(option, market, model), expected)
                self.assertIsNone(bsm_greeks(option, market, model))

    def test_zero_volatility_boundary_prices(self):
        cases = (
            (100.0, 100.0, 0.0, OptionType.CALL, 0.0, 1e-12),
            (80.0, 100.0, 0.10, OptionType.PUT, 10.48374180359596, 1e-10),
        )
        for spot, strike, rate, kind, expected, tolerance in cases:
            with self.subTest(kind=kind, spot=spot):
                option = Option(kind, ExerciseStyle.EUROPEAN, strike, 1.0, "USD")
                market = MarketState(spot, rate, 0.0)
                model = ModelParameters(0.0)
                self.assertTrue(
                    isclose(
                        bsm_price(option, market, model),
                        expected,
                        abs_tol=tolerance,
                        rel_tol=0.0,
                    )
                )
                self.assertIsNone(bsm_greeks(option, market, model))


if __name__ == "__main__":
    unittest.main()
