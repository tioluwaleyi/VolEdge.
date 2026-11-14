#include "voledge/bsm.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>
#include <stdexcept>
#include <string>

namespace voledge {
namespace {

double normal_cdf(double value) {
    return 0.5 * std::erfc(-value / std::sqrt(2.0));
}

void require_finite(double value, const char* name) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument(std::string(name) + " must be finite");
    }
}

void require_finite_result(double value, const char* name) {
    if (!std::isfinite(value)) {
        throw std::overflow_error(
            std::string("BSM produced a nonfinite ") + name
        );
    }
}

double payoff(OptionType type, double spot, double strike) {
    if (type == OptionType::call) {
        return std::max(spot - strike, 0.0);
    }
    return std::max(strike - spot, 0.0);
}

}  // namespace

PricingResult price_european_bsm(
    const Option& option,
    const MarketState& market,
    const ModelParameters& model
) {
    if (option.type != OptionType::call && option.type != OptionType::put) {
        throw std::invalid_argument("option type must be call or put");
    }
    if (option.exercise_style != ExerciseStyle::european
        && option.exercise_style != ExerciseStyle::american) {
        throw std::invalid_argument("exercise style must be European or American");
    }
    if (option.exercise_style != ExerciseStyle::european) {
        throw std::invalid_argument("BSM pricing requires European exercise");
    }

    require_finite(option.strike, "strike");
    require_finite(option.maturity_years, "maturity_years");
    require_finite(market.spot, "spot");
    require_finite(market.rate, "rate");
    require_finite(market.dividend_yield, "dividend_yield");
    require_finite(model.volatility, "volatility");

    if (option.strike <= 0.0) {
        throw std::invalid_argument("strike must be positive");
    }
    if (option.maturity_years < 0.0) {
        throw std::invalid_argument("maturity_years cannot be negative");
    }
    if (market.spot <= 0.0) {
        throw std::invalid_argument("spot must be positive");
    }
    if (model.volatility < 0.0) {
        throw std::invalid_argument("volatility cannot be negative");
    }

    const double spot = market.spot;
    const double strike = option.strike;
    const double maturity = option.maturity_years;
    const double rate = market.rate;
    const double dividend = market.dividend_yield;
    const double volatility = model.volatility;

    if (maturity == 0.0) {
        return {payoff(option.type, spot, strike), std::nullopt};
    }

    const double discounted_spot = spot * std::exp(-dividend * maturity);
    const double discounted_strike = strike * std::exp(-rate * maturity);
    require_finite_result(discounted_spot, "discounted spot");
    require_finite_result(discounted_strike, "discounted strike");

    if (volatility == 0.0) {
        const double deterministic_price = option.type == OptionType::call
            ? std::max(discounted_spot - discounted_strike, 0.0)
            : std::max(discounted_strike - discounted_spot, 0.0);
        require_finite_result(deterministic_price, "price");
        return {deterministic_price, std::nullopt};
    }

    const double sqrt_maturity = std::sqrt(maturity);
    const double total_volatility = volatility * sqrt_maturity;
    if (!std::isfinite(total_volatility) || total_volatility == 0.0) {
        throw std::overflow_error("Volatility-time scale is out of range");
    }

    const double d1 = (
        std::log(spot) - std::log(strike)
        + (rate - dividend) * maturity
    ) / total_volatility + 0.5 * total_volatility;
    const double d2 = d1 - total_volatility;
    require_finite_result(d1, "d1");
    require_finite_result(d2, "d2");

    const double price = option.type == OptionType::call
        ? discounted_spot * normal_cdf(d1)
            - discounted_strike * normal_cdf(d2)
        : discounted_strike * normal_cdf(-d2)
            - discounted_spot * normal_cdf(-d1);
    require_finite_result(price, "price");
    if (price < 0.0) {
        throw std::overflow_error("BSM produced a negative price");
    }

    const double density = std::exp(-0.5 * d1 * d1)
        / std::sqrt(2.0 * std::numbers::pi);
    const double discounted_density = std::exp(-dividend * maturity) * density;
    const double gamma = discounted_density / (spot * total_volatility);
    const double vega = spot * discounted_density * sqrt_maturity;
    const double diffusion_theta = -spot * discounted_density * volatility
        / (2.0 * sqrt_maturity);

    double delta;
    double theta;
    double rho;
    if (option.type == OptionType::call) {
        delta = std::exp(-dividend * maturity) * normal_cdf(d1);
        theta = diffusion_theta
            + dividend * discounted_spot * normal_cdf(d1)
            - rate * discounted_strike * normal_cdf(d2);
        rho = strike * maturity * std::exp(-rate * maturity)
            * normal_cdf(d2);
    } else {
        delta = -std::exp(-dividend * maturity) * normal_cdf(-d1);
        theta = diffusion_theta
            - dividend * discounted_spot * normal_cdf(-d1)
            + rate * discounted_strike * normal_cdf(-d2);
        rho = -strike * maturity * std::exp(-rate * maturity)
            * normal_cdf(-d2);
    }

    require_finite_result(delta, "delta");
    require_finite_result(gamma, "gamma");
    require_finite_result(vega, "vega");
    require_finite_result(theta, "theta");
    require_finite_result(rho, "rho");

    return {price, Greeks{delta, gamma, vega, theta, rho}};
}

}  // namespace voledge
