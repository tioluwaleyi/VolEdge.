#pragma once

#include <optional>

namespace voledge {

enum class OptionType {
    call,
    put,
};

enum class ExerciseStyle {
    european,
    american,
};

struct Option {
    OptionType type;
    ExerciseStyle exercise_style;
    double strike;
    double maturity_years;
};

struct MarketState {
    double spot;
    double rate;
    double dividend_yield;
};

struct ModelParameters {
    double volatility;
};

struct Greeks {
    double delta;
    double gamma;
    double vega;
    double theta;
    double rho;
};

struct PricingResult {
    double price;
    std::optional<Greeks> greeks;
};

PricingResult price_european_bsm(
    const Option& option,
    const MarketState& market,
    const ModelParameters& model
);

}  // namespace voledge
