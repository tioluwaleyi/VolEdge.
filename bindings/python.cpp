#include "voledge/bsm.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>
#include <string>

namespace py = pybind11;

namespace {

double numeric_value(const py::object& value, const char* name) {
    if (PyBool_Check(value.ptr())
        || (!PyFloat_Check(value.ptr()) && !PyLong_Check(value.ptr()))) {
        throw py::type_error(std::string(name) + " must be a number");
    }
    return py::cast<double>(value);
}

}  // namespace

PYBIND11_MODULE(_voledge_native, module) {
    module.doc() = "Scalar C++20 European BSM pricing for VolEdge";

    py::enum_<voledge::OptionType>(module, "OptionType")
        .value("call", voledge::OptionType::call)
        .value("put", voledge::OptionType::put);

    py::enum_<voledge::ExerciseStyle>(module, "ExerciseStyle")
        .value("european", voledge::ExerciseStyle::european)
        .value("american", voledge::ExerciseStyle::american);

    py::class_<voledge::Option>(module, "Option")
        .def(
            py::init([](
                         voledge::OptionType type,
                         voledge::ExerciseStyle exercise_style,
                         py::object strike,
                         py::object maturity_years
                     ) {
                return voledge::Option{
                    type,
                    exercise_style,
                    numeric_value(strike, "strike"),
                    numeric_value(maturity_years, "maturity_years"),
                };
            }),
            py::arg("type"),
            py::arg("exercise_style"),
            py::arg("strike"),
            py::arg("maturity_years")
        );

    py::class_<voledge::MarketState>(module, "MarketState")
        .def(
            py::init([](
                         py::object spot,
                         py::object rate,
                         py::object dividend_yield
                     ) {
                return voledge::MarketState{
                    numeric_value(spot, "spot"),
                    numeric_value(rate, "rate"),
                    numeric_value(dividend_yield, "dividend_yield"),
                };
            }),
            py::arg("spot"),
            py::arg("rate"),
            py::arg("dividend_yield")
        );

    py::class_<voledge::ModelParameters>(module, "ModelParameters")
        .def(
            py::init([](py::object volatility) {
                return voledge::ModelParameters{
                    numeric_value(volatility, "volatility")
                };
            }),
            py::arg("volatility")
        );

    py::class_<voledge::Greeks>(module, "Greeks")
        .def_readonly("delta", &voledge::Greeks::delta)
        .def_readonly("gamma", &voledge::Greeks::gamma)
        .def_readonly("vega", &voledge::Greeks::vega)
        .def_readonly("theta", &voledge::Greeks::theta)
        .def_readonly("rho", &voledge::Greeks::rho);

    py::class_<voledge::PricingResult>(module, "PricingResult")
        .def_readonly("price", &voledge::PricingResult::price)
        .def_readonly("greeks", &voledge::PricingResult::greeks);

    module.def(
        "price_european_bsm",
        [](const voledge::Option& option,
           const voledge::MarketState& market,
           const voledge::ModelParameters& model) {
            try {
                return voledge::price_european_bsm(option, market, model);
            } catch (const std::overflow_error& error) {
                PyErr_SetString(PyExc_ArithmeticError, error.what());
                throw py::error_already_set();
            }
        },
        py::arg("option"),
        py::arg("market"),
        py::arg("model"),
        "Price a European option and return optional per-unit Greeks."
    );
}
