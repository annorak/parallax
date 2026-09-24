# Parallax

A local browser-use red-team range for testing AI agents against prompt-injection traps.

The fake company is [E Corp](https://en.wikipedia.org/wiki/Mr._Robot).

## Setup

Requires Python 3.11 or newer and `uv`.

```sh
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
browser-use install
```

Fill in the API key for the provider you plan to use in `.env`.
