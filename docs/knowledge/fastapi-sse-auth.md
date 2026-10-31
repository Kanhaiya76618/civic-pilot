# Skill Note: FastAPI SSE, Non-Blocking Inference & JWT Role Auth

## Overview & Architecture
FastAPI provides high-performance async web APIs, but executing CPU-heavy ML inference (YOLO image forward-pass, Whisper audio transcription, OpenCV morphology) inside an `async def` route will block the single-threaded asyncio event loop.
To maintain high responsiveness:
1. CPU/ML inference is defined in synchronous `def` routes (handled by FastAPI's anyio worker threadpool) or explicitly dispatched via `starlette.concurrency.run_in_threadpool`.
2. Live task progress and execution events are streamed to the frontend via Server-Sent Events (SSE) using `sse-starlette.EventSourceResponse`.
3. Authentication uses signed JWTs stored in `httpOnly`, `SameSite=Lax` cookies, with role verification (`citizen` vs `admin`).

---

## 1. Patterns
- **Sync `def` vs Async `async def` Rule**: If a route performs synchronous computation or blocking I/O (e.g., PyTorch inference, file processing), declare it as `def endpoint(...)`. FastAPI will automatically run it on a separate worker thread. Never put long synchronous code in `async def`.
- **SSE Streaming with Clean Disconnect**: Use `sse-starlette.EventSourceResponse`. Wrap the generator in a `try...finally` block to detect client disconnects and clean up queues/subscriptions.
- **httpOnly Cookie JWT**: Set JWTs in cookies with `httponly=True`, `samesite="lax"`, `secure=False` (in localhost dev). Protect against XSS token theft compared to `localStorage`.
- **Role Dependency Guards**: Define reusable dependency functions (`require_admin`, `get_current_user`) using `fastapi.Depends`.

---

## 2. Common Pitfalls
1. **Blocking the Async Loop**: Calling `model.predict(img)` inside `async def` blocks all incoming HTTP and WebSocket requests until inference completes.
2. **Missing Client Disconnect Handling in SSE**: If an SSE generator loops indefinitely without checking `await request.is_disconnected()`, it leaks background generator tasks on browser tab close.
3. **CORS with Credentials**: When using cookies across origins (e.g. Vite dev on 5173, FastAPI on 8000), `CORSMiddleware` requires `allow_credentials=True` and specific origin URLs (`allow_origins=["http://localhost:5173"]`), not wildcard `"*"`.

---

## 3. Minimal Working Code Skeleton

```python
import asyncio
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
import jwt
from sse_starlette.sse import EventSourceResponse

SECRET_KEY = "dev-insecure-secret"
ALGORITHM = "HS256"

app = FastAPI()

def run_sync_cpu_inference(image_bytes: bytes) -> dict:
    """Simulates CPU-heavy YOLO/CV triage in worker thread."""
    import time
    time.sleep(0.5) # blocking computation
    return {"severity": 85, "category": "Pothole"}

# --- Auth ---
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=8)) -> str:
    payload = data.copy()
    payload.update({"exp": datetime.now(timezone.utc) + expires_delta})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(required_role: str):
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") != required_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return role_checker

# --- Routes ---
@app.post("/api/auth/login")
def login(role: str, response: Response):
    token = create_access_token({"sub": "user_123", "role": role})
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax")
    return {"status": "ok", "role": role}

@app.post("/api/triage")
async def triage_endpoint(request: Request):
    """Offloads sync CV inference to worker thread so event loop remains free."""
    body = await request.body()
    result = await run_in_threadpool(run_sync_cpu_inference, body)
    return result

@app.get("/api/events")
async def sse_events(request: Request):
    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            for i in range(10):
                if await request.is_disconnected():
                    break
                yield {"event": "step", "data": f'{{"step": {i}, "status": "active"}}'}
                await asyncio.sleep(1)
        finally:
            print("Client disconnected from SSE stream")

    return EventSourceResponse(event_generator())
```

---

## 4. Verified Source Links
- FastAPI Concurrency & Worker Threads: https://fastapi.tiangolo.com/async/#path-operation-functions
- SSE Starlette (Server-Sent Events for Starlette/FastAPI): https://github.com/sysid/sse-starlette
- PyJWT Documentation: https://pyjwt.readthedocs.io/
