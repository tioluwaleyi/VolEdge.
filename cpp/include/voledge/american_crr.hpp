#pragma once

#include "voledge/bsm.hpp"

namespace voledge {

double price_american_crr(
    const Option& option,
    const MarketState& market,
    const ModelParameters& model,
    int steps
);

}  // namespace voledge
