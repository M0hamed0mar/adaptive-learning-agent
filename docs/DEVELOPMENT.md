# Development Guide

Guide for developing the Adaptive Learning Agent locally.

## Setup

### 1. Clone and prepare

```bash
git clone https://github.com/<your-username>/adaptive-learning-agent.git
cd adaptive-learning-agent

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
2. Configure environment
Copy .env.example to .env and fill in:

bash
cp .env.example .env
Set at minimum:

GROQ_API_KEY

(Optional) TAVILY_API_KEY

3. Initialize the database
bash
alembic upgrade head
4. Start the development server
bash
uvicorn app.main:app --reload
Open http://localhost:8000.

Project Structure
text
app/
├── agents/          # Domain agents (profile, roadmap, prompt, tutor)
├── api/             # FastAPI routes and dependencies
├── config/          # Settings and constants
├── core/            # LLM client, logging, exceptions
├── database/        # Async engine and session management
├── graph/           # LangGraph state, nodes, and workflow
├── models/          # SQLAlchemy ORM models
├── prompts/         # LLM prompts (as Python strings)
├── schemas/         # Pydantic schemas
├── services/        # Business logic and CRUD
├── tools/           # External tools (web search)
├── web/             # HTML routes, templates, static assets
└── main.py          # FastAPI application factory
Common Tasks
Adding a new agent
Create a folder under app/agents/<domain>/

Write agent.py, critic.py, refiner.py as needed

Add prompts under app/prompts/

Add Pydantic schemas under app/schemas/

Wire it into the LangGraph workflow

Adding a new endpoint
Add a Pydantic schema under app/schemas/session_api.py

Add a service method under app/services/

Add the route under app/api/routes/

Register the router in app/main.py

Adding a new migration
bash
alembic revision --autogenerate -m "description"
alembic upgrade head
Running tests
bash
pytest                          # all tests
pytest tests/unit/              # unit only
pytest -k "test_roadmap"        # match by name
Manual testing
The tests/manual/ folder contains scripts for end-to-end testing:

bash
python tests/manual/run_all.py
Produces tests/manual/check_report.md.

Code Style
English only in code, comments, and docstrings

Type hints everywhere (from __future__ import annotations)

Docstrings on every class and non-trivial function

Structured logging via structlog

Async everywhere in services, agents, and workflows

Pydantic v2 for schemas; use _StrictBase with extra="forbid"

Conventions
ComponentPatternExample
Modulessnake_caseprofile_service.py
ClassesPascalCaseProfileAgent
Functionssnake_casebuild_profile()
ConstantsSCREAMING_SNAKEMAX_PROFILE_QUESTIONS
Pydantic modelsPascalCaseUserProfile
SQLAlchemy modelsPascalCase (+ ORM suffix)Lesson as LessonORM
LangGraph nodes*_nodebuild_profile_node
Routes*_endpoint (or descriptive)create_session
Adding a New Language
Update DEFAULT_LANGUAGE in app/config/constants.py

Update the prompts in app/prompts/ (language section)

The Lesson content will follow the brief's language

Debugging
Enable verbose logs
Set LOG_LEVEL=DEBUG in .env.

Inspect the database
bash
sqlite3 data/adaptive_learning.db
.tables
SELECT * FROM study_sessions;
Check the LLM client
The LLMClient logs every request:

text
llm_request_started method=generate_structured schema=RoadmapTitles
llm_request_retrying attempt=2
llm_request_completed
Contributing
Create a feature branch

Make changes with tests

Run pytest and ruff check

Submit a pull request
