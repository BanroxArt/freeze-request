# Contributing

Useful contributions:

- Corrections to an issuer's policy entry, with a link to the issuer's own current document.
- New issuers, from their published terms only.
- New networks, with address and hash formats from the network's own docs.

Code changes:

- `ruff check .`, `ruff format --check .`, `python scripts/check.py`, `mypy` and `pytest -q` must pass.
- Every issuer entry quotes or closely paraphrases the issuer's own document and records the date it was checked.
- No network calls from the package.
- Synthetic data only. Never commit a real customer, account, address or case.
