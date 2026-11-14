# VolEdge — P0 Specification

Prepared 18 October 2026. Version 0.1. Initial European BSM scope, §2 pricing conventions, and fixture-scoped independent reference tolerances are approved. P0 is closed for those gates and fixtures only. American CRR, its one-step references, contract-complete native exposure, and experimental American Greeks are early P1 work.

## 1. Purpose and first release

VolEdge is a Python/C++20 derivatives simulation, risk and trading laboratory. Python owns validated research inputs, orchestration, experiments, reporting and visualization. C++ owns numerical kernels. pybind11 connects them. Rust is deferred.

Agreed first pricing milestone: European calls and puts on a single positive underlying with continuous dividend yield, priced with Black–Scholes–Merton (BSM). Start with synthetic, explicitly labeled inputs; market data and execution adapters are deferred. Outputs are price, delta, gamma, vega, theta and rho. This scope provides an analytical benchmark for subsequent Monte Carlo and risk phases.

American exercise is a separate milestone using a CRR binomial tree; it is not part of the European BSM implementation. The approved Python reference CRR convention is: u=exp(sigma*sqrt(dt)), d=1/u, p=(exp((r-q)*dt)-d)/(u-d), continuation discount exp(-r*dt), and exercise at each tree date. Probabilities outside [0,1] are rejected, not clamped; at zero volatility the deterministic risk-neutral path is rolled back with exercise at each requested date; expiry returns intrinsic. Python and scalar C++20 CRR implementations are present, including a scalar pybind11 binding to the existing C++ kernel. Python-to-C++ and compiled-binding parity checks cover prices and invalid inputs. Python additionally estimates CRR delta and gamma with centered spot bumps; native American Greeks and batch pricing are deferred. Exercise style is a property of the option contract and must not be inferred from its listing venue or the venue's region. Other deferred work includes exotic options, implied-volatility calibration, Black-76, Bachelier, PDE, Heston/jumps, multi-asset correlation, optimization and live execution.

## 2. Approved pricing conventions

| Item | Approved rule |
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
| American CRR delta/gamma | Python finite differences only: h=0.001*S by default, configurable positive relative bump; centered two-point delta and three-point gamma; tuple (delta, gamma); unavailable at expiry and zero volatility; reject S-h<=0 |

The absence of dates is deliberate: no day-count convention is silently selected. Any later market calendar/date adapter needs a documented decision.

The CRR step-count bound is a resource limit for the O(steps^2) Python tree.
Its zero-volatility rule and strict invalid-probability handling are recorded
above; no probability clipping is performed.

The approved Python-only CRR delta/gamma estimate uses
h=relative_spot_bump*S (default 0.001*S), delta=[V(S+h)-V(S-h)]/(2h), and
gamma=[V(S+h)-2V(S)+V(S-h)]/h^2, holding the tree step count fixed across
the three prices. It returns None at expiry or zero volatility and raises
ValueError when S-h is nonpositive; no clamping or one-sided fallback is
used. These finite-tree estimates can be unstable near exercise boundaries
and sensitive to bump size and tree steps; monotone convergence is not
assumed. This convention does not add Greeks to the C++ kernel or binding.

## 3. Model registry

European model identifier: `bsm_continuous_yield_v1`; American model
identifier: `crr_continuous_yield_v1`. They are separate registry entries;
each pricing API rejects IDs that do not match the selected pricer.
Instrument identifiers: `european_call_v1` and `european_put_v1`. Python
reference, scalar C++20 implementation and pybind11 binding are present.

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

## 4. Typed contract and additive API

The owner approved an additive migration on 11 November 2026: preserve all
legacy constructors, function signatures, return values, and CLI behavior;
add a contract-complete API rather than populating absent metadata with
fabricated values. The new API requires caller-supplied nonempty `run_id`,
preserved verbatim so multiple pricing results can share one run identifier.

| Type | Fields and rules |
|---|---|
| Instrument | kind: call/put enum; strike: positive float; maturity_years: nonnegative float; currency: nonempty string |
| PricingRequest metadata | currency: nonempty string matching the instrument currency; snapshot_id: nonempty string; source_kind: synthetic/recorded; model_id; caller-supplied nonempty run_id. Python `Option` includes currency and checks equality. The legacy-compatible C++ `Option` has no currency field; for `ContractPricingRequest`, its nonempty `currency` field is authoritative and preserved in the result. |
| PricingRequest model | European exercise requires `bsm_continuous_yield_v1`; American exercise requires `crr_continuous_yield_v1`; reject mismatches. CRR additionally requires valid integer steps. |
| ModelParameters | volatility: nonnegative finite float; model ID is required in the metadata-complete pricing request |
| PricingResult | unit_price: finite float; currency; optional Greeks; diagnostic codes; model_id; run_id; snapshot_id; source_kind |
| Greeks | delta, gamma, vega, theta, rho: finite floats with the units above |
| SimulationConfig | proposed future seed, path_count, time_steps, variance_reduction and RNG algorithm/version |
| SimulationResult | proposed future estimate, standard_error, confidence_interval, sample_count, timing and run metadata |
| RiskReport | proposed future base_value, exposure totals, scenario P&L and explicitly defined loss-tail metrics |

No portfolio/simulation fields become active APIs in P0. Risk-tail confidence levels, horizons and quantile rules remain pending P3 specification.

Initial pricing request: instrument + market state + model parameters. Python validates before calling C++; C++ independently validates for native callers. Wrong types, enum values, nonfinite numbers and invalid domains produce explicit errors. Python must reject booleans masquerading as numeric inputs. Inputs outside documented computational support produce a numerical-range error rather than silent clipping.

At T=0 or sigma=0, the new result returns a finite boundary price, Greeks
unavailable, and explicit reason code(s) `greeks_unavailable_expiry` and/or
`greeks_unavailable_zero_volatility`. Legacy APIs retain their existing
`None`/`nullopt` behavior and do not synthesize metadata. At American exercise
interior points the contract result reports `greeks_not_implemented`;
experimental Python American delta/gamma remain separate and are not attached
to this result. No silent zero Greeks. Do not turn validation failures into a
valid-looking PricingResult.

P0 contract review: this section defines the approved additive request/result
contract, caller-supplied run ID, model selection, units, boundary diagnostics,
and error behavior while preserving legacy API compatibility. At the `eb61377`
base, the executable implementation is the typed legacy Python/C++ BSM input
and output surface; the contract-complete `PricingRequest`/`PricingResult`,
American CRR request handling, and C++/pybind contract exposure are separate
early-P1 implementation. No implementation evidence for those early-P1 APIs
is included in this P0 checkpoint.

## 5. Binding contract

P1 begins with scalar pricing; batching is deferred unless explicitly scoped. Future batch arrays must be float64, C-contiguous, documented shape and explicit ownership. Reject wrong dtype/shape without implicit conversion. Check dimensions and size bounds before allocation. Use owned output arrays; never return views into freed C++ memory. Release the GIL only around independent native computation that does not access Python objects. Map domain errors to ValueError and computational failures to a documented exception. Test scalar behavior, exceptions and any exposed ownership behavior under sanitizers.

## 6. Reference cases and acceptance plan

Owner-approved fixture-scoped tolerances (12 November 2026): analytical BSM prices and Greeks use `abs_tol=1e-10`, `rel_tol=1e-10`; expiry payoffs are exact; the listed zero-volatility call uses `abs_tol=1e-12` and put uses `abs_tol=1e-10`. These European BSM references support P0. The supplemental early-P1 one-step CRR call/put hand fixtures use `abs_tol=1e-12`; they are not a P0 gate. These approvals apply only to listed references. Identity checks use `abs_tol=1e-10`, `rel_tol=1e-10` on moderate-scale fixtures. The proposed finite-difference Greek check `abs_tol=1e-5`, `rel_tol=1e-4` remains a separate numerical diagnostic, not part of this independent reference approval.

| Case | Inputs | Expected behavior |
|---|---|---|
| A: ordinary benchmark | S=100,K=100,T=1,r=0.05,q=0,sigma=0.20 | Compare against the independently calculated BSM-1/2 references in `VolEdge_P0_Reference_Cases.md`; separately run implementation parity |
| B: dividends | Same with q=0.02 | Compare against BSM-3/4 references; dividend-adjusted parity is a separate identity check |
| C: expiry ITM call | S=110,K=100,T=0 | Call=10, put=0; Greeks unavailable |
| D: expiry ATM | S=K=100,T=0 | Both prices=0; Greeks unavailable |
| E: deterministic ATM | S=K=100,T=1,r=q=0,sigma=0 | Both prices=0; Greeks unavailable |
| F: negative rate | S=K=100,T=1,r=-0.01,q=0,sigma=0.20 | Finite price or explicit numerical failure; parity on successful outputs |
| G: invalid inputs | S<=0,K<=0,T<0,sigma<0,NaN,infinity | Explicit validation error |
| H: numerical range | Extreme finite rates/maturities and very small positive volatility | Documented finite output or explicit numerical-range error |
| I: parameter grids | Moneyness, maturity and volatility grids | Bounds, monotonicity and cross-language agreement |

`docs/VolEdge_P0_Reference_Cases.md` records independently calculated
interior BSM price/Greek values and direct payoff/deterministic boundary
references for P0. It also labels the hand-calculated one-step CRR fixture as
supplemental early-P1 evidence. The BSM calculation is reproducible with
`tests/independent_reference_check.py`, uses `statistics.NormalDist().cdf`,
and does not import VolEdge; `tests/test_p0_references.py` checks the Python
BSM implementation against the approved constants. The Python/C++ baseline
and its parity tests are in the `eb61377` base. Property grids and
cross-language parity remain consistency checks, not independent accuracy
evidence. The owner approved the listed manifest and tolerances on 12
November 2026; no accuracy claim beyond those cases is implied.

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

The tested build tools are pinned in `requirements-build.txt`: CMake 4.4.4
and pybind11 3.1.0. The recorded WSL environment uses the project `.venv`,
Python 3.14.4, and GCC 15.2. The exact verification sequence from the
repository root is:

    source .venv/bin/activate
    cmake -S . -B build-wsl-clean-20261111 -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
    cmake --build build-wsl-clean-20261111 --parallel
    PYTHONPATH=python python -m unittest discover -s tests -v
    ctest --test-dir build-wsl-clean-20261111 --output-on-failure
    PYTHONPATH=python python tests/american_crr_greek_diagnostic.py
    git diff --check

The isolated P0 checkpoint verification commands and results are recorded
below. Later-phase status and Studio history remain outside this checkpoint.
Python/C++ and binding parity checks compare implementations on
fixed fixtures; agreement is not independent numerical validation or evidence
of general accuracy. Python tests now include a modest BSM property grid and
the native parity check covers a modest parameter grid. Independent BSM
references and a hand CRR calculation are presented and approved in
`VolEdge_P0_Reference_Cases.md`, with the exact fixture scope stated.
Sanitizer and CI evidence are not complete; these are not P0 exit criteria
for this scalar scope.

## 9. Phase gates

P0: approved initial scope and conventions; model registry; reviewed input/output/error contracts; threat model; reference-case manifest and acceptance tolerances. P1: implemented Python oracle and C++ core, checked bindings, passing numerical/native suites and reproducible build evidence. P2: seeded MC, variance reduction, uncertainty and convergence. P3: reconciled portfolio/scenario risk and defined tails. P4: cost-aware no-lookahead replay with baselines. P5: reconciled paper OMS with hard-limit and kill-switch evidence.

## 10. P0 acceptance audit and next action

| P0 exit criterion | Status | Evidence / remaining work |
|---|---|---|
| Approved initial instrument and model scope | PASS | §1 defines European calls/puts with continuous-yield BSM first; §3 records assumptions and instrument IDs. Exercise style is contractual, not inferred from listing venue. American CRR, scalar bindings and Python experimental American delta/gamma are early P1 deliverables, not requirements that redefine P0. |
| Approved pricing conventions | PASS | §2 records currency, positive spot/strike, supplied year fraction, annual decimal volatility/rates, continuous compounding, Greek units and expiry/zero-vol behavior. `tests/test_p0_references.py` checks the independent BSM and boundary fixtures against the Python reference. Contract-result diagnostic codes are an additive extension; their compiled exposure is early P1. |
| Model registry and assumptions | PASS for P0 model | §3 defines European `bsm_continuous_yield_v1`, option types, formulas, assumptions, bounds and identities. The separately registered CRR model and its implementation are early P1. |
| Reviewed typed input/output/error contracts | PASS for European BSM foundation | §4 records the additive compatibility decision, caller-supplied run ID, metadata and boundary diagnostics for the BSM contract. The legacy-compatible pricing inputs and Python validation are documented; the new contract-complete API, American CRR handling and C++/pybind exposure are early P1. No legacy call fabricates provenance. |
| Threat model | PASS (documented gate) | §7 identifies input validation, native-boundary, numerical, reproducibility, dependency/artifact, secrets, resource and trading risks, with controls and phase-specific evidence. §8/§9 distinguish future controls from P0 documentation. Sanitizers, fuzzing, secrets scans and later-phase controls are not claimed as completed P0 evidence. |
| Reference-case manifest and acceptance tolerances | PASS (fixture-scoped) | Owner approved the exact tolerances on 12 November 2026: analytical BSM price/Greeks `abs_tol=1e-10`, `rel_tol=1e-10`; expiry payoff exact; zero-vol call `abs_tol=1e-12`; zero-vol put `abs_tol=1e-10`. `docs/VolEdge_P0_Reference_Cases.md` gives derivations; `tests/independent_reference_check.py` independently regenerates 42 values and compares the constants; `tests/test_p0_references.py` asserts the European BSM prices/Greeks and boundaries against the Python implementation. One-step CRR call/put fixtures use `abs_tol=1e-12` as supplemental early-P1 evidence, not a P0 gate. No general accuracy claim is made. |
| Reproducible repository evidence | PASS as corroboration, not an approval substitute | Isolated WSL candidate run: independent reference generator checked 42 values; full Python suite passed 32 tests; Release native build passed; CTest passed 4/4; `git diff --check` passed. These checks corroborate implementation/reproducibility only; parity/build results are not independent numerical accuracy evidence. |
| P0 gate | PASS / CLOSED after this audit | All P0 criteria above are verified from the approved specification and repository evidence. The §6 A–I table is a broader implementation acceptance plan; grids, compiled bindings and CRR are early P1 verification, not additional P0 approvals. |

Exercise style is a contract field and is independent of listing venue or
listing region; README and the Python contract agree. BSM Greek units are
consistent between §2, `pricing.py`, the C++ kernel, and README: vega/rho are
per absolute decimal change and theta is calendar-time `-dV/dT`. The
one-step American CRR fixtures can exercise at the root; in the listed
at-the-money cases, root exercise pays zero while continuation is positive.
Their one-step parity with the European tree does not test early rollback.

Reference-test mapping: `tests/independent_reference_check.py` generates
independent BSM, boundary and supplemental one-step CRR constants without
importing VolEdge. `tests/test_p0_references.py` checks P0 BSM prices/Greeks,
expiry and zero-volatility outputs against the Python implementation.
`test_american_crr_one_step_hand_reference_without_dividends` and
`test_american_put_early_exercise_adds_value` are early-P1 CRR tests; the
latter is the multi-step rollback case. Python/C++ and binding parity checks
are consistency evidence only.

Isolated candidate commands (WSL, project `.venv`):

    source /mnt/c/Users/olaju/Desktop/voledge/.venv/bin/activate
    PYTHONPATH=python python tests/independent_reference_check.py
    PYTHONPATH=python python -m unittest discover -s tests -v
    cmake -S . -B build-p0-review -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/mnt/c/Users/olaju/Desktop/voledge/.venv/bin/python
    cmake --build build-p0-review --parallel
    ctest --test-dir build-p0-review --output-on-failure
    git diff --check

Observed results: 42 reference values matched; 32 Python tests passed; the
Release build succeeded; all 4 CTest checks passed; and the candidate diff
check passed. The native tests include the base commit's early-P1 CRR/parity
checks; these remain distinct from independent P0 reference evidence.

### Closeout hindsight

- **Gate sequencing:** At `eb61377`, this specification still opened with
  “Status: specification draft” and said remaining conventions needed owner
  approval. Work subsequently advanced into CRR and binding milestones before
  a per-criterion P0 PASS/GAP record was maintained. This audit records each
  P0 exit criterion and separates those early P1 deliverables.
- **Parity versus accuracy:** An eight-case parity result and zero observed
  difference establish agreement only for those implementations and fixtures.
  The independent reference manifest is separate; neither parity nor its
  number of cases proves general accuracy.
- **Convention and binding scope:** Exercise style belongs to the contract,
  not venue/region. BSM Greeks use per-unit delta/gamma, vega/rho per absolute
  decimal change, and calendar-time theta `-dV/dT`. Legacy boundary APIs keep
  `None`/`nullopt`; only the new result attaches unavailable-Greek reason
  codes. The compiled extension exposes both legacy scalar calls and the
  additive contract API; it does not expose native American Greeks.
- **Experimental American Greeks:** The 0.1% default bump is retained, not
  validated as generally accurate. At 800 steps the ATM call gamma changed
  from `0.2652518` at the default bump to `0.0190562` at a 5% bump, compared
  with BSM gamma `0.0187620`; the broader diagnostic records larger
  instability near exercise boundaries. These finite-tree measurements do
  not justify changing the default or claiming convergence.

Tracker entry:
| Phase | Status | Commit | Evidence | Blocker | Next action |
|---|---|---|---|---|---|
| P0 | COMPLETE / CLOSED | `eb61377` HEAD; audited worktree remains uncommitted | Owner-approved scope/conventions/contracts and fixture references; current WSL verification in `steps.md`: 76 Python tests, Release build, 5/5 CTest, diagnostic, diff checks | No P0 blocker. Experimental American gamma instability remains a separate early-P1 validation limitation, not a P0 gate. | Continue later-phase work without broadening the approved numerical-accuracy claim |

## Sources

AGENT-voledge.md and the VolEdge section (physical pages 14–27) of Quant_Architecture_Visual_Complete(3).pdf, supplied by the user. Initial scope, detailed units/error decisions and tolerances above are explicitly proposed elaborations of that baseline.
