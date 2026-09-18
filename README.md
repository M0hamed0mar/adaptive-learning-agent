# Adaptive Learning Agent

An AI-powered adaptive learning system that generates personalized
learning roadmaps and delivers focused, on-demand lessons for technical
topics.

Given a single free-text description of a learning goal, the system
orchestrates a set of specialized LLM agents to produce a tailored
curriculum, refine it through critique-and-improvement loops, and
generate teaching briefs that are later expanded into complete,
context-aware lessons.

**Live demo:** _Deployed on AWS · available on request_

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Deployment](#deployment)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [License](#license)

---

## Overview

Traditional online courses deliver generic content to every learner.
The Adaptive Learning Agent treats each learner as a distinct case and
builds a personalized curriculum around their profile.

The pipeline is composed of specialized agents, each with a single
responsibility:

1. **Profile Agent** — builds a structured `UserProfile` from a free-text
   description and four explicit answers.
2. **Roadmap Titles Agent** — proposes a roadmap skeleton (module and
   part titles only).
3. **Roadmap Critic** — evaluates the skeleton against the profile.
4. **Roadmap Refiner** — applies the critic's feedback in one
   refinement pass.
5. **Teaching Brief Generator** — produces one concise brief per part
   in batches.
6. **Teaching Brief Critic & Refiner** — reviews and improves the
   briefs in a single pass.
7. **Tutor Agent** — expands each brief into a complete Markdown lesson
   on demand.
8. **Tutor Chat** — answers follow-up questions about a lesson, with
   optional web search via function calling.

The pipeline is orchestrated with **LangGraph** and exposed through a
**FastAPI** application that serves both a JSON API and a server-rendered
HTML interface.

---

## Key Features

- **Personalized roadmap generation** from a single free-text prompt.
- **Multi-agent critique and refinement** loops for roadmap quality.
- **Batched teaching brief generation** with real-time progress reporting.
- **Lazy lesson generation** — lessons are produced on demand, not
  pre-generated.
- **Interactive tutor chat** with per-lesson context.
- **Web search integration** through Tavily, invoked automatically by
  the LLM only when needed (function calling).
- **Server-rendered UI** with FastAPI, Jinja2, HTMX, and Tailwind CSS.
- **Full persistence** with SQLAlchemy 2.0 (async) and Alembic
  migrations.
- **Structured, typed, and validated** data flow via Pydantic v2.
- **Structured logging** with `structlog`.
- **Dockerized** and deployed on AWS (ECS Fargate + Application Load
  Balancer).

---

## Architecture
+------------------+
| Web Client |
| (Browser/API) |
+---------+--------+
|
v
+------------------+------------------+
| FastAPI |
| (JSON API + Server-rendered UI) |
+------------------+------------------+
|
v
+------------------+------------------+
| LangGraph |
| (orchestrates the agent pipeline) |
+------------------+------------------+
|
+------------------------------+------------------------------+
| | |
v v v
+---------+---------+ +---------+---------+ +---------+---------+
| Roadmap Agents | | Brief Agents | | Tutor Agents |
| - Titles Agent | | - Set Generator | | - Lesson Agent |
| - Titles Critic | | - Set Critic | | - Chat Agent |
| - Titles Refiner | | - Set Refiner | | (+ Web Search) |
+---------+---------+ +---------+---------+ +---------+---------+
| | |
+------------------------------+------------------------------+
|
v
+------------------+------------------+
| Persistence |
| SQLAlchemy 2.0 (async) + Alembic |
+------------------+------------------+
|
v
+------------------+------------------+
| SQLite / PostgreSQL |
+-------------------------------------+

text

The pipeline is a directed acyclic graph with two bounded refinement
loops:

1. **Roadmap refinement loop** — after generation, a critic evaluates
   the roadmap titles; if unacceptable, one refinement pass is applied
   and the result is re-evaluated.
2. **Brief refinement loop** — the same pattern is applied to the
   batch of teaching briefs.

Once both loops complete, briefs are attached to the roadmap parts and
the session transitions to the `ready` state. Lessons are generated
lazily when the user opens a part.

See `docs/ARCHITECTURE.md` for a detailed description.

---

## Technology Stack

| Layer              | Technology                                       |
|--------------------|--------------------------------------------------|
| Language           | Python 3.14 (dev) / 3.12 (Docker)                |
| LLM Provider       | Groq (OpenAI-compatible API)                     |
| LLM Model          | `qwen/qwen3.8-27b`                               |
| Orchestration      | LangGraph                                        |
| Data Validation    | Pydantic v2, pydantic-settings                   |
| Backend API        | FastAPI, Uvicorn                                 |
| Server-rendered UI | Jinja2, HTMX, Tailwind CSS (CDN)                 |
| ORM                | SQLAlchemy 2.0 (async)                           |
| Database (dev)     | SQLite + aiosqlite (WAL mode)                    |
| Database (prod)    | SQLite (single-instance) / PostgreSQL            |
| Migrations         | Alembic                                          |
| Retry Logic        | Tenacity                                         |
| Logging            | structlog                                        |
| HTTP Client        | httpx                                            |
| Web Search         | Tavily                                           |
| Testing            | pytest, pytest-asyncio, httpx                    |
| Deployment         | Docker, AWS ECR, AWS ECS Fargate, ALB            |

---

## Project Structure
adaptive-learning-agent/
├── app/
│ ├── agents/ # Domain agents (profile, roadmap, prompt, tutor)
│ ├── api/ # FastAPI routes and dependencies
│ ├── config/ # Settings and constants
│ ├── core/ # LLM client, logging, exceptions
│ ├── database/ # Async engine and session management
│ ├── graph/ # LangGraph state, nodes, and workflow
│ ├── models/ # SQLAlchemy ORM models
│ ├── prompts/ # LLM prompts (as Python strings)
│ ├── schemas/ # Pydantic schemas
│ ├── services/ # Business logic and CRUD
│ ├── tools/ # External tools (web search)
│ ├── web/ # HTML routes, templates, static assets
│ └── main.py # FastAPI application factory
├── data/ # SQLite database (dev)
├── docs/ # Architecture, deployment, development docs
├── infrastructure/aws/ # AWS deployment documentation
├── migrations/ # Alembic migrations
├── scripts/ # Operational scripts
├── secrets/ # Local secrets (git-ignored)
├── tests/ # Unit, integration, and manual tests
├── .dockerignore # Docker build exclusions
├── .env.example # Environment template
├── .gitignore # Git exclusions
├── alembic.ini # Alembic configuration
├── docker-compose.yml # Local Docker stack
├── Dockerfile # Container image definition
├── pytest.ini # Test configuration
├── README.md # This file
└── requirements.txt # Python dependencies

text

---

## Getting Started

### Prerequisites

- Python 3.12 or newer
- A Groq API key (free tier available at https://console.groq.com)
- A Tavily API key (optional, for web search — https://tavily.com)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/adaptive-learning-agent.git
cd adaptive-learning-agent

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the environment template and fill in your keys
cp .env.example .env

# Apply database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload
Open http://localhost:8000 in your browser.

Quick Test
bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","version":"0.1.0",...}
Configuration
All configuration is read from environment variables (or a .env
file). The most important options:

VariableDescriptionDefault
GROQ_API_KEYGroq API key (required)—
GROQ_MODELGroq model identifierqwen/qwen3.8-27b
GROQ_MIN_REQUEST_INTERVALSeconds between consecutive Groq requests2.5
DATABASE_URLSQLAlchemy async-compatible database URLsqlite+aiosqlite:///./data/adaptive_learning.db
TAVILY_API_KEYTavily API key (optional)—
APP_ENVdevelopment, staging, or productiondevelopment
LOG_LEVELPython log levelINFO
See .env.example for the complete list.

API Reference
The JSON API is mounted under /api/v1. Interactive documentation is
available at /docs (Swagger UI) and /redoc.

Sessions
MethodPathDescription
POST/api/v1/sessionsCreate a new session
GET/api/v1/sessionsList sessions
GET/api/v1/sessions/{id}Get a session
DELETE/api/v1/sessions/{id}Delete a session
POST/api/v1/sessions/{id}/profileSubmit profile answers
GET/api/v1/sessions/{id}/profileGet the current profile
Content
MethodPathDescription
GET/api/v1/sessions/{id}/roadmapGet the roadmap
GET/api/v1/sessions/{id}/lessonsList lessons
GET/api/v1/sessions/{id}/lessons/{part_id}Get a single lesson
POST/api/v1/sessions/{id}/lessons/{part_id}/generateGenerate a lesson on demand
Progress
MethodPathDescription
GET/api/v1/sessions/{id}/progressGet progress
POST/api/v1/sessions/{id}/progress/completeMark a part as completed
POST/api/v1/sessions/{id}/progress/advanceAdvance to the next part
Chat
MethodPathDescription
POST/api/v1/sessions/{id}/lessons/{part_id}/chatAsk a question about a lesson
GET/api/v1/sessions/{id}/lessons/{part_id}/messagesList chat messages
How It Works
1. Session Creation
The user submits a free-text description of a learning goal (e.g.
"I am a beginner AI Engineer. I want to learn Docker for my ML
projects."). The description is stored verbatim.

2. Profile Construction
The Profile Agent builds a structured UserProfile from the
description and four explicit answers (level, goal, role, learning
style). The topic and language are inferred by the LLM.

3. Roadmap Generation
The Roadmap Titles Agent proposes a skeleton of module and part titles.
The Roadmap Critic evaluates the skeleton against the profile. If the
score is below the approval threshold, the Roadmap Refiner applies a
single refinement pass.

4. Brief Generation
For each part in the roadmap, the Teaching Brief Generator produces a
concise brief (200–400 characters) in batches, with progress reported
to the client. The briefs are then reviewed and improved by the brief
critic and refiner.

5. Lesson Delivery
Lessons are generated lazily, on demand, when the user opens a part.
The Tutor Agent expands the part's brief into a full Markdown lesson,
tailored to the user's profile.

6. Interactive Chat
Each lesson includes an "Ask any question" panel. The Tutor Chat agent
answers follow-up questions using the lesson content and the user's
profile as context. When web search is enabled and the LLM deems it
necessary, it invokes the Tavily search tool through OpenAI-compatible
function calling.

Deployment
The application is deployed on AWS using ECS Fargate behind an
Application Load Balancer. The container image is stored in
Amazon ECR.

Docker
bash
# Build locally
docker build -t adaptive-learning-agent:latest .

# Run locally
docker run --rm -p 8000:8000 --env-file .env adaptive-learning-agent:latest
Docker Compose
bash
docker compose up --build
AWS
See infrastructure/aws/README.md and docs/DEPLOYMENT.md for
detailed instructions.

Quick summary:

Build the Docker image

Push to Amazon ECR

Create an ECS Express Mode service in us-east-1

Configure environment variables (including API keys)

Access the application at the auto-generated HTTPS URL

Costs: ~$20/month when running continuously. Approximately $6/month
when the ECS service is stopped (ALB remains). Can be restarted in 1–2
minutes from the AWS Console.

Testing
The test suite is split into three categories:

tests/unit/ — isolated tests for services, schemas, and API routes.

tests/integration/ — cross-module tests.

tests/manual/ — end-to-end scripts that exercise the full pipeline.

Run all tests:

bash
pytest
Run only unit tests:

bash
pytest tests/unit/
Run the manual end-to-end suite:

bash
python tests/manual/run_all.py
This produces tests/manual/check_report.md with a summary of all
manual checks.

Design Decisions
Why multi-agent with critique loops?
Single-pass LLM generation produces plausible but shallow output.
Adding a critic and a bounded refinement loop measurably improves the
structural quality of both the roadmap and the teaching briefs, at a
small, bounded cost in latency.

Why lazy lesson generation?
Pre-generating every lesson is expensive and unnecessary. Most learners
will not open every part. Generating lessons on demand keeps response
times low and resource usage minimal, while preserving the same output
quality.

Why short briefs instead of full prompts?
Full teaching prompts (per part) are four to five times larger than
concise briefs. The brief is expanded by the Tutor Agent at lesson time
using a fixed system prompt that encodes all style and format rules.
This design reduces both latency and token usage without sacrificing
lesson quality.

Why LangGraph?
LangGraph provides explicit state, conditional routing, and bounded
loops, which map directly to the critique-refinement patterns used
throughout the pipeline. It also makes the workflow testable in
isolation.

Why SQLite in development and PostgreSQL in production?
SQLite in WAL mode is sufficient for development and single-instance
deployments, and requires no external service. Swapping to PostgreSQL
for production is a one-line change in DATABASE_URL.

Why ECS Fargate instead of App Runner?
AWS App Runner stopped accepting new customers on April 30, 2026.
AWS recommends ECS Express Mode as the replacement. ECS Fargate
provides the same containerized deployment model with more flexibility
and no vendor lock-in.

License
This project is licensed under the MIT License. See LICENSE for
details.
