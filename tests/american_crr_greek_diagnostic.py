"""Small reproducible sensitivity sweep for Python American CRR delta/gamma."""

from dataclasses import dataclass
from math import isclose

from voledge.american import american_crr_greeks, american_crr_price
from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.pricing import bsm_greeks


SPOT_BUMPS = (0.001, 0.02, 0.05)
TREE_STEPS = (80, 160, 320)
DELTA_STABILITY_TOLERANCE = 0.01
GAMMA_STABILITY_TOLERANCE = 0.0005
EXERCISE_TOLERANCE = 1e-10


@dataclass(frozen=True)
class Scenario:
    name: str
    option_type: OptionType
    spot: float
    rate: float
    compare_with_bsm: bool = False


SCENARIOS = (
    Scenario("call_itm", OptionType.CALL, 110.0, 0.05, True),
    Scenario("call_atm", OptionType.CALL, 100.0, 0.05, True),
    Scenario("call_otm", OptionType.CALL, 90.0, 0.05, True),
    Scenario("put_itm_exercise", OptionType.PUT, 40.0, 0.10),
    Scenario("put_atm", OptionType.PUT, 100.0, 0.10),
    Scenario("put_otm", OptionType.PUT, 110.0, 0.10),
    Scenario("put_boundary_crossing", OptionType.PUT, 83.0, 0.10),
)

STRIKE = 100.0
MATURITY = 1.0
VOLATILITY = 0.20


def _option(kind: OptionType, style: ExerciseStyle) -> Option:
    return Option(kind, style, STRIKE, MATURITY, "USD")


def _market(spot: float, rate: float) -> MarketState:
    return MarketState(spot, rate, 0.0)


def _intrinsic(option_type: OptionType, spot: float) -> float:
    if option_type is OptionType.CALL:
        return max(spot - STRIKE, 0.0)
    return max(STRIKE - spot, 0.0)


def _exercise_state(
    scenario: Scenario,
    model: ModelParameters,
    spot: float,
    steps: int,
) -> str:
    option = _option(scenario.option_type, ExerciseStyle.AMERICAN)
    value = american_crr_price(
        option,
        _market(spot, scenario.rate),
        model,
        steps,
    )
    if isclose(
        value,
        _intrinsic(scenario.option_type, spot),
        rel_tol=0.0,
        abs_tol=EXERCISE_TOLERANCE,
    ):
        return "exercise"
    return "continuation"


def _is_stable(max_difference: float, tolerance: float) -> str:
    return "stable" if max_difference <= tolerance else "unstable"


def main() -> None:
    model = ModelParameters(VOLATILITY)
    result_rows = []
    summary_rows = []

    for scenario in SCENARIOS:
        option = _option(scenario.option_type, ExerciseStyle.AMERICAN)
        market = _market(scenario.spot, scenario.rate)
        expected = None
        if scenario.compare_with_bsm:
            expected = bsm_greeks(
                _option(scenario.option_type, ExerciseStyle.EUROPEAN),
                market,
                model,
            )
            if expected is None:
                raise AssertionError(f"{scenario.name}: BSM Greeks unavailable")

        estimates = {}
        max_bsm_delta_error = 0.0
        max_bsm_gamma_error = 0.0
        exercise_profiles = set()
        for bump in SPOT_BUMPS:
            sample_spots = (
                scenario.spot * (1.0 - bump),
                scenario.spot,
                scenario.spot * (1.0 + bump),
            )
            for steps in TREE_STEPS:
                result = american_crr_greeks(
                    option,
                    market,
                    model,
                    steps,
                    relative_spot_bump=bump,
                )
                if result is None:
                    raise AssertionError(
                        f"{scenario.name}: unexpected unavailable Greeks"
                    )
                delta, gamma = result
                estimates[bump, steps] = result
                profile = tuple(
                    _exercise_state(scenario, model, spot, steps)
                    for spot in sample_spots
                )
                exercise_profiles.add(profile)

                delta_error = (
                    abs(delta - expected.delta) if expected is not None else None
                )
                gamma_error = (
                    abs(gamma - expected.gamma) if expected is not None else None
                )
                if delta_error is not None:
                    max_bsm_delta_error = max(
                        max_bsm_delta_error, delta_error
                    )
                    max_bsm_gamma_error = max(
                        max_bsm_gamma_error, gamma_error
                    )

                result_rows.append(
                    (
                        scenario.name,
                        bump,
                        steps,
                        delta,
                        gamma,
                        delta_error,
                        gamma_error,
                        "/".join(profile),
                    )
                )

        max_bump_delta = max(
            abs(estimates[left, steps][0] - estimates[right, steps][0])
            for left, right in zip(SPOT_BUMPS, SPOT_BUMPS[1:])
            for steps in TREE_STEPS
        )
        max_bump_gamma = max(
            abs(estimates[left, steps][1] - estimates[right, steps][1])
            for left, right in zip(SPOT_BUMPS, SPOT_BUMPS[1:])
            for steps in TREE_STEPS
        )
        max_step_delta = max(
            abs(estimates[bump, left][0] - estimates[bump, right][0])
            for bump in SPOT_BUMPS
            for left, right in zip(TREE_STEPS, TREE_STEPS[1:])
        )
        max_step_gamma = max(
            abs(estimates[bump, left][1] - estimates[bump, right][1])
            for bump in SPOT_BUMPS
            for left, right in zip(TREE_STEPS, TREE_STEPS[1:])
        )
        summary_rows.append(
            (
                scenario.name,
                max_bump_delta,
                max_step_delta,
                max_bump_gamma,
                max_step_gamma,
                max_bsm_delta_error if expected is not None else None,
                max_bsm_gamma_error if expected is not None else None,
                len(exercise_profiles),
            )
        )

    print(
        "American CRR Greek diagnostic "
        f"(bumps={SPOT_BUMPS}, steps={TREE_STEPS}, "
        f"stability tolerances: delta={DELTA_STABILITY_TOLERANCE:g}, "
        f"gamma={GAMMA_STABILITY_TOLERANCE:g})"
    )
    print(
        "case\tbump\tsteps\tdelta\tgamma\tBSM_delta_abs_error"
        "\tBSM_gamma_abs_error\texercise(S-h/S/S+h)"
    )
    for row in result_rows:
        name, bump, steps, delta, gamma, delta_error, gamma_error, profile = row
        print(
            f"{name}\t{bump:.4g}\t{steps}\t{delta:.9g}\t{gamma:.9g}\t"
            f"{'' if delta_error is None else f'{delta_error:.6g}'}\t"
            f"{'' if gamma_error is None else f'{gamma_error:.6g}'}\t"
            f"{profile}"
        )

    print(
        "\nNeighbor stability summary (max absolute change over adjacent "
        "bump sizes / adjacent step counts)"
    )
    print(
        "case\tdelta_bump\tstatus\tdelta_steps\tstatus\tgamma_bump\tstatus"
        "\tgamma_steps\tstatus\tmax_BSM_delta_error\tmax_BSM_gamma_error"
        "\texercise_profiles"
    )
    for row in summary_rows:
        (
            name,
            bump_delta,
            step_delta,
            bump_gamma,
            step_gamma,
            bsm_delta_error,
            bsm_gamma_error,
            profile_count,
        ) = row
        print(
            f"{name}\t{bump_delta:.6g}\t"
            f"{_is_stable(bump_delta, DELTA_STABILITY_TOLERANCE)}\t"
            f"{step_delta:.6g}\t"
            f"{_is_stable(step_delta, DELTA_STABILITY_TOLERANCE)}\t"
            f"{bump_gamma:.6g}\t"
            f"{_is_stable(bump_gamma, GAMMA_STABILITY_TOLERANCE)}\t"
            f"{step_gamma:.6g}\t"
            f"{_is_stable(step_gamma, GAMMA_STABILITY_TOLERANCE)}\t"
            f"{'' if bsm_delta_error is None else f'{bsm_delta_error:.6g}'}\t"
            f"{'' if bsm_gamma_error is None else f'{bsm_gamma_error:.6g}'}\t"
            f"{profile_count}"
        )

    boundary_profiles = {
        state
        for name, _, _, _, _, _, _, profile in result_rows
        if name == "put_boundary_crossing"
        for state in profile.split("/")
    }
    if len(boundary_profiles) < 2:
        raise AssertionError("Missing put boundary exercise classifications")
    exercise_put_profiles = {
        profile
        for name, _, _, _, _, _, _, profile in result_rows
        if name == "put_itm_exercise"
    }
    if exercise_put_profiles != {"exercise/exercise/exercise"}:
        raise AssertionError(
            "The deep ITM put did not exercise at every sampled spot"
        )
    print(
        "\nPASS: fixed small sweep completed; put boundary case shows both "
        "exercise and continuation among bumped samples/step counts"
    )


if __name__ == "__main__":
    main()
