# VolEdge

VolEdge is a Python/C++20 derivatives research project. The current pricing
milestone contains validated Python contracts, a European Black–Scholes–Merton
(BSM) reference pricer, and a scalar C++20 implementation with prices and
Greeks, exposed through a pybind11 extension. Both implementations use
continuous dividend yield; no American pricer is included yet.

## Conventions

- Spot and strike are positive; maturity is a nonnegative year fraction.
- Rates, continuous dividend yield and volatility are annual decimals.
- Theta is calendar-time decay per year (`-dV/dT`).
- Vega and rho are per 1.0 change in volatility and rate (multiply by 0.01
  for a one-percentage-point change).
- At expiry or zero volatility, the engine returns the boundary price and
  reports Greeks unavailable.
- BSM rejects American exercise. American exercise is planned separately with
  a CRR binomial tree; exercise style comes from the contract, not its venue.

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