# VolEdge — P0 Specification

Prepared 18 October 2026. Version 0.1. Status: specification draft; initial European BSM scope is agreed, while remaining pricing conventions require owner approval.

## 1. Purpose and first release

VolEdge is a Python/C++20 derivatives simulation, risk and trading laboratory. Python owns validated research inputs, orchestration, experiments, reporting and visualization. C++ owns numerical kernels. pybind11 connects them. Rust is deferred.

Agreed first pricing milestone: European calls and puts on a single positive underlying with continuous dividend yield, priced with Black–Scholes–Merton (BSM). Start with synthetic, explicitly labeled inputs; market data and execution adapters are deferred. Outputs are price, delta, gamma, vega, theta and rho. This scope provides an analytical benchmark for subsequent Monte Carlo and risk phases.

American exercise is a separate milestone using a CRR binomial tree; it is not part of the European BSM implementation. The approved Python reference CRR convention is: u=exp(sigma*sqrt(dt)), d=1/u, p=(exp((r-q)*dt)-d)/(u-d), continuation discount exp(-r*dt), and exercise at each tree date. Probabilities outside [0,1] are rejected, not clamped; at zero volatility the deterministic risk-neutral path is rolled back with exercise at each requested date; expiry returns intrinsic. Python and scalar C++20 CRR implementations are present and checked by a Python-to-C++ parity test; American Greeks and pybind11 bindings are deferred. Exercise style is a property of the option contract and must not be inferred from its listing venue or the venue's region. Other deferred work includes exotic options, implied-volatility calibration, Black-76, Bachelier, PDE, Heston/jumps, multi-asset correlation, optimization and live execution.

## 2. Proposed conventions — approval pending

| Item | Proposed rule |
|---|---|
| Currency | One explicitly supplied currency per run; no implicit FX conversion |
| Spot/strike | Currency per underlying unit; strictly positive |
| Contract price | Value per underlying unit; multiplier applied once at portfolio layer |
| Time | Nonnegative year fraction T supplied directly to the initial engine |
| Date adapter | Deferred; no automatic calendar, business-day adjustment or day-count conversion |
| Volatility | Annualized decimal; 0.20 means 20%; nonnegative |
| Rate r and dividend yield q | Annualized, continuously compounded decimals; finite negative values allowed |
| Exercise | First milestone: European, at expiry only; American exercise is a separate later CRR binomial-tree milestone |
| Settlement | Cash-equivalent terminal payoff; initial engine excludes settlement delays |
| Numeric precision | Python float and C++ double; reject nonfinite input/output |
| Vega/rho | Derivative per absolute decimal change; display per 1 percentage point by multiplying by 0.01 |
| Theta | Calendar-time decay per year, theta = -dV/dT; no per-day conversion in core |
| Position | Signed contract quantity times positive multiplier times unit price/Greek |
| Expiry | Price equals intrinsic; Greeks unavailable at T=0 in v0.1 |
| Zero volatility | Discounted deterministic payoff; Greeks unavailable at sigma=0 in v0.1 |
| American CRR step count | Python reference requires integer steps in [1, 10000] |

The absence of dates is deliberate: no day-count convention is silently selected. Any later market calendar/date adapter needs a documented decision.

The CRR step-count bound is a resource limit for the O(steps^2) Python tree.
Its zero-volatility rule and strict invalid-probability handling are recorded
above; no probability clipping is performed.

## 3. Model registry proposal

Model identifier: bsm_continuous_yield_v1. Instrument identifiers: european_call_v1 and european_put_v1. Python reference and scalar C++20 implementations are present; bindings remain deferred.

Assumptions: frictionless pricing benchmark, lognormal underlying, constant r/q/sigma over maturity, continuous dividend yield, European exercise. No claim that these assumptions describe observed markets. Pricing is a model value, not an executable quote.

For T>0 and sigma>0:

    d1 = [ln(S/K) + (r-q+sigma^2/2)T] / (sigma sqrt(T))
    d2 = d1 - sigma sqrt(T)
    C = S exp(-qT) N(d1) - K exp(-rT) N(d2)
    P = K exp(-rT) N(-d2) - S exp(-qT) N(-d1)

At T=0: C=max(S-K,0), P=max(K-S,0).
At sigma=0 and T>0: C=max(S exp(-qT)-K exp(-rT),0), with the reversed expression for P.

Required identities: C-P=S exp(-qT)-K exp(-rT); call delta minus put delta equals exp(-qT); call and put gamma/vega agree. Calls increase with S and decrease with K; puts have the reverse ordering. Vanilla option values increase with volatility away from degenerate boundaries.

Bounds: max(S exp(-qT)-K exp(-rT),0) <= C <= S exp(-qT); corresponding put bounds swap the discounted terms. Overflow/underflow and cancellation must be handled or rejected explicitly, never hidden as NaN.

## 4. Typed contract proposal

These are design contracts, not implemented public interfaces. Freeze them only after review.

| Type | Fields and rules |
|---|---|
| Instrument | kind: call/put enum; strike: positive float; maturity_years: nonnegative float; currency: nonempty string |
| MarketState | spot: positive float; rate: finite float; dividend_yield: finite float; snapshot_id: nonempty string; source_kind: synthetic/recorded |
| ModelParameters | model_id: bsm_continuous_yield_v1; volatility: nonnegative finite float |
| PricingResult | unit_price: finite float; currency; optional Greeks; diagnostic codes; model_id; run_id |
| Greeks | delta, gamma, vega, theta, rho: finite floats with the units above |
| SimulationConfig | proposed future seed, path_count, time_steps, variance_reduction and RNG algorithm/version |
| SimulationResult | proposed future estimate, standard_error, confidence_interval, sample_count, timing and run metadata |
| RiskReport | proposed future base_value, exposure totals, scenario P&L and explicitly defined loss-tail metrics |

No portfolio/simulation fields become active APIs in P0. Risk-tail confidence levels, horizons and quantile rules remain pending P3 specification.

Initial pricing request: instrument + market state + model parameters. Python validates before calling C++; C++ independently validates for native callers. Wrong types, enum values, nonfinite numbers and invalid domains produce explicit errors. Python must reject booleans masquerading as numeric inputs. Inputs outside documented computational support produce a numerical-range error rather than silent clipping.

At T=0 or sigma=0, return a finite boundary price, Greeks=null and a diagnostic explaining unavailability. No silent zero Greeks. Do not turn validation failures into a valid-looking PricingResult.

## 5. Binding contract

P1 begins with scalar pricing; batching is deferred unless explicitly scoped. Future batch arrays must be float64, C-contiguous, documented shape and explicit ownership. Reject wrong dtype/shape without implicit conversion. Check dimensions and size bounds before allocation. Use owned output arrays; never return views into freed C++ memory. Release the GIL only around independent native computation that does not access Python objects. Map domain errors to ValueError and computational failures to a documented exception. Test scalar behavior, exceptions and any exposed ownership behavior under sanitizers.

## 6. Reference cases and acceptance plan

Proposed numerical tolerances: analytical reference prices abs_tol=1e-10, rel_tol=1e-10; identity checks abs_tol=1e-10, rel_tol=1e-10 on moderate-scale fixtures. Proposed finite-difference Greek check abs_tol=1e-5, rel_tol=1e-4 on smooth interior cases. Review these against measured conditioning; do not silently widen tolerances to hide defects.

| Case | Inputs | Expected behavior |
|---|---|---|
| A: ordinary benchmark | S=100,K=100,T=1,r=0.05,q=0,sigma=0.20 | Compare Python/C++ against independently verified stored benchmark; parity and Greek checks |
| B: dividends | Same with q=0.02 | Dividend-adjusted parity and delta difference |
| C: expiry ITM call | S=110,K=100,T=0 | Call=10, put=0; Greeks unavailable |
| D: expiry ATM | S=K=100,T=0 | Both prices=0; Greeks unavailable |
| E: deterministic ATM | S=K=100,T=1,r=q=0,sigma=0 | Both prices=0; Greeks unavailable |
| F: negative rate | S=K=100,T=1,r=-0.01,q=0,sigma=0.20 | Finite price or explicit numerical failure; parity on successful outputs |
| G: invalid inputs | S<=0,K<=0,T<0,sigma<0,NaN,infinity | Explicit validation error |
| H: numerical range | Extreme finite rates/maturities and very small positive volatility | Documented finite output or explicit numerical-range error |
| I: parameter grids | Moneyness, maturity and volatility grids | Bounds, monotonicity and cross-language agreement |

Nontrivial case A/B expected prices are intentionally not fabricated here: calculate and cross-check independently in P1 before freezing reference fixtures. Boundary expectations above follow directly from the proposed payoff contract and have not been executed as tests.

For finite differences: bump each input with a scale-aware step, avoid crossing domain boundaries, compare multiple step sizes, and use theta=-dV/dT. Compare the dividend-adjusted analytical expressions with independent numerical differences. Gamma uses second differences and needs separate conditioning checks.

Python oracle agreement alone is insufficient because both implementations can share a formula bug. Include identities, boundary cases, dimensional checks and independently verified reference values.

## 7. Threat model

| Boundary/failure | Control | Evidence required |
|---|---|---|
| Untrusted financial input | Strict schemas; native validation; units explicit | Invalid-domain and nonfinite-input tests |
| Python/native memory boundary | Checked types/shapes/ownership; allocation limits | Binding tests; ASan/UBSan; malformed-input tests |
| Wrong formula/Greek units | Independent references, parity and finite differences | Numerical test report with tolerances |
| Nondeterministic simulation | Pin RNG/environment; persist seed and configuration | Later P2 replay and convergence evidence |
| Future data leakage | Availability timestamps and chronological replay | Later P4 point-in-time tests |
| Tampered dependencies/artifacts | Pin and scan dependencies; verify trusted checksums/signatures; safe loaders | Dependency inventory and artifact verification tests |
| Secrets in source/logs | No credentials required for initial scope; redacted logs | Secrets scan before release |
| Oversized jobs | Explicit limits before allocating paths/grids | Resource-limit tests in relevant phase |
| Unreconciled paper orders | Order state machine, risk gates, kill switch | Later P5 failure injection and reconciliation |

No real-order adapter in initial scope. Paper outcomes never authorize real capital.

## 8. Reproducibility and repository plan

Proposed layout: python/voledge/, cpp/include/, cpp/src/, cpp/tests/, bindings/, tests/fixtures/, docs/, notebooks/. Keep notebooks exploratory.

Every experiment records: run ID, UTC creation time, immutable input snapshot/hash, schema/model version, source commit, dirty-tree indicator, Python/compiler/CMake/binding versions, build configuration, dependency versions, source-data identifiers, numerical tolerances and diagnostics. Stochastic runs additionally record seed, RNG algorithm/version, path count and variance-reduction configuration.

Tool versions must be inspected and pinned during setup; none are asserted installed by this document. CMake, pybind11, pytest/Hypothesis and GoogleTest or Catch2 are proposed tools. Choose the native test framework and dependency versions before installing major dependencies.

Reproducible verification commands:

    g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror -Icpp/include cpp/src/bsm.cpp cpp/src/bsm_cli.cpp -o /tmp/voledge_bsm_cli
    PYTHONPATH=python python3 tests/cpp_parity_check.py /tmp/voledge_bsm_cli
    PYTHONPATH=python python3 -m unittest discover -s tests -v

The direct WSL build and parity command passed for eight price/Greek comparisons at absolute and relative tolerances of 1e-10; the Python suite passed 19 tests. The CMake/CTest path is defined in the repository but was not run because CMake is unavailable in the current WSL environment. Sanitizer flags, static checks and CI commands remain to be defined.

## 9. Phase gates

P0: approved initial scope and conventions; model registry; reviewed input/output/error contracts; threat model; reference-case manifest and acceptance tolerances. P1: implemented Python oracle and C++ core, checked bindings, passing numerical/native suites and reproducible build evidence. P2: seeded MC, variance reduction, uncertainty and convergence. P3: reconciled portfolio/scenario risk and defined tails. P4: cost-aware no-lookahead replay with baselines. P5: reconciled paper OMS with hard-limit and kill-switch evidence.

## 10. P0 acceptance audit and next action

| Requirement | Current state |
|---|---|
| Initial instrument and model scope | Agreed: European BSM first; Python/C++ American CRR is a separate reference milestone |
| Pricing units, maturity, boundaries and errors | Proposed; owner approval pending |
| Typed contract definitions | Python contracts and scalar C++ pricing types implemented |
| Threat model | Drafted; controls not yet implemented/tested |
| Reference cases and tolerances | Python benchmarks/finite differences, BSM binding parity, and 8-case Python/C++ CRR parity run; native comparison tolerance 1e-10 absolute and relative |
| Repository commit/build evidence | No commit; WSL direct C++20 build and parity verification completed |
| P0 gate | OPEN; specification prepared, decisions not frozen |

Initial scope decision: European calls/puts with continuous dividend yield come first; American exercise remains a separate CRR binomial-tree milestone. Exercise style is explicitly carried by the contract, independent of venue. Remaining conventions (direct year-fraction input, annual decimal units, and boundary prices with unavailable Greeks) remain subject to owner approval.

Tracker-ready entry:
P0/P1 | European BSM scope agreed; American CRR conventions approved separately | BSM/bindings commit 3a5a3e1; Python CRR commit 4e744a8 | Python unittest and CTest results recorded in steps.md | Python/C++ European BSM and Python/C++ American CRR parity; no CRR binding | American Greeks and pybind11 exposure deferred | continue numerical validation without requiring monotone tree convergence

## Sources

AGENT-voledge.md and the VolEdge section (physical pages 14–27) of Quant_Architecture_Visual_Complete(3).pdf, supplied by the user. Initial scope, detailed units/error decisions and tolerances above are explicitly proposed elaborations of that baseline.
