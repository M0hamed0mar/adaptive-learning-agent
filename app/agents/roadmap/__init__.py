"""
Roadmap agents package.

Exposes the roadmap titles pipeline (Phase 11 redesign).

The old agent/critic/refiner (full roadmap with objectives) has been
replaced by the titles-only pipeline, which is much faster.
"""

from app.agents.roadmap.titles_agent import (
    RoadmapTitlesAgent,
    roadmap_titles_agent,
)
from app.agents.roadmap.titles_critic import (
    RoadmapTitlesCritic,
    roadmap_titles_critic,
)
from app.agents.roadmap.titles_refiner import (
    RoadmapTitlesRefiner,
    roadmap_titles_refiner,
)
from app.agents.roadmap.titles_workflow import (
    RoadmapTitlesResult,
    RoadmapTitlesWorkflow,
    roadmap_titles_workflow,
)

__all__ = [
    # Agent
    "RoadmapTitlesAgent",
    "roadmap_titles_agent",
    # Critic
    "RoadmapTitlesCritic",
    "roadmap_titles_critic",
    # Refiner
    "RoadmapTitlesRefiner",
    "roadmap_titles_refiner",
    # Workflow
    "RoadmapTitlesWorkflow",
    "RoadmapTitlesResult",
    "roadmap_titles_workflow",
]
