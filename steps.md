European BSM milestone remains verified: Python BSM and scalar C++/pybind11 parity are unchanged.

American CRR milestone: the approved Python implementation is matched by a scalar C++20 kernel, standalone native test driver, and scalar `_voledge_native` binding. The binding calls the existing kernel; the Python reference, C++ kernel/CLI, and European BSM API are unchanged. Both implementations use continuous dividend yield, exercise at each node, a 1–10,000 integer step count, intrinsic expiry price, deterministic zero-volatility rollback, and reject invalid probabilities without clamping. The compiled binding parity test verified that it loaded the built extension, compared the same eight call/put cases at identical step counts (one-step fixtures, early-exercise put, no-dividend call, dividend call, expiry and zero volatility), and checked matching exception types/messages for European exercise, invalid probability, out-of-range steps, booleans, floats and numerical overflow. At atol=1e-10 and rtol=1e-10 the largest absolute price difference was 0.

Verified in WSL using Python 3.14.4, GCC 15.2, CMake 4.4.4 and pybind11 3.1.0:

- `source .venv/bin/activate && cmake -S . -B build-wsl-clean-20261111 -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$PWD/.venv/bin/python" && cmake --build build-wsl-clean-20261111 --parallel` — passed.
- `PYTHONPATH=build-wsl-clean-20261111/python:python python tests/pybind_american_crr_parity_check.py` — passed; 8 comparisons, largest absolute difference 0, error-boundary checks passed.
- `PYTHONPATH=python python -m unittest discover -s tests -v` — passed, 25 tests.
- `ctest --test-dir build-wsl-clean-20261111 --output-on-failure` — passed, all 4 checks.

American Greeks and batch pricing remain deferred. Tree errors are not required to decrease monotonically with step count.
