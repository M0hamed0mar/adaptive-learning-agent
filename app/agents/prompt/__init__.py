"""
Teaching prompt agents package.

Exposes the batch teaching-prompt pipeline (Phase 11 redesign).

The old generator/critic/refiner (one prompt per call) has been
replaced by the batch pipeline, which generates ALL prompts in ONE
LLM call and refines them in ONE more.
"""

from app.agents.prompt.set_critic import (
    TeachingPromptSetCritic,
    teaching_set_critic,
)
from app.agents.prompt.set_generator import (
    TeachingPromptSetGenerator,
    teaching_set_generator,
)
from app.agents.prompt.set_refiner import (
    TeachingPromptSetRefiner,
    teaching_set_refiner,
)
from app.agents.prompt.set_workflow import (
    TeachingPromptSetResult,
    TeachingPromptSetWorkflow,
    teaching_set_workflow,
)

__all__ = [
    # Generator
    "TeachingPromptSetGenerator",
    "teaching_set_generator",
    # Critic
    "TeachingPromptSetCritic",
    "teaching_set_critic",
    # Refiner
    "TeachingPromptSetRefiner",
    "teaching_set_refiner",
    # Workflow
    "TeachingPromptSetWorkflow",
    "TeachingPromptSetResult",
    "teaching_set_workflow",
]
