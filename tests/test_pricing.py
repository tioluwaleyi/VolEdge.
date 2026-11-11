import unittest
from math import exp

from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.american import (
    MAX_CRR_STEPS,
    american_crr_greeks,
    american_crr_price,
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

    def test_american_crr_one_step_hand_calculation(self):
        market = MarketState(100.0, 0.05, 0.02)
        model = ModelParameters(0.20)
        for kind, expected in (
            (OptionType.CALL, 11.073540703840242),
            (OptionType.PUT, 8.176615823236105),
        ):
            with self.subTest(kind=kind):
                price = american_crr_price(
                    self.option(kind, style=ExerciseStyle.AMERICAN),
                    market,
                    model,
                    steps=1,
                )
                self.assertAlmostEqual(price, expected, delta=1e-12)

    def test_american_put_early_exercise_adds_value(self):
        option = Option(
            OptionType.PUT,
            ExerciseStyle.AMERICAN,
            50.0,
            1.0,
            "USD",
        )
        market = MarketState(40.0, 0.10, 0.0)
        model = ModelParameters(0.20)
        american_price = american_crr_price(option, market, model, steps=100)
        european_price = bsm_price(
            Option(
                OptionType.PUT,
                ExerciseStyle.EUROPEAN,
                50.0,
                1.0,
                "USD",
            ),
            market,
            model,
        )
        self.assertGreater(american_price, european_price)

    def test_american_call_converges_to_european_bsm(self):
        option = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        market = MarketState(100.0, 0.05, 0.0)
        model = ModelParameters(0.20)
        tree_price = american_crr_price(option, market, model, steps=2000)
        bsm_call = bsm_price(
            Option(
                OptionType.CALL,
                ExerciseStyle.EUROPEAN,
                100.0,
                1.0,
                "USD",
            ),
            market,
            model,
        )
        self.assertAlmostEqual(tree_price, bsm_call, delta=0.01)

    def test_american_call_crr_greeks_match_european_bsm(self):
        american_option = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        european_option = self.option(OptionType.CALL)
        market = MarketState(100.0, 0.05, 0.0)
        model = ModelParameters(0.20)
        expected = bsm_greeks(european_option, market, model)
        self.assertIsNotNone(expected)

        estimates = american_crr_greeks(
            american_option,
            market,
            model,
            steps=800,
            relative_spot_bump=0.05,
        )
        self.assertIsNotNone(estimates)
        delta, gamma = estimates
        self.assertAlmostEqual(delta, expected.delta, delta=0.0022)
        self.assertAlmostEqual(gamma, expected.gamma, delta=0.00035)

    def test_american_crr_greeks_sensitivity_to_bump_and_steps(self):
        option = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        market = MarketState(100.0, 0.05, 0.0)
        model = ModelParameters(0.20)
        default_bump = american_crr_greeks(
            option, market, model, steps=800
        )
        wider_bump = american_crr_greeks(
            option,
            market,
            model,
            steps=800,
            relative_spot_bump=0.05,
        )
        fewer_steps = american_crr_greeks(
            option,
            market,
            model,
            steps=400,
            relative_spot_bump=0.05,
        )
        self.assertGreater(abs(default_bump[1] - wider_bump[1]), 0.2)
        self.assertGreater(abs(fewer_steps[1] - wider_bump[1]), 0.0002)

    def test_deep_in_the_money_american_put_crr_greeks(self):
        option = Option(
            OptionType.PUT,
            ExerciseStyle.AMERICAN,
            100.0,
            1.0,
            "USD",
        )
        market = MarketState(40.0, 0.10, 0.0)
        model = ModelParameters(0.20)
        bump = market.spot * 0.001

        for spot in (market.spot - bump, market.spot, market.spot + bump):
            with self.subTest(spot=spot):
                price = american_crr_price(
                    option,
                    MarketState(spot, market.rate, market.dividend_yield),
                    model,
                    steps=200,
                )
                self.assertAlmostEqual(100.0 - spot, price, delta=1e-12)

        estimates = american_crr_greeks(
            option, market, model, steps=200
        )
        self.assertIsNotNone(estimates)
        self.assertAlmostEqual(estimates[0], -1.0, delta=1e-9)
        self.assertAlmostEqual(estimates[1], 0.0, delta=1e-8)

    def test_american_crr_greeks_boundaries_and_bump_validation(self):
        option = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        market = MarketState(100.0, 0.05, 0.0)
        self.assertIsNone(
            american_crr_greeks(
                self.option(
                    OptionType.CALL,
                    maturity=0.0,
                    style=ExerciseStyle.AMERICAN,
                ),
                market,
                ModelParameters(0.20),
                steps=10,
            )
        )
        self.assertIsNone(
            american_crr_greeks(
                option,
                market,
                ModelParameters(0.0),
                steps=10,
            )
        )

        with self.assertRaisesRegex(ValueError, "lower spot nonpositive"):
            american_crr_greeks(
                option,
                market,
                ModelParameters(0.20),
                steps=10,
                relative_spot_bump=1.0,
            )
        for invalid_bump in (True, 0.0, -0.1, float("inf")):
            with self.subTest(relative_spot_bump=invalid_bump):
                with self.assertRaises((TypeError, ValueError)):
                    american_crr_greeks(
                        option,
                        market,
                        ModelParameters(0.20),
                        steps=10,
                        relative_spot_bump=invalid_bump,
                    )

    def test_american_crr_expiry_and_zero_volatility(self):
        put = self.option(
            OptionType.PUT,
            maturity=0.0,
            style=ExerciseStyle.AMERICAN,
        )
        self.assertEqual(
            american_crr_price(
                put,
                MarketState(90.0, 0.05, 0.0),
                ModelParameters(0.20),
                steps=3,
            ),
            10.0,
        )

        deterministic_put = Option(
            OptionType.PUT,
            ExerciseStyle.AMERICAN,
            100.0,
            1.0,
            "USD",
        )
        self.assertEqual(
            american_crr_price(
                deterministic_put,
                MarketState(80.0, 0.10, 0.0),
                ModelParameters(0.0),
                steps=4,
            ),
            20.0,
        )

    def test_american_crr_rejects_invalid_probability(self):
        option = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        with self.assertRaisesRegex(ValueError, "probability is outside"):
            american_crr_price(
                option,
                MarketState(100.0, 0.50, 0.0),
                ModelParameters(0.01),
                steps=1,
            )

    def test_american_crr_validates_style_and_steps(self):
        american_call = self.option(
            OptionType.CALL,
            style=ExerciseStyle.AMERICAN,
        )
        market = MarketState(100.0, 0.05, 0.0)
        model = ModelParameters(0.20)

        with self.assertRaisesRegex(ValueError, "American exercise"):
            american_crr_price(
                self.option(OptionType.CALL),
                market,
                model,
                steps=10,
            )
        for invalid_steps in (True, 1.5, 0, -1, MAX_CRR_STEPS + 1):
            with self.subTest(steps=invalid_steps):
                with self.assertRaises((TypeError, ValueError)):
                    american_crr_price(
                        american_call,
                        market,
                        model,
                        steps=invalid_steps,
                    )


if __name__ == "__main__":
    unittest.main()
