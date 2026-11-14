import unittest
from dataclasses import FrozenInstanceError

from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)


class ContractTests(unittest.TestCase):
    def test_both_exercise_styles(self):
        for style in ExerciseStyle:
            with self.subTest(style=style):
                option = Option(OptionType.CALL, style, 100.0, 1.0, "USD")
                self.assertEqual(option.exercise_style, style)

    def test_expiry_is_allowed(self):
        option = Option(
            OptionType.PUT, ExerciseStyle.EUROPEAN, 100.0, 0.0, "USD"
        )
        self.assertEqual(option.maturity_years, 0.0)

    def test_invalid_option_terms(self):
        for strike, maturity in [(-100.0, 1.0), (0.0, 1.0), (100.0, -1.0)]:
            with self.subTest(strike=strike, maturity=maturity):
                with self.assertRaises(ValueError):
                    Option(
                        OptionType.CALL,
                        ExerciseStyle.EUROPEAN,
                        strike,
                        maturity,
                        "USD",
                    )

    def test_negative_rates_are_allowed(self):
        market = MarketState(100.0, -0.01, 0.02)
        self.assertEqual(market.rate, -0.01)

    def test_invalid_spot(self):
        for spot in [0.0, -1.0, float("nan"), float("inf")]:
            with self.subTest(spot=spot):
                with self.assertRaises(ValueError):
                    MarketState(spot, 0.05, 0.0)

    def test_invalid_numeric_types(self):
        for spot in [True, "100", None]:
            with self.subTest(spot=spot):
                with self.assertRaises(TypeError):
                    MarketState(spot, 0.05, 0.0)

    def test_nonfinite_rates(self):
        for value in [float("nan"), float("inf"), -float("inf")]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MarketState(100.0, value, 0.0)
                with self.assertRaises(ValueError):
                    MarketState(100.0, 0.05, value)

    def test_volatility_boundaries(self):
        self.assertEqual(ModelParameters(0.0).volatility, 0.0)
        for value in [-0.2, float("nan"), float("inf")]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ModelParameters(value)

    def test_market_is_immutable(self):
        market = MarketState(100.0, 0.05, 0.0)
        with self.assertRaises(FrozenInstanceError):
            market.spot = 200.0


if __name__ == "__main__":
    unittest.main()
