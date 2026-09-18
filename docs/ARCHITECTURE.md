# Architecture

Detailed technical documentation for the Adaptive Learning Agent.

## Overview

The system is a multi-agent pipeline orchestrated with LangGraph. Each
agent has a single responsibility, and they are composed into two
bounded refinement loops followed by a lazy lesson-generation step.

## System Layers
┌───────────────────────────────────────────────────────────────┐
│ Presentation │
│ │
│ HTML UI (Jinja2 + HTMX + Tailwind) | JSON API (FastAPI) │
└──────────────────────────────┬────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────┐
│ Orchestration │
│ │
│ LangGraph StateGraph (2 loops) │
└──────────────────────────────┬────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────┐
│ Agents │
│ │
│ Profile │ Roadmap (Generator/Critic/Refiner) │
│ │ Briefs (Generator/Critic/Refiner) │
│ │ Tutor (Lesson + Chat) │
└──────────────────────────────┬────────────────────────────────┘
│
▼
┌───────────────────────────────────────────────────────────────┐
│ Infrastructure │
│ │
│ LLMClient │ Database │ Web Search │ Logging │
└───────────────────────────────────────────────────────────────┘

text

## Agent Pipeline
START
│
▼
build_profile ← ProfileAgent.build_profile()
│
▼
generate_roadmap ← RoadmapTitlesAgent.generate()
│
▼
evaluate_roadmap ◀───────┐ ← RoadmapTitlesCritic.evaluate()
│ │
├─ acceptable? ────────┤
│ no │
▼ │
refine_roadmap │ ← RoadmapTitlesRefiner.refine()
│ │
└───────────────────────┘
│
│ yes
▼
save_roadmap ← Persist to DB
│
▼
generate_prompts ← TeachingPromptSetGenerator.generate()
│ (with progress callback)
▼
evaluate_prompts ◀───────┐ ← TeachingPromptSetCritic.evaluate()
│ │
├─ acceptable? ────────┤
│ no │
▼ │
refine_prompts │ ← TeachingPromptSetRefiner.refine()
│ │
└───────────────────────┘
│
│ yes
▼
save_prompts ← Attach briefs to roadmap parts
│
▼
END

text

## State Model

The LangGraph state (`LearningState`) is a `TypedDict` with these
fields:

```python
class LearningState(TypedDict, total=False):
    # Inputs
    session_id: int
    raw_input: str
    profile_answers: dict[str, str]

    # Derived
    profile: UserProfile
    roadmap: RoadmapTitles
    roadmap_critique: RoadmapTitlesCritique
    roadmap_iterations: int
    roadmap_acceptable: bool

    prompt_set: TeachingPromptSet
    prompt_set_critique: TeachingPromptSetCritique
    prompt_set_iterations: int
    prompt_set_acceptable: bool

    status: str
    errors: list[str]
Data Model
text
User ───┬── StudySession ───┬── LearningProfile
        │                   │
        │                   ├── Roadmap ───┬── RoadmapModule ───┬── RoadmapPart
        │                   │              │                    │
        │                   │              │                    └── Lesson
        │                   │              │
        │                   ├── Progress
        │                   │
        │                   └── Message[]
        │
        └── ...
LLM Client
All LLM calls go through app/core/llm_client.py. The client:

Throttles requests client-side (GROQ_MIN_REQUEST_INTERVAL)

Retries on transient errors with exponential backoff

Validates structured output against Pydantic schemas

Detects truncation (finish_reason == "length")

Maps provider errors to a custom exception hierarchy

Two methods:

generate_text() — for prose (lessons, prompts)

generate_structured() — for JSON (schemas)

Agent Design
Each agent:

Has one responsibility (single-purpose)

Is stateless (no internal state)

Returns Pydantic models (typed)

Is async (compatible with FastAPI)

Logs structured events (structlog)

Why These Choices
Why LangGraph?
LangGraph provides explicit state, conditional routing, and bounded
loops — a natural fit for critique-and-refine workflows. It also makes
the pipeline testable in isolation.

Why batched briefs instead of full prompts?
Full prompts are 4-5x larger than concise briefs. The brief is
expanded by the Tutor Agent at lesson time using a fixed system prompt
that encodes all style and format rules. This cuts latency and token
usage without sacrificing quality.

Why lazy lesson generation?
Lessons are expensive to generate. Most learners do not open every
part. Generating on demand keeps response times low.

Why the critic/refiner pattern?
Single-pass generation produces shallow output. Adding a critic plus
a bounded refinement loop measurably improves structural quality at a
small, bounded cost in latency.

Further Reading
docs/DEPLOYMENT.md — deployment instructions

infrastructure/aws/README.md — AWS architecture

README.md — project overview
