"""
Test 01: LLM client.

Verifies that the Groq API is reachable and that both
`generate_text` and `generate_structured` work.

Writes results to tests/manual/_report_01_llm.txt
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.core.llm_client import llm_client
from app.schemas.roadmap import RoadmapTitles


REPORT_PATH = Path(__file__).resolve().parent / "_report_01_llm.txt"


def log(msg: str, *, to_file: bool = True) -> None:
    print(msg)
    if to_file:
        with REPORT_PATH.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")


async def main() -> bool:
    # Truncate the report file.
    REPORT_PATH.write_text("", encoding="utf-8")

    log("=" * 70)
    log("TEST 01: LLM Client")
    log("=" * 70)
    log("")

    # --- Settings ---
    log("Settings:")
    log(f"  GROQ_MODEL:                {settings.GROQ_MODEL}")
    log(f"  GROQ_MAX_TOKENS:           {settings.GROQ_MAX_TOKENS}")
    log(f"  GROQ_TIMEOUT:              {settings.GROQ_TIMEOUT}")
    log(f"  GROQ_MAX_RETRIES:          {settings.GROQ_MAX_RETRIES}")
    log(f"  GROQ_MIN_REQUEST_INTERVAL: {settings.GROQ_MIN_REQUEST_INTERVAL}")
    log("")

    ok = True

    # --- Test 1: generate_text ---
    log("[Test 1/3] generate_text — tiny prompt")
    try:
        t0 = time.perf_counter()
        result = await llm_client.generate_text(
            prompt="Reply with the single word: hello",
            max_tokens=20,
        )
        elapsed = time.perf_counter() - t0
        log(f"  OK    ({elapsed:.2f}s) response={result!r}")
    except Exception as e:
        ok = False
        log(f"  FAIL  {type(e).__name__}: {e}")
    log("")

    # --- Test 2: generate_structured ---
    log("[Test 2/3] generate_structured — RoadmapTitles schema")
    try:
        t0 = time.perf_counter()
        roadmap = await llm_client.generate_structured(
            prompt=(
                "Design a very short roadmap (1 module, 2 parts) for "
                "learning Docker. Return JSON only."
            ),
            schema=RoadmapTitles,
            instructions=(
                "You are a curriculum designer. Output ONLY valid JSON. "
                "Use English for module/part titles."
            ),
            max_tokens=2000,
        )
        elapsed = time.perf_counter() - t0
        log(f"  OK    ({elapsed:.2f}s)")
        log(f"        title:   {roadmap.title!r}")
        log(f"        modules: {len(roadmap.modules)}")
        for m in roadmap.modules:
            log(f"          - {m.title!r} ({len(m.parts)} parts)")
    except Exception as e:
        ok = False
        log(f"  FAIL  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
    log("")

    # --- Test 3: rate limiter ---
    log("[Test 3/3] rate limiter — 3 sequential calls")
    try:
        t0 = time.perf_counter()
        for i in range(3):
            await llm_client.generate_text(
                prompt=f"Say '{i}'", max_tokens=10
            )
        elapsed = time.perf_counter() - t0
        log(f"  OK    3 calls took {elapsed:.2f}s")
        log(
            f"        (expected >= "
            f"{2 * settings.GROQ_MIN_REQUEST_INTERVAL:.1f}s for throttling)"
        )
    except Exception as e:
        ok = False
        log(f"  FAIL  {type(e).__name__}: {e}")
    log("")

    log("=" * 70)
    log(f"RESULT: {'PASS' if ok else 'FAIL'}")
    log("=" * 70)

    return ok


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
