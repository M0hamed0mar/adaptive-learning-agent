"""
Full end-to-end integration test for the FastAPI layer.

This script exercises the entire HTTP API by running a real uvicorn
server in a background task, then making real HTTP requests to it.

Why a real server instead of httpx.ASGITransport?
    - Background tasks launched via `asyncio.create_task` (used by
      POST /sessions/{id}/profile to run the learning pipeline) need
      a running event loop with a live server. ASGITransport is
      synchronous with respect to the test's request/response cycle
      and does not reliably let background tasks progress between
      requests.

By running a real uvicorn server on a random port, we:
    - Get correct background task execution.
    - Exercise the real ASGI stack.
    - Avoid needing a separate terminal.

The test:
    1. Starts uvicorn in the background.
    2. Creates a new session via POST /sessions.
    3. Triggers the learning pipeline via POST /sessions/{id}/profile.
    4. Polls GET /sessions/{id} until status is 'ready' (or 'failed').
    5. Verifies lessons via GET /sessions/{id}/lessons.
    6. Verifies a single lesson via GET /sessions/{id}/lessons/{part_id}.
    7. Verifies progress via GET /sessions/{id}/progress.
    8. Marks a part completed via POST .../progress/complete.
    9. Advances progress via POST .../progress/advance.
   10. Cleans up via DELETE /sessions/{id}.
   11. Shuts down uvicorn.

Run:
    python scripts/demo_api.py
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from app.main import app  # noqa: E402


# ============================================================
# Configuration
# ============================================================

SESSION_POLL_INTERVAL_S = 5
SESSION_POLL_TIMEOUT_S = 600  # 10 minutes


# ============================================================
# Helpers — server lifecycle
# ============================================================

def _pick_free_port() -> int:
    """Return an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.asynccontextmanager
async def running_server(port: int):
    """
    Async context manager that runs a uvicorn server on `port`.

    Yields once the server is ready to accept requests, and shuts it
    down cleanly on exit.
    """
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Run the server in a background task.
    task = asyncio.create_task(server.serve())

    # Wait until the server reports "started".
    try:
        while not server.started:
            await asyncio.sleep(0.05)
            if task.done():
                # Server failed to start.
                task.result()
                raise RuntimeError("uvicorn failed to start")

        yield

    finally:
        server.should_exit = True
        await task


# ============================================================
# Helpers — output
# ============================================================

def _print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _check(condition: bool, message: str) -> None:
    if not condition:
        print(f"   ❌ {message}")
        raise AssertionError(message)
    print(f"   ✅ {message}")


# ============================================================
# Main test
# ============================================================

async def main() -> None:
    port = _pick_free_port()
    base_url = f"http://127.0.0.1:{port}"

    async with running_server(port):
        # Give the app's lifespan a moment to finish.
        await asyncio.sleep(0.5)

        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=60.0,
        ) as client:
            # --------------------------------------------------------
            # 1. Health check
            # --------------------------------------------------------
            _print_section("STEP 1 — GET /api/v1/health")
            r = await client.get("/api/v1/health")
            _check(r.status_code == 200, f"Status 200 (got {r.status_code})")
            health = r.json()
            _check(health["status"] == "ok", f"status='ok' (got {health['status']!r})")

            # --------------------------------------------------------
            # 2. Create session
            # --------------------------------------------------------
            _print_section("STEP 2 — POST /api/v1/sessions")
            r = await client.post(
                "/api/v1/sessions",
                json={
                    "topic": "Docker",
                    "raw_input": "Docker for AI Engineers",
                },
            )
            _check(r.status_code == 201, f"Status 201 (got {r.status_code})")
            created = r.json()
            session_id = created["id"]
            _check(created["status"] == "draft", f"status='draft'")
            print(f"   → session_id = {session_id}")

            # --------------------------------------------------------
            # 3. List sessions
            # --------------------------------------------------------
            _print_section("STEP 3 — GET /api/v1/sessions")
            r = await client.get("/api/v1/sessions")
            _check(r.status_code == 200, f"Status 200")
            sessions = r.json()
            _check(any(s["id"] == session_id for s in sessions), "new session in list")

            # --------------------------------------------------------
            # 4. Get session (before)
            # --------------------------------------------------------
            _print_section("STEP 4 — GET /api/v1/sessions/{id} (before)")
            r = await client.get(f"/api/v1/sessions/{session_id}")
            _check(r.status_code == 200, f"Status 200")
            detail = r.json()
            _check(detail["has_profile"] is False, "has_profile=False")

            # --------------------------------------------------------
            # 5. Submit profile
            # --------------------------------------------------------
            _print_section("STEP 5 — POST /api/v1/sessions/{id}/profile")
            r = await client.post(
                f"/api/v1/sessions/{session_id}/profile",
                json={
                    "level": "beginner",
                    "goal": "build_projects",
                    "role": "AI Engineer",
                    "learning_style": "practical",
                    "focus": "Dockerizing FastAPI applications",
                },
            )
            _check(r.status_code == 202, f"Status 202")
            accepted = r.json()
            _check(accepted["status"] == "planning", "status='planning'")

            # --------------------------------------------------------
            # 6. Poll until ready/failed
            # --------------------------------------------------------
            _print_section("STEP 6 — Polling session status")
            print(f"   ⏳ every {SESSION_POLL_INTERVAL_S}s (timeout {SESSION_POLL_TIMEOUT_S}s)")

            started_at = time.perf_counter()
            final_status = None

            while True:
                elapsed = time.perf_counter() - started_at
                if elapsed > SESSION_POLL_TIMEOUT_S:
                    raise AssertionError(f"Pipeline timeout after {SESSION_POLL_TIMEOUT_S}s")

                r = await client.get(f"/api/v1/sessions/{session_id}")
                detail = r.json()
                status = detail["status"]
                print(
                    f"   [{elapsed:6.1f}s] status={status!r} "
                    f"has_profile={detail['has_profile']} "
                    f"has_roadmap={detail['has_roadmap']}"
                )

                if status == "ready":
                    final_status = "ready"
                    break
                if status == "failed":
                    final_status = "failed"
                    break

                await asyncio.sleep(SESSION_POLL_INTERVAL_S)

            _check(
                final_status == "ready",
                f"pipeline completed with status='ready' (got {final_status!r})",
            )

            # --------------------------------------------------------
            # 7. Session detail (after)
            # --------------------------------------------------------
            _print_section("STEP 7 — GET /api/v1/sessions/{id} (after)")
            r = await client.get(f"/api/v1/sessions/{session_id}")
            detail = r.json()
            _check(detail["has_profile"] is True, "has_profile=True")
            _check(detail["has_roadmap"] is True, "has_roadmap=True")
            total_parts = detail["total_parts"]
            _check(total_parts is not None, f"total_parts={total_parts}")

            # --------------------------------------------------------
            # 8. Lessons
            # --------------------------------------------------------
            _print_section("STEP 8 — GET /api/v1/sessions/{id}/lessons")
            r = await client.get(f"/api/v1/sessions/{session_id}/lessons")
            _check(r.status_code == 200, f"Status 200")
            lessons_response = r.json()
            _check(
                lessons_response["total"] == total_parts,
                f"lessons count == total_parts ({lessons_response['total']} == {total_parts})",
            )
            first_part_id = lessons_response["lessons"][0]["part_id"]

            # --------------------------------------------------------
            # 9. Single lesson
            # --------------------------------------------------------
            _print_section(f"STEP 9 — GET lesson {first_part_id}")
            r = await client.get(f"/api/v1/sessions/{session_id}/lessons/{first_part_id}")
            _check(r.status_code == 200, f"Status 200")

            # --------------------------------------------------------
            # 10. Progress
            # --------------------------------------------------------
            _print_section("STEP 10 — GET /api/v1/sessions/{id}/progress")
            r = await client.get(f"/api/v1/sessions/{session_id}/progress")
            _check(r.status_code == 200, f"Status 200")
            progress = r.json()
            _check(progress["percentage"] == 0.0, "percentage=0.0")

            # --------------------------------------------------------
            # 11. Mark part completed            # --------------------------------------------------------
            _print_section("STEP 11 — POST progress/complete")
            r = await client.post(
                f"/api/v1/sessions/{session_id}/progress/complete",
                json={"part_id": first_part_id},
            )
            _check(r.status_code == 200, f"Status 200")
            progress = r.json()
            _check(first_part_id in progress["completed_parts"], "part in completed")

            # --------------------------------------------------------
            # 12. Idempotency
            # --------------------------------------------------------
            _print_section("STEP 12 — Re-mark (idempotency)")
            r = await client.post(
                f"/api/v1/sessions/{session_id}/progress/complete",
                json={"part_id": first_part_id},
            )
            progress2 = r.json()
            _check(
                progress2["percentage"] == progress["percentage"],
                "percentage unchanged",
            )

            # --------------------------------------------------------
            # 13. Advance
            # --------------------------------------------------------
            _print_section("STEP 13 — POST progress/advance")
            r = await client.post(f"/api/v1/sessions/{session_id}/progress/advance")
            _check(r.status_code == 200, f"Status 200")

            # --------------------------------------------------------
            # 14. Delete
            # --------------------------------------------------------
            _print_section("STEP 14 — DELETE /api/v1/sessions/{id}")
            r = await client.delete(f"/api/v1/sessions/{session_id}")
            _check(r.status_code == 204, f"Status 204")

            r = await client.get(f"/api/v1/sessions/{session_id}")
            _check(r.status_code == 404, f"GET after delete → 404")

    # ----------------------------------------------------------
    # Done
    # ----------------------------------------------------------
    _print_section("🎉 API INTEGRATION TEST PASSED")
    print("   All 14 steps completed successfully.\n")


if __name__ == "__main__":
    asyncio.run(main())