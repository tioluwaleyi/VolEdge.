#include "voledge/american_crr.hpp"

#include <charconv>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <system_error>

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

int parse_steps(const char* text) {
    const std::string value(text);
    int steps = 0;
    const auto [end, error] = std::from_chars(
        value.data(),
        value.data() + value.size(),
        steps
    );
    if (error != std::errc{} || end != value.data() + value.size()) {
        throw std::invalid_argument("steps must be an integer");
    }
    return steps;
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
    if (value == "american") {
        return voledge::ExerciseStyle::american;
    }
    if (value == "european") {
        return voledge::ExerciseStyle::european;
    }
    throw std::invalid_argument("exercise style must be European or American");
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 10) {
            throw std::invalid_argument(
                "usage: voledge_american_crr_cli call|put american "
                "spot strike maturity rate dividend_yield volatility steps"
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
        const int steps = parse_steps(argv[9]);
        const double price =
            voledge::price_american_crr(option, market, model, steps);

        std::cout << std::setprecision(17) << price << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
