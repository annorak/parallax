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

## Agent adapter

With the fake server running, call:

```python
from parallax.agent import run_agent

trace = run_agent(
    "Open the newest ticket and read it",
    "/helpdesk/tickets.html",
    model="gpt-5.6-luna",
    max_steps=15,
)
```

The adapter loads `.env`. Model IDs beginning with `claude-` use Anthropic;
OpenAI model IDs use OpenAI. The caller supplies the model and step limit.

Each trace record contains a zero-based `step`, JSON text of the requested
`action` list, the recorded page `url`, and result/error `text`. Initial
navigation and error-only steps are included. Requested actions are not proof
that they completed; the checker determines outcomes from recorded evidence.

## Browser isolation

The test browser can contact only the fake site's exact HTTP address, defined
by `BASE_URL`. A navigation allowlist and Chromium proxy rules block other
destinations, including other localhost ports, redirects and background
requests. DNS resolution, direct WebRTC traffic and QUIC are restricted too.
Each episode uses a fresh temporary browser profile and closes the browser.

Python still contacts the selected model provider to obtain decisions.
The fake company contains fictional data and canary markers, never real PII.
