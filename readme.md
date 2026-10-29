# tinyresolver

A DNS resolver written from scratch in Python, as a learning project.
The full brief (milestones, rules, schedule) is in the "tinyresolver Project Brief" doc.

## Run the tests

    python3 -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install pytest
    pytest tests/test_m1_encode.py -v   # one milestone at a time

Do not edit anything in tests/. Live tests that use the real internet are
skipped unless TINYRESOLVER_LIVE=1 is set.
