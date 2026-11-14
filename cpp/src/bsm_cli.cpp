#include "voledge/bsm.hpp"

#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

double parse_number(const char* text) {
    std::size_t parsed_characters = 0;
    const std::string value(text);
    const double parsed = std::stod(value, &parsed_characters);
    if (parsed_characters != value.size()) {
        throw std::invalid_argument("numeric input contains trailing characters");
    }
    return parsed;
}

voledge::OptionType parse_option_type(const std::string& value) {
    if (value == "call") {
        return voledge::OptionType::call;
    }
    if (value == "put") {
        return voledge::OptionType::put;
    }
    throw std::invalid_argument("option type must be call or put");
}

voledge::ExerciseStyle parse_exercise_style(const std::string& value) {
    if (value == "european") {
        return voledge::ExerciseStyle::european;
    }
    if (value == "american") {
        return voledge::ExerciseStyle::american;
    }
    throw std::invalid_argument("exercise style must be european or american");
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 9) {
            throw std::invalid_argument(
                "usage: voledge_bsm_cli call|put european|american "
                "spot strike maturity rate dividend_yield volatility"
            );
        }

        const voledge::Option option{
            parse_option_type(argv[1]),
            parse_exercise_style(argv[2]),
            parse_number(argv[4]),
            parse_number(argv[5]),
        };
        const voledge::MarketState market{
            parse_number(argv[3]),
            parse_number(argv[6]),
            parse_number(argv[7]),
        };
        const voledge::ModelParameters model{parse_number(argv[8])};
        const voledge::PricingResult result =
            voledge::price_european_bsm(option, market, model);

        std::cout << std::setprecision(17) << result.price << ','
                  << (result.greeks.has_value() ? 1 : 0);
        if (result.greeks.has_value()) {
            const voledge::Greeks& greeks = *result.greeks;
            std::cout << ',' << greeks.delta
                      << ',' << greeks.gamma
                      << ',' << greeks.vega
                      << ',' << greeks.theta
                      << ',' << greeks.rho;
        }
        std::cout << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
