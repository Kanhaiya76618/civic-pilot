import os
import tempfile

# Settings are read at import time, so set the test environment first.
_TMP = tempfile.mkdtemp(prefix="civic-test-")
SANDBOX_PORT = 8199
os.environ.update(
    CIVIC_DATA_DIR=_TMP,
    SANDBOX_URL=f"http://127.0.0.1:{SANDBOX_PORT}",
    CIVIC_LLM_ENABLED="0",
    CIVIC_HEADLESS="1",
    CIVIC_STEP_TIMEOUT_MS="8000",
    SANDBOX_TEST_MODE="1",
    CIVIC_SKIP_DOTENV="1",  # tests never pick up the developer's real keys
)

import threading  # noqa: E402
import time  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import uvicorn  # noqa: E402

from executor.config import settings  # noqa: E402
from executor.db import Store  # noqa: E402
from executor.worker import Executor  # noqa: E402
from sandbox_portal.app import app as sandbox_app  # noqa: E402

SANDBOX_URL = f"http://127.0.0.1:{SANDBOX_PORT}"


@pytest.fixture(scope="session")
def sandbox():
    server = uvicorn.Server(uvicorn.Config(sandbox_app, host="127.0.0.1", port=SANDBOX_PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            httpx.get(SANDBOX_URL + "/__sms", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield SANDBOX_URL
    server.should_exit = True


def _fake_public_apis(request: httpx.Request) -> httpx.Response:
    """Offline stand-in for the live PIN/IFSC APIs. tests/test_live_portal.py uses the real ones."""
    code = request.url.path.rsplit("/", 1)[-1]
    if "postalpincode" in request.url.host:
        if code == "999999":
            return httpx.Response(200, json=[{"Status": "Error", "PostOffice": None}])
        if code == "110001":
            return httpx.Response(200, json=[{"Status": "Success", "PostOffice": [
                {"Name": "Connaught Place", "District": "Central Delhi", "State": "Delhi"},
                {"Name": "New Delhi GPO", "District": "New Delhi", "State": "Delhi"},
            ]}])
        return httpx.Response(200, json=[{"Status": "Success", "PostOffice": [{"Name": "Test PO", "District": "Gaya", "State": "Bihar"}]}])
    if code == "ABCD0000000":
        return httpx.Response(404, json="Not Found")
    return httpx.Response(200, json={"BANK": "Test Bank", "BRANCH": "Main", "CITY": "Patna", "DISTRICT": "Patna", "STATE": "Bihar", "IFSC": code})


@pytest.fixture(autouse=True)
def offline_public_apis(request):
    from executor import enrich
    if request.node.get_closest_marker("live"):
        enrich.transport = None
    else:
        enrich.transport = httpx.MockTransport(_fake_public_apis)
    enrich._cache.clear()
    yield


@pytest.fixture(autouse=True)
def reset_sandbox(sandbox):
    httpx.post(SANDBOX_URL + "/__admin/config", json={"variant": "default", "test_mode": True})
    httpx.post(SANDBOX_URL + "/__admin/reset")
    yield


@pytest_asyncio.fixture(scope="session")
async def executor(sandbox):
    settings.ensure_dirs()
    ex = Executor(Store(settings.db_path))
    await ex.start()
    yield ex
    await ex.stop()


@pytest.fixture(autouse=True)
def reset_executor_flags(request):
    yield
    if "executor" in request.fixturenames:
        ex = request.getfixturevalue("executor")
        ex.llm = None
        ex.store.set_flag("kill_switch", False)
