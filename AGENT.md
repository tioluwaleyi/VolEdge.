# AGENT.md: VolEdge

Guidance for AI coding agents working in this repository. Read this file fully before making changes.

## Project Overview

- **Name:** VolEdge
- **Purpose:** A Python/C++ derivatives simulation, risk and trading laboratory. It links financial simulation, derivatives pricing accuracy, portfolio risk and trading infrastructure in one reproducible research workflow.
- **Status:** Early implementation. Python input contracts and a European continuous-yield BSM reference pricer, a scalar C++20 BSM kernel, and a pybind11 extension are implemented. The current WSL verification uses Python 3.14.4, GCC 15.2, CMake 4.4.4 and pybind11 3.1.0; 19 Python unit tests and 2 CTest checks pass, including Python/native parity. The broader research, simulation, risk, strategy and execution architecture remains a proposal; do not claim components are complete unless built and verified in this repo.

## Architecture

Python owns the research workflow; C++ owns numerical kernels. Rust is optional and only justified if live trading needs a separate market-data/execution service. It must never duplicate the pricing engine.

```
Python research terminal (instrument builder, 2D/3D surfaces, simulation controls)
  -> Research orchestration and market data (point-in-time quotes, curves, calendars, experiments)
  -> C++20 numerical library (pricing, Greeks, calibration, PDE, Monte Carlo, optimization)
  -> Validation and portfolio risk (convergence, model error, exposures, VaR/ES, stress)
  -> Strategy research and event-driven backtest (hedging, spreads, costs, order simulation)
  -> Paper trading, audit and visualization (orders, P&L, risk limits, lineage)
```

## Tech Stack

- **Python:** research orchestration, Pydantic-style input validation, experiment runner, dashboard, reports, notebooks
- **C++20:** performance-critical numerical algorithms
- **Bindings:** pybind11 (explicit array ownership, shape/dtype checks, exception mapping, GIL release for independent compute)
- **Build:** CMake; pin the Python and compiler versions in the repo and record them with each run
- **Testing:** pytest and Hypothesis (Python), GoogleTest or Catch2 (C++), ASan/UBSan for native code

Adjust these to match the actual repo once it has files.

## Suggested Repository Layout

```
.
├── python/voledge/     # Research workflow, validation, orchestration, UI
├── cpp/                # C++20 numerical library
│   ├── include/
│   └── src/
├── bindings/           # pybind11 module
├── tests/              # Python tests, reference fixtures, property tests
├── cpp/tests/          # Native unit tests
├── docs/               # Convention sheet, model registry, threat model
├── notebooks/          # Exploration only, never production logic
└── AGENT.md
```

## Setup Commands

Fill in once the build system exists.

```bash
# Python environment
<create venv and install dependencies>

# Configure and build C++ (with sanitizers for test builds)
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# Tests
pytest
ctest --test-dir build
```

## Numerical Engines and Validation

| Engine | Candidate algorithms | Validation |
|---|---|---|
| Analytical | BSM with dividends, Black-76, Bachelier | Known values, put-call parity, finite-difference Greeks |
| Trees / PDE | CRR binomial, finite-difference Black-Scholes PDE | Convergence against analytical benchmarks |
| Stochastic simulation | GBM, Heston, jumps, correlated paths | Fixed seed, distribution checks, confidence intervals |
| Volatility | Implied-vol root finding, SVI / SABR calibration | Residuals, no-arbitrage checks, holdout quotes |
| Risk | Greeks, scenario P&L, VaR / ES | Backtesting, stress-case consistency |
| Optimization | Hedge constraints, calibration objectives | Feasibility, solver convergence, baselines |

## Core Contracts

- **C++ types:** `Instrument`, `MarketState`, `ModelParameters`, `PricingResult`, `Greeks`, `SimulationConfig`, `SimulationResult`, `RiskReport`.
- **Python:** validate all inputs before they reach native code; orchestrate experiments; generate reports.
- **Every run** records the random seed, model/version identifiers, build version and an input snapshot, so results are reproducible.
- A Python BSM implementation serves as the reference oracle for the C++ BSM/Greeks.

## Coding Conventions

- Match the existing style of the file you are editing; do not reformat unrelated code.
- State units and conventions explicitly (volatility as annualized decimal, rates continuously compounded, day-count and calendar choice documented in the convention sheet).
- Use type hints on all public Python functions and strong types in C++ interfaces. Avoid raw pointers and unchecked casts across the binding boundary.
- Invalid financial inputs (T=0, sigma=0, negative spot, extreme rates) must either return a documented finite result or raise an explicit error. Never return silent NaNs.
- Keep numerical kernels deterministic given a seed. Do not introduce non-determinism through unordered containers or thread races.
- No dead code, commented-out blocks or stray debug prints in commits.

## Testing Requirements

- Every behavior change needs a test. Do not weaken or delete a test to make it pass.
- **Reference tests:** compare against known values and the Python oracle within declared absolute and relative tolerances.
- **Property tests:** put-call parity, monotonicity, boundary inputs.
- **Greeks:** verify against finite differences and check dimensions and units.
- **Monte Carlo:** seed replay, antithetic checks, standard error and convergence against analytical benchmarks.
- **Native bindings:** malformed arrays, wrong shapes and dtypes, ownership tests, ASan/UBSan runs.
- **Data and backtests:** point-in-time checks to prove no future information is used.
- Run the full Python and C++ suites before declaring a task complete, and report real results.

## Delivery Phases

Follow P0 to P5 in order. A phase starts only after the previous phase's gate passes. A failed gate loops back to the phase that produced the defect.

| Phase | Deliverable | Exit gate |
|---|---|---|
| P0 Specification | Model registry, conventions, threat model, typed contracts | Each instrument has explicit assumptions, valid inputs and error behavior |
| P1 Math core | Python BSM oracle, C++ BSM/Greeks, checked pybind11 bindings | Parity and finite-difference checks pass declared tolerances |
| P2 Simulation | MC engine, variance reduction, convergence UI | Seed replay repeatable; estimates converge against benchmarks |
| P3 Risk | Portfolio Greeks, scenarios, VaR/ES | Scenario totals reconcile with position repricing; tail conventions documented |
| P4 Strategy | Hedging replay and event-driven backtest | No-lookahead checks pass; results include costs and baseline comparisons |
| P5 Paper execution | Risk-gated OMS and monitoring | Rejects and partial fills reconcile; hard breach blocks new orders |

**Progress rule:** record Planned, Implemented, Tested and Blocked separately. A diagram or a passing unit test alone does not close a phase.

**Tracker entry format:** `Phase | status | commit/data version | test command | result | blocker | next action`

## Boundaries

### Always
- Check array types, shapes and ownership at the Python/C++ boundary.
- Record seeds, versions and assumptions with every experiment.
- Report estimates with uncertainty (standard error or confidence interval).
- State known limitations alongside results.

### Ask first
- Adding or upgrading major dependencies, or introducing Rust.
- Changing public C++ types, binding signatures or the model registry.
- Choosing market conventions that affect pricing results.
- Large refactors or deleting files.

### Never
- Commit secrets, API keys or credentials.
- Load model artifacts that are not signed or checksummed, and never use unsafe deserialization.
- Fabricate benchmark numbers, test output or convergence results.
- Let future information leak into a backtest or calibration.
- Treat paper-trading results as approval for real capital. Any live trading requires independent review.
- Place orders after a hard risk-limit breach; fail closed and keep an operator kill switch.

## Security and Numerical Checkpoints

| Failure | Test | Exit requirement |
|---|---|---|
| Invalid financial inputs | Property tests: T=0, sigma=0, negative spot, extreme rates | Documented finite result or explicit error |
| Wrong Greeks/units | Finite differences, dimensional checks | Within specified tolerances |
| Monte Carlo bugs | Seed replay, antithetic checks, convergence tests | Stable estimates and error bars |
| Unsafe native bindings | ASan/UBSan, fuzz malformed arrays, ownership tests | No crashes or out-of-bounds access |
| Data leakage | Point-in-time feature and split tests | No future information used |
| Model artifact attacks | Signed/checksummed artifacts, safe deserialization | Only trusted models loaded |
| Trading loss controls | Stale quotes, rejects, partial fills, kill switch | No new orders after hard-limit breach |

General gates: pin and scan dependencies, enforce strict schemas and units, run CI with static checks, unit, integration and fuzz/property tests, and use reproducible builds.

## Release Evidence

Every milestone needs a source commit, a reproducible command, test output, a benchmark or experiment artifact, and documented known limitations. A green unit-test suite does not prove market profitability, model calibration quality or production security.

## Commit and PR Guidelines

- Imperative, concise subject lines (e.g. `Add C++ BSM Greeks with finite-difference tests`).
- PRs state the problem, the solution, the phase it belongs to and how it was verified.
- Keep PRs small enough to review in one sitting.

## Known Issues and Gotchas

- The current native pricing scope is European BSM only; American CRR, NumPy/batch pricing, and installed-package behavior are not implemented or verified.
- The recorded build and test verification is for WSL/Linux with the tool versions stated above; other operating systems, compilers and Python versions remain unverified.
