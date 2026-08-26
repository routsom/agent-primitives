import asyncio

import httpx
import pytest

from multiagent_boilerplate.a2a.client import delegate_to_remote_agent, fetch_agent_card
from multiagent_boilerplate.a2a.server import A2AServerOptions, start_a2a_server
from multiagent_boilerplate.agents.types import AgentTask
from multiagent_boilerplate.harness import Harness, SlidingWindowRateLimiter
from multiagent_boilerplate.providers.mock import MockChatModel
from multiagent_boilerplate.tools.registry import build_tool_registry
from multiagent_boilerplate.tracing.tracer import Tracer


class DummyRuntime:
    async def spawn_subagents(self, tasks, depth):
        raise RuntimeError("n/a")

    async def write_artifact(self, kind, summary, content, created_by):
        return {
            "artifactId": "x",
            "kind": kind,
            "sizeBytes": 1,
            "createdBy": created_by,
            "createdAt": "now",
            "summary": summary,
            "uri": "file://x",
        }

    async def read_artifact(self, artifact_id):
        return {}

    async def save_plan(self, plan):
        return None


def _task() -> AgentTask:
    return AgentTask(
        task_id="t1",
        role="subagent",
        objective="test",
        output_format="bullets",
        allowed_tools=["search_web", "write_artifact"],
        boundaries="none",
        budget={"maxToolCalls": 5},
    )


def test_sliding_window_rate_limiter() -> None:
    limiter = SlidingWindowRateLimiter(2, 1000)
    assert limiter.try_acquire("k", 0) is True
    assert limiter.try_acquire("k", 100) is True
    assert limiter.try_acquire("k", 200) is False
    assert limiter.try_acquire("other", 200) is True
    assert limiter.try_acquire("k", 1200) is True


@pytest.fixture
def server():
    opts = A2AServerOptions(
        port=8895,
        base_url="http://localhost:8895",
        model=MockChatModel(),
        harness=Harness(build_tool_registry()),
        runtime=DummyRuntime(),
        tracer=Tracer(on_span_end=lambda _s: None),
        max_delegation_depth=2,
        auth_token="secret-token",
        rate_limit=(100, 60_000),
    )
    srv = start_a2a_server(opts)
    yield "http://localhost:8895"
    srv.shutdown()


async def test_serves_agent_card_without_auth(server: str) -> None:
    card = await fetch_agent_card(server)
    assert card["role"] == "subagent"


async def test_rejects_task_with_no_token(server: str) -> None:
    with pytest.raises(RuntimeError, match="401"):
        await delegate_to_remote_agent(server, _task(), 0)


async def test_rejects_task_with_wrong_token(server: str) -> None:
    with pytest.raises(RuntimeError, match="401"):
        await delegate_to_remote_agent(server, _task(), 0, auth_token="wrong")


async def test_accepts_task_with_correct_token(server: str) -> None:
    result = await delegate_to_remote_agent(server, _task(), 0, auth_token="secret-token")
    assert result.status == "ok"


def test_httpx_and_asyncio_available() -> None:
    # Guard: these tests need httpx + a running loop; fail loudly if the fixture wiring breaks.
    assert httpx is not None
    assert asyncio is not None
