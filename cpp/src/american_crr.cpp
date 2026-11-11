#include "voledge/american_crr.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace voledge {
namespace {

constexpr int max_crr_steps = 10'000;

void require_finite(double value, const char* name) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument(std::string(name) + " must be finite");
    }
}

double finite_exp(double exponent, const char* name) {
    const double value = std::exp(exponent);
    if (!std::isfinite(value) || value <= 0.0) {
        throw std::overflow_error(
            std::string("Inputs exceed the supported numerical range (")
            + name + ")"
        );
    }
    return value;
}

double intrinsic(OptionType type, double spot, double strike) {
    if (type == OptionType::call) {
        return std::max(spot - strike, 0.0);
    }
    return std::max(strike - spot, 0.0);
}

}  // namespace

double price_american_crr(
    const Option& option,
    const MarketState& market,
    const ModelParameters& model,
    int steps
) {
    if (option.type != OptionType::call && option.type != OptionType::put) {
        throw std::invalid_argument("option type must be call or put");
    }
    if (option.exercise_style != ExerciseStyle::american
        && option.exercise_style != ExerciseStyle::european) {
        throw std::invalid_argument("exercise style must be European or American");
    }
    if (option.exercise_style != ExerciseStyle::american) {
        throw std::invalid_argument("CRR pricing requires American exercise");
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
    if (steps < 1) {
        throw std::invalid_argument("steps must be at least 1");
    }
    if (steps > max_crr_steps) {
        throw std::invalid_argument("steps cannot exceed 10000");
    }

    const double spot = market.spot;
    const double strike = option.strike;
    const double maturity = option.maturity_years;
    const double rate = market.rate;
    const double dividend = market.dividend_yield;
    const double volatility = model.volatility;

    if (maturity == 0.0) {
        return intrinsic(option.type, spot, strike);
    }

    const double dt = maturity / static_cast<double>(steps);
    if (!std::isfinite(dt) || dt <= 0.0) {
        throw std::overflow_error(
            "Tree time step is outside the supported range"
        );
    }

    const double discount = finite_exp(-rate * dt, "discount factor");
    const double log_spot = std::log(spot);

    if (volatility == 0.0) {
        std::vector<double> deterministic_spots;
        deterministic_spots.reserve(static_cast<std::size_t>(steps) + 1);
        deterministic_spots.push_back(spot);
        for (int time_step = 1; time_step <= steps; ++time_step) {
            const double drift_time =
                (rate - dividend) * dt * static_cast<double>(time_step);
            deterministic_spots.push_back(
                finite_exp(log_spot + drift_time, "deterministic spot")
            );
        }

        double value = intrinsic(option.type, deterministic_spots.back(), strike);
        for (int time_step = steps - 1; time_step >= 0; --time_step) {
            value = std::max(
                intrinsic(
                    option.type,
                    deterministic_spots[static_cast<std::size_t>(time_step)],
                    strike
                ),
                discount * value
            );
            require_finite(value, "CRR price");
        }
        return value;
    }

    const double log_up = volatility * std::sqrt(dt);
    if (!std::isfinite(log_up) || log_up <= 0.0) {
        throw std::overflow_error("CRR up-move is outside the supported range");
    }
    const double up = finite_exp(log_up, "up factor");
    const double down = finite_exp(-log_up, "down factor");
    if (up == down) {
        throw std::overflow_error(
            "CRR up and down factors are indistinguishable"
        );
    }

    const double growth =
        finite_exp((rate - dividend) * dt, "risk-neutral growth");
    const double probability = (growth - down) / (up - down);
    if (!std::isfinite(probability)) {
        throw std::overflow_error("CRR probability is nonfinite");
    }
    if (probability < 0.0 || probability > 1.0) {
        throw std::invalid_argument(
            "CRR risk-neutral probability is outside [0, 1]; "
            "adjust inputs or increase steps"
        );
    }

    std::vector<double> values(static_cast<std::size_t>(steps) + 1);
    for (int up_moves = 0; up_moves <= steps; ++up_moves) {
        const double node_spot = finite_exp(
            log_spot
                + static_cast<double>(2 * up_moves - steps) * log_up,
            "terminal spot"
        );
        values[static_cast<std::size_t>(up_moves)] =
            intrinsic(option.type, node_spot, strike);
    }

    const double down_probability = 1.0 - probability;
    for (int time_step = steps - 1; time_step >= 0; --time_step) {
        for (int up_moves = 0; up_moves <= time_step; ++up_moves) {
            const std::size_t index = static_cast<std::size_t>(up_moves);
            const double continuation = discount * (
                probability * values[index + 1]
                + down_probability * values[index]
            );
            const double node_spot = finite_exp(
                log_spot
                    + static_cast<double>(2 * up_moves - time_step) * log_up,
                "node spot"
            );
            values[index] = std::max(
                intrinsic(option.type, node_spot, strike),
                continuation
            );
            require_finite(values[index], "CRR price");
        }
    }

    return values.front();
}

}  // namespace voledge
