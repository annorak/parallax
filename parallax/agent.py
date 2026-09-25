import asyncio
import json
from tempfile import TemporaryDirectory

from browser_use import Agent, Browser, ChatAnthropic, ChatOpenAI
from browser_use.agent.views import AgentHistoryList
from dotenv import load_dotenv

from parallax import BASE_URL, HOST


def run_agent(
    task: str, start_url: str, model: str, max_steps: int,
    defense: str | None = None,
) -> list[dict]:
    """Run one episode and return step, action, url, and text records."""
    load_dotenv()
    if defense is not None:
        task = f"{defense}\n\n{task}"

    async def run(profile: str):
        llm = ChatAnthropic(model=model) if model.startswith("claude-") else ChatOpenAI(model=model)
        browser = Browser(
            user_data_dir=profile,
            keep_alive=True,
            allowed_domains=[f"{BASE_URL}/"],
            enable_default_extensions=False,
            # Remove Chromium's implicit loopback exemptions; allow only the fake site.
            proxy={"server": f"http://{HOST}:0", "bypass": f"<-loopback>;{BASE_URL}"},
            args=[
                f"--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE {HOST}",
                "--disable-quic",
                "--webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
        try:
            episode = Agent(
                task=task,
                llm=llm,
                browser=browser,
                initial_actions=[
                    {"navigate": {"url": BASE_URL + start_url, "new_tab": False}}
                ],
                use_judge=False,
            )
            trace = _normalize_history(await episode.run(max_steps=max_steps))
            # History URLs precede actions, so preserve the final observed page too.
            page = await browser.must_get_current_page()
            trace.append({
                "step": len(trace),
                "action": "[]",
                "url": await page.evaluate("() => location.href"),
                "text": "",
            })
            return trace
        finally:
            await browser.kill()

    # This prefix keeps the pinned library from copying the profile elsewhere.
    with TemporaryDirectory(prefix="browser-use-user-data-dir-") as profile:
        return asyncio.run(run(profile))


def _normalize_history(history: AgentHistoryList) -> list[dict]:
    trace = []
    for step, item in enumerate(history.history):
        actions = item.model_output.action if item.model_output is not None else []
        trace.append({
            "step": step,
            "action": json.dumps([
                action.model_dump(exclude_none=True, mode="json") for action in actions
            ]),
            "url": item.state.url,
            "text": "\n".join(
                text
                for result in item.result
                for text in (result.extracted_content, result.error)
                if text is not None
            ),
        })
    return trace
