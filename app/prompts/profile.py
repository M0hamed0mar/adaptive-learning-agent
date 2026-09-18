"""
Prompts for the Profile Agent (Phase 11 redesign).

The profile is now:
    - 4 answers from the user (level, goal, role, learning_style).
    - raw_input (the user's free-text description).
    - topic + language inferred by the LLM.

No more question generation, no more profile critique.
"""

from __future__ import annotations

from app.config.constants import (
    DEFAULT_LANGUAGE,
    LearningGoal,
    LearningStyle,
    UserLevel,
)


# ============================================================
# Helpers
# ============================================================

def _format_enum_values(enum_cls) -> str:
    """Return a comma-separated list of enum values."""
    return ", ".join(f"`{member.value}`" for member in enum_cls)


_LEVEL_VALUES = _format_enum_values(UserLevel)
_GOAL_VALUES = _format_enum_values(LearningGoal)
_STYLE_VALUES = _format_enum_values(LearningStyle)


# ============================================================
# System prompt
# ============================================================

PROFILE_BUILDING_SYSTEM = f"""\
أنت builder لبروفايل تعلم (learning profile) لمنصة تعليمية ذكية.

مهمتك: بناء `UserProfile` من:
    (أ) وصف المستخدم الحر (raw_input).
    (ب) 4 إجابات جاهزة من المستخدم.

------------------------------------------------------------
المطلوب منك
------------------------------------------------------------
1. استخرج `topic` من `raw_input` (اسم الموضوع المعياري).
   - مثال: "I want to learn Docker for my ML projects" → topic = "Docker"
   - مثال: "أنا عايز أذاكر Machine Learning وبالأخص NLP" → topic = "Machine Learning"
   - لو الـraw_input غامض، اختر أقرب موضوع تقني واضح.

2. املأ `level` و `goal` و `role` و `learning_style` من الإجابات
   المعطاة (استخدم القيم الحرفية للـenums).

3. احفظ `raw_input` **بالضبط كما هو** بدون أي تعديل.

4. املأ `language` باللغة المطلوبة (افتراضيًا `{DEFAULT_LANGUAGE}`).

------------------------------------------------------------
قواعد صارمة
------------------------------------------------------------
1. لا تخترع معلومات غير موجودة في raw_input أو في الإجابات.
2. الـ`topic` يجب أن يكون:
   - اسم موضوع تقني (Docker, Kubernetes, Machine Learning, ...).
   - قصيرًا وواضحًا.
3. الـ`level` يجب أن يكون أحد هذه القيم بالضبط:
   {_LEVEL_VALUES}
4. الـ`goal` يجب أن يكون أحد هذه القيم بالضبط:
   {_GOAL_VALUES}
5. الـ`learning_style` يجب أن يكون أحد هذه القيم بالضبط:
   {_STYLE_VALUES}
6. الـ`role` نص حر قصير (2-5 كلمات)، مثل "AI Engineer".
7. الـ`raw_input` يجب أن يُنسخ حرفيًا كما هو.
8. أعد JSON فقط، بدون أي نص إضافي.
"""


# ============================================================
# User prompt builder
# ============================================================

def build_profile_building_prompt(
    *,
    raw_input: str,
    answers: dict[str, str],
    topic: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    Build the user prompt for profile construction.

    Args:
        raw_input: The user's free-text description.
        answers: The 4 answers from the UI.
        topic: A pre-filled topic, or "" to let the LLM infer it.
        language: Output language code.

    Returns:
        A formatted prompt ready to send to the LLM.
    """
    formatted_answers = "\n".join(
        f"    - {field}: {value}" for field, value in answers.items()
    )

    topic_hint = (
        f'    Hint topic (already known): "{topic}"'
        if topic
        else "    Hint topic: (غير محدد — استخرجه من raw_input)"
    )

    return f"""\
ابنِ UserProfile من المعلومات التالية.

------------------------------------------------------------
وصف المستخدم الحر (raw_input):
------------------------------------------------------------
"{raw_input}"

------------------------------------------------------------
الإجابات الجاهزة:
------------------------------------------------------------
{formatted_answers}

{topic_hint}

------------------------------------------------------------
المطلوب
------------------------------------------------------------
- استخرج `topic` من raw_input.
- استخدم الإجابات حرفيًا في الحقول المقابلة.
- احفظ `raw_input` كما هو بالضبط.
- املأ `language` بـ `{language}`.
- أعد JSON فقط.
"""


__all__ = [
    "PROFILE_BUILDING_SYSTEM",
    "build_profile_building_prompt",
]
