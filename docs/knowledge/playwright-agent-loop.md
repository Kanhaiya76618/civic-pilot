# Skill Note: Playwright Autonomous Agent Loop & CDP Screencast

## Overview & Architecture
An autonomous browser agent operates as an iterative feedback loop:
$$\text{Perceive} \longrightarrow \text{Think} \longrightarrow \text{Act} \longrightarrow \text{Evaluate}$$
Rather than raw HTML, the perception step compresses the DOM and accessibility tree into an actionable text snapshot of interactive element references (e.g., `e1: [button 'Submit']`, `e2: [input 'Mobile']`), pruning non-interactive noise to conserve model context.

---

## 1. Patterns
- **Accessibility & Interactive Pruning**: Extract nodes that have ARIA roles, click/input handlers, or focusable attributes. Map each to an ephemeral ID (`e1`, `e2`) so the LLM outputs concise targeted actions.
- **Persistent Context**: Reuse a single browser context with isolated session state (`context.storage_state()`) to preserve citizen cookies across multi-step execution.
- **Offline HAR Replay**: Use `page.route_from_har("trace.har", not_found="abort")` or `page.route()` to allow instant, zero-network, deterministic replays during judging or live demos when venue Wi-Fi fails.
- **CDP Screencast Streaming**: Attach via Chrome DevTools Protocol (`context.new_cdp_session(page)`) to trigger `Page.startScreencast`. Acknowledge each frame with `Page.screencastFrameAck` and emit JPEG buffers over WebSockets/SSE to the citizen UI for low-latency live streaming.

---

## 2. Common Pitfalls
1. **Unacknowledged Screencast Frames**: Failing to send `Page.screencastFrameAck(sessionId=...)` causes Chrome to throttle or completely halt frame emission.
2. **Context Leak on Crash**: Omitting proper cleanup (`context.close()`, `browser.close()`) in `finally:` blocks leads to orphaned headless Chromium processes exhausting RAM.
3. **Selector Flakiness**: Relying on brittle absolute CSS/XPath paths instead of semantic role, label, or accessibility name locators (`page.get_by_role`, `page.get_by_label`).
4. **Unbounded History Context**: Passing full previous DOM snapshots into the LLM context prompt leads to token blowup. Pass only the delta of the current snapshot and the immediate action evaluation.

---

## 3. Minimal Working Code Skeleton

```python
import asyncio
from playwright.async_api import async_playwright, Page, CDPSession

async def extract_interactive_snapshot(page: Page) -> str:
    """Prunes DOM to interactive element references with roles and text."""
    js_extract = """
    () => {
        const elements = Array.from(document.querySelectorAll('button, a, input, select, textarea, [role="button"]'));
        return elements
            .filter(el => el.offsetParent !== null && !el.disabled)
            .map((el, i) => {
                const tag = el.tagName.toLowerCase();
                const text = (el.innerText || el.getAttribute('aria-label') || el.placeholder || el.value || '').trim().slice(0, 50);
                const role = el.getAttribute('role') || tag;
                return `[e${i+1}] ${role}: "${text}" (id=${el.id || 'none'})`;
            }).join('\\n');
    }
    """
    return await page.evaluate(js_extract)

async def stream_cdp_screencast(page: Page, frame_callback):
    """Streams live JPEG frames over CDP screencast protocol."""
    cdp: CDPSession = await page.context.new_cdp_session(page)
    
    async def on_frame(event):
        session_id = event["sessionId"]
        frame_data = event["data"] # base64 JPEG
        await frame_callback(frame_data)
        await cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
        
    cdp.on("Page.screencastFrame", lambda ev: asyncio.create_task(on_frame(ev)))
    await cdp.send("Page.startScreencast", {
        "format": "jpeg",
        "quality": 60,
        "maxWidth": 1280,
        "maxHeight": 900,
        "everyNthFrame": 1
    })
    return cdp

async def agent_loop(page: Page, goal: str, max_steps: int = 10):
    for step in range(max_steps):
        snapshot = await extract_interactive_snapshot(page)
        # Think: LLM decides action from goal + snapshot
        # Action execution
        print(f"Step {step+1}: Snapshot extracted ({len(snapshot)} chars)")
        # Evaluate state changes
        await page.wait_for_timeout(500)
```

---

## 4. Verified Source Links
- Playwright Python API Documentation: https://playwright.dev/python/docs/api/class-playwright
- Chrome DevTools Protocol `Page.startScreencast`: https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-startScreencast
- Playwright HAR Network Recording & Routing: https://playwright.dev/python/docs/mock#replaying-designs-from-har
