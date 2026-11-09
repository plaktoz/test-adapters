# Implement test-adapters in Python

We chose Python, not Node or a compiled language, because the library must drive pytest, a Python tool, and parse its report with the standard library. The cost is that a jest-only repo needs a Python interpreter to run the tool. `uv tool` and `pipx` install it without touching the project's own environment.
