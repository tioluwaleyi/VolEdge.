import unittest
from math import exp

from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.pricing import bsm_greeks, bsm_price


class PricingTests(unittest.TestCase):
    def option(self, kind, maturity=1.0, style=ExerciseStyle.EUROPEAN):
        return Option(kind, style, 100.0, maturity, "USD")

    def test_call_benchmark(self):
        price = bsm_price(
            self.option(OptionType.CALL),
            MarketState(100.0, 0.05, 0.0),
            ModelParameters(0.20),
        )
        self.assertAlmostEqual(price, 10.450583572185565, delta=1e-10)

    def test_put_benchmark(self):
        price = bsm_price(
            self.option(OptionType.PUT),
            MarketState(100.0, 0.05, 0.0),
            ModelParameters(0.20),
        )
        self.assertAlmostEqual(price, 5.573526022256971, delta=1e-10)

    def test_dividend_adjusted_parity(self):
        market = MarketState(100.0, 0.05, 0.02)
        model = ModelParameters(0.20)
        call = bsm_price(self.option(OptionType.CALL), market, model)
        put = bsm_price(self.option(OptionType.PUT), market, model)
        expected = 100.0 * exp(-0.02) - 100.0 * exp(-0.05)
        self.assertAlmostEqual(call - put, expected, delta=1e-10)

    def test_expiry_payoffs(self):
        market = MarketState(110.0, 0.05, 0.0)
        model = ModelParameters(0.20)
        self.assertEqual(
            bsm_price(self.option(OptionType.CALL, 0.0), market, model),
            10.0,
        )
        self.assertEqual(
            bsm_price(self.option(OptionType.PUT, 0.0), market, model),
            0.0,
        )

    def test_zero_volatility(self):
        market = MarketState(100.0, 0.05, 0.0)
        model = ModelParameters(0.0)
        expected = 100.0 - 100.0 * exp(-0.05)
        self.assertAlmostEqual(
            bsm_price(self.option(OptionType.CALL), market, model),
            expected,
            delta=1e-10,
        )
        self.assertEqual(
            bsm_price(self.option(OptionType.PUT), market, model), 0.0
        )

    def test_call_increases_with_spot(self):
        option = self.option(OptionType.CALL)
        model = ModelParameters(0.20)
        low = bsm_price(option, MarketState(90.0, 0.05, 0.0), model)
        high = bsm_price(option, MarketState(110.0, 0.05, 0.0), model)
        self.assertGreater(high, low)

    def test_american_requires_another_pricer(self):
        option = self.option(
            OptionType.PUT, style=ExerciseStyle.AMERICAN
        )
        with self.assertRaisesRegex(ValueError, "European"):
            bsm_price(
                option,
                MarketState(100.0, 0.05, 0.0),
                ModelParameters(0.20),
            )

    def test_greeks_match_finite_differences(self):
        market = MarketState(105.0, 0.04, 0.02)
        model = ModelParameters(0.25)
        spot_step = 1e-3
        parameter_step = 1e-5

        for kind in (OptionType.CALL, OptionType.PUT):
            option = self.option(kind, maturity=1.25)
            greeks = bsm_greeks(option, market, model)
            self.assertIsNotNone(greeks)

            def price(spot, rate, volatility, maturity):
                return bsm_price(
                    self.option(kind, maturity=maturity),
                    MarketState(spot, rate, market.dividend_yield),
                    ModelParameters(volatility),
                )

            up_spot = price(
                market.spot + spot_step,
                market.rate,
                model.volatility,
                option.maturity_years,
            )
            down_spot = price(
                market.spot - spot_step,
                market.rate,
                model.volatility,
                option.maturity_years,
            )
            center = price(
                market.spot,
                market.rate,
                model.volatility,
                option.maturity_years,
            )
            self.assertAlmostEqual(
                greeks.delta,
                (up_spot - down_spot) / (2 * spot_step),
                delta=2e-7,
            )
            self.assertAlmostEqual(
                greeks.gamma,
                (up_spot - 2 * center + down_spot) / spot_step**2,
                delta=2e-6,
            )

            up_volatility = price(
                market.spot,
                market.rate,
                model.volatility + parameter_step,
                option.maturity_years,
            )
            down_volatility = price(
                market.spot,
                market.rate,
                model.volatility - parameter_step,
                option.maturity_years,
            )
            self.assertAlmostEqual(
                greeks.vega,
                (up_volatility - down_volatility) / (2 * parameter_step),
                delta=2e-7,
            )

            up_maturity = price(
                market.spot,
                market.rate,
                model.volatility,
                option.maturity_years + parameter_step,
            )
            down_maturity = price(
                market.spot,
                market.rate,
                model.volatility,
                option.maturity_years - parameter_step,
            )
            self.assertAlmostEqual(
                greeks.theta,
                -(up_maturity - down_maturity) / (2 * parameter_step),
                delta=2e-7,
            )

            up_rate = price(
                market.spot,
                market.rate + parameter_step,
                model.volatility,
                option.maturity_years,
            )
            down_rate = price(
                market.spot,
                market.rate - parameter_step,
                model.volatility,
                option.maturity_years,
            )
            self.assertAlmostEqual(
                greeks.rho,
                (up_rate - down_rate) / (2 * parameter_step),
                delta=2e-7,
            )

    def test_greeks_are_unavailable_at_boundaries(self):
        market = MarketState(100.0, 0.05, 0.02)
        for kind in (OptionType.CALL, OptionType.PUT):
            self.assertIsNone(
                bsm_greeks(
                    self.option(kind, maturity=0.0),
                    market,
                    ModelParameters(0.20),
                )
            )
            self.assertIsNone(
                bsm_greeks(
                    self.option(kind),
                    market,
                    ModelParameters(0.0),
                )
            )

    def test_greeks_reject_american_exercise(self):
        option = self.option(OptionType.CALL, style=ExerciseStyle.AMERICAN)
        with self.assertRaisesRegex(ValueError, "European"):
            bsm_greeks(
                option,
                MarketState(100.0, 0.05, 0.0),
                ModelParameters(0.20),
            )


if __name__ == "__main__":
    unittest.main()
