# Approved numerical reference cases for review

Status: owner-approved on 12 November 2026 for the listed fixtures and
tolerances only. European BSM and boundary fixtures support P0. The one-step
CRR fixtures are supplemental early-P1 checks, not part of the P0 European
BSM exit gate. All cases are separate from Python/C++/pybind parity tests.
Parity establishes implementation agreement only and is not included as
evidence of model accuracy.

Run `python tests/independent_reference_check.py` to independently generate
all values from standard-library formulas and compare them with the constants
below. It does not import VolEdge code; any discrepancy is printed and makes
the command fail without changing the approved values or tolerances.

## European BSM analytical references

Inputs use annual decimals, continuous dividend yield, one-year maturity,
and per-underlying-unit prices/Greeks. Expected values were calculated in a
separate short Python calculation using `math` for the BSM equations and
`statistics.NormalDist().cdf` for the normal CDF; this does not call or import
VolEdge code. Formulas used are the closed-form BSM price and analytic Greeks
listed in §3 of the P0 specification. Rounded values below retain 15
significant digits; test values are in `tests/test_pricing.py`.

The independent calculation can be reproduced with the following
standard-library logic (the values shown in the table are its output):

```python
from math import exp, log, pi, sqrt
from statistics import NormalDist

N = NormalDist().cdf
phi = lambda x: exp(-x * x / 2) / sqrt(2 * pi)
vol = sigma * sqrt(T)
d1 = (log(S / K) + (r - q + sigma * sigma / 2) * T) / vol
d2 = d1 - vol
discounted_spot = S * exp(-q * T)
discounted_strike = K * exp(-r * T)
gamma = exp(-q * T) * phi(d1) / (S * vol)
vega = S * exp(-q * T) * phi(d1) * sqrt(T)
# For calls: C=discounted_spot*N(d1)-discounted_strike*N(d2)
# For puts:  P=discounted_strike*N(-d2)-discounted_spot*N(-d1)
```

Delta, theta, and rho use the corresponding analytic expressions in §3 and
the approved unit/sign conventions in §2. The calculation was executed
separately from VolEdge and its six interior scenarios are captured in the
table and committed test.

| Case | S | K | T | r | q | sigma | Kind | Expected price | Delta | Gamma | Vega | Theta | Rho |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| BSM-1 | 100 | 100 | 1 | 0.05 | 0 | 0.20 | Call | 10.4505835721856 | 0.636830651175619 | 0.0187620173458469 | 37.5240346916938 | -6.4140275464382 | 53.2324815453763 |
| BSM-2 | 100 | 100 | 1 | 0.05 | 0 | 0.20 | Put | 5.57352602225697 | -0.363169348824381 | 0.0187620173458469 | 37.5240346916938 | -1.65788042393463 | -41.8904609046951 |
| BSM-3 | 100 | 100 | 1 | 0.05 | 0.02 | 0.20 | Call | 9.22700550815404 | 0.586851146134764 | 0.0189505787550087 | 37.9011575100174 | -5.08931891399833 | 49.4581091053224 |
| BSM-4 | 100 | 100 | 1 | 0.05 | 0.02 | 0.20 | Put | 6.33008062754993 | -0.393347527171991 | 0.0189505787550087 | 37.9011575100174 | -2.29356913810827 | -45.6648333447491 |
| BSM-5 | 100 | 100 | 1 | -0.01 | 0 | 0.20 | Call | 7.51305824360244 | 0.519938805838372 | 0.0199221957047382 | 39.8443914094764 | -3.53963091754529 | 44.4808223402348 |
| BSM-6 | 100 | 100 | 1 | -0.01 | 0 | 0.20 | Put | 8.51807495201923 | -0.480061194161628 | 0.0199221957047382 | 39.8443914094764 | -4.54968108462946 | -56.524194368182 |

Approved acceptance tolerance for these moderate-scale, smooth interior
fixtures: `abs_tol=1e-10`, `rel_tol=1e-10` for price and each Greek. This
threshold is substantially above the rounding error in the 15-digit table
while tight enough to detect meaningful equation, sign, and Greek-unit
errors. The table does not establish accuracy for extreme inputs,
near-boundary Greeks, or the American tree.

## Boundary references

| Case | Inputs | Expected output | Independent derivation | Proposed tolerance |
|---|---|---|---|---|
| Expiry call | S=110, K=100, T=0 | Price 10; Greeks unavailable; code `greeks_unavailable_expiry` | Direct payoff `max(S-K,0)` | Exact |
| Expiry put | S=90, K=100, T=0 | Price 10; Greeks unavailable; code `greeks_unavailable_expiry` | Direct payoff `max(K-S,0)` | Exact |
| Zero-vol call | S=100, K=100, T=1, r=q=0, sigma=0 | Price 0; Greeks unavailable; code `greeks_unavailable_zero_volatility` | Discounted deterministic payoff | `abs_tol=1e-12` |
| Zero-vol put | S=80, K=100, T=1, r=0.10, q=0, sigma=0 | Price `100*exp(-0.10)-80` = 10.48374180359596; Greeks unavailable | Discounted deterministic payoff | `abs_tol=1e-10` |

## Hand-calculated CRR spot checks

These are supplemental early-P1 checks of the American CRR convention, not
part of the P0 European BSM scope or BSM parity. One-step
inputs: S=K=100, T=1, r=0.05, q=0, sigma=0.20, steps=1. The tree has
`u=exp(0.2)=1.22140275816017`, `d=1/u=0.818730753077982`,
`p=(exp(0.05)-d)/(u-d)=0.577493196356124`, and discount
`exp(-0.05)=0.951229424500714`.

| Kind | Up payoff | Down payoff | Hand-rolled value |
|---|---:|---:|---:|
| Call | 22.140275816017 | 0 | 12.1622849646239 |
| Put | 0 | 18.1269246922018 | 7.28522741469534 |

An American option may exercise immediately at the root, including in a
one-step tree. These particular at-the-money fixtures have zero root
exercise value and positive continuation value, so immediate exercise is not
selected and their values match the one-step European tree values. They
validate the specified CRR arithmetic but do not validate early rollback.

Approved tolerance: `abs_tol=1e-12` for the listed one-step tree fixtures, allowing only
floating-point evaluation-order differences. The arithmetic is shown so the
fixture can be independently checked by hand. The committed Python
`test_american_crr_one_step_hand_reference_without_dividends` checks the same
values. An additional existing one-step fixture with q=0.02 is also tested
separately; the listed independent hand reference is the zero-dividend case.
The distinct multi-step `test_american_put_early_exercise_adds_value` checks
that a 100-step American put is worth more than its European counterpart.
Python/C++ and compiled-binding parity checks are further separate
implementation-consistency evidence, not independent numerical references.

## Not parity evidence

Existing and newly expanded Python/C++/compiled-binding comparisons remain
cross-implementation checks. They do not appear in the analytical tables
above and cannot substitute for them. The experimental American delta/gamma
diagnostic is also not a price reference; gamma instability near exercise
boundaries remains an open validation issue.
