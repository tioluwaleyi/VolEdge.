# VolEdge

VolEdge is a Python/C++20 derivatives research project. The current pricing
milestone contains validated Python contracts, a European Black–Scholes–Merton
(BSM) reference pricer, and a scalar C++20 implementation with prices and
Greeks, exposed through a pybind11 extension. Both implementations use
continuous dividend yield. A Python-only American CRR reference pricer is also
available; the European BSM APIs, C++ implementation and bindings remain
unchanged.

## Conventions

- Spot and strike are positive; maturity is a nonnegative year fraction.
- Rates, continuous dividend yield and volatility are annual decimals.
- Theta is calendar-time decay per year (`-dV/dT`).
- Vega and rho are per 1.0 change in volatility and rate (multiply by 0.01
  for a one-percentage-point change).
- At expiry or zero volatility, the engine returns the boundary price and
  reports Greeks unavailable.
- The European BSM API rejects American exercise. The separate American CRR
  API requires an American contract; exercise style comes from the contract,
  not its venue.

## American CRR reference pricer

Import `american_crr_price` from `voledge.american`. It takes the existing
`Option`, `MarketState` and `ModelParameters` contracts plus an explicit
`steps` argument:

```python
from voledge.contracts import (
    ExerciseStyle,
    MarketState,
    ModelParameters,
    Option,
    OptionType,
)
from voledge.american import american_crr_price

option = Option(OptionType.PUT, ExerciseStyle.AMERICAN, 100.0, 1.0, "USD")
market = MarketState(95.0, 0.05, 0.02)
model = ModelParameters(0.20)
price = american_crr_price(option, market, model, steps=500)
```

The tree uses annual decimal volatility, continuously compounded annual rate
and dividend yield, `u=exp(sigma*sqrt(dt))`, `d=1/u`, and
`p=(exp((r-q)*dt)-d)/(u-d)`. At each node it takes the greater of immediate
exercise and continuation discounted by `exp(-r*dt)`. `steps` must be an
integer from 1 through 10,000. A risk-neutral probability outside `[0,1]`
raises `ValueError`; the implementation never clamps it.

At expiry the result is intrinsic value. At zero volatility a deterministic
risk-neutral spot path is rolled back, still allowing exercise at each of the
requested tree dates. The function returns a price only; American Greeks,
C++ CRR, and bindings are deferred. Large trees are computationally
expensive; convergence need not improve monotonically with each step count.

## Reproducible WSL setup

The tested build tools are pinned in `requirements-build.txt` (CMake 4.4.4
and pybind11 3.1.0). Run these commands from the repository root in WSL. They
reuse the project-local `.venv` and configure a new, dedicated build directory.
The system must provide a C++20 compiler and Python development headers.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python --version
cmake --version
python -m pybind11 --version
cmake -S . -B build-wsl-clean-20261111 -DCMAKE_BUILD_TYPE=Release \
  -DPython3_EXECUTABLE="$PWD/.venv/bin/python"
cmake --build build-wsl-clean-20261111 --parallel
```

The configure command selects the same `.venv` Python used for pybind11
discovery and the tests. The extension is emitted under
`build-wsl-clean-20261111/python`. Import the compiled module explicitly with:

```sh
PYTHONPATH=build-wsl-clean-20261111/python python -c \
  "import _voledge_native; print(_voledge_native.__file__)"
```

## Test

```sh
PYTHONPATH=build-wsl-clean-20261111/python:python \
  python tests/pybind_parity_check.py
PYTHONPATH=python python -m unittest discover -s tests -v
ctest --test-dir build-wsl-clean-20261111 --output-on-failure
```

The binding parity test imports `_voledge_native` directly and checks that
Python loaded a compiled extension, so it cannot silently use the reference
pricer as the native implementation. It compares price and all available
Greeks for calls and puts, including nonzero dividends, negative rates, expiry
and zero volatility, with `abs_tol=1e-10` and `rel_tol=1e-10`. It also checks
American exercise and invalid-spot error translation. CTest runs both this
binding check and the independent CLI parity check against the Python
reference.

The Python unittest suite also checks the American CRR one-step hand
calculation (absolute tolerance `1e-12`), early exercise value for a put, and
a non-dividend-paying call against European BSM at 2,000 steps (absolute
tolerance `0.01`). It tests expiry, zero volatility, invalid probabilities,
exercise style and step-count validation. Tree errors are not required to
decrease at every increase in the step count.