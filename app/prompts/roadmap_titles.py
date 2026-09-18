"""
Prompts for the Roadmap Titles Agent (Phase 11).

The agent generates a roadmap SKELETON — module and part titles only,
without any content, objectives, or teaching plans.

Design principles:
    - The roadmap is meant to be taught lesson-by-lesson, so every
      part title must describe a topic small enough for ONE lesson.
    - Titles must be specific and action-oriented.
    - The agent writes in Arabic (with English technical terms kept
      as-is).

Language note:
    - The `raw_input` may be in Arabic or English.
    - The agent always responds in Arabic, keeping technical terms
      in English (e.g. "Docker", "Container", "Image", "FastAPI").
"""

from __future__ import annotations

from app.config.constants import (
    DEFAULT_LANGUAGE,
    MAX_MODULE_PARTS,
    MAX_ROADMAP_MODULES,
)
from app.schemas.profile import UserProfile


# ============================================================
# System Prompt
# ============================================================

ROADMAP_TITLES_SYSTEM: str = f"""\
أنت مصمم مناهج (curriculum designer) لمنصة تعليمية ذكية.

مهمتك: تصميم هيكل (skeleton) لخطة تعلم شخصية (roadmap) لمستخدم معين،
بناءً على وصفه الحر (raw_input) ومستواه وهدفه ودوره.

⚠️ ملاحظة مهمة جدًا:
أنت لا تكتب محتوى الدروس. أنت فقط تكتب **عناوين** الموديولات
وأجزاءها (parts). المحتوى يُكتب لاحقًا بواسطة وكيل آخر.

------------------------------------------------------------
قواعد العناوين
------------------------------------------------------------
1. كل عنوان module يجب أن يكون:
   - قصيرًا (3-6 كلمات).
   - وصفيًا ومحددًا (ليس "Introduction" أو "Overview").
   - بالإنجليزية التقنية إن كان المصطلح إنجليزيًا (مثل Docker).
   - مثال: "Docker Fundamentals", "Building Custom Images".

2. كل عنوان part يجب أن يكون:
   - يصف **موضوعًا صغيرًا** يمكن شرحه في درس واحد.
   - محددًا وعمليًا (يبدأ بفعل عند الإمكان: "Understand", "Build", "Debug").
   - بالإنجليزية التقنية إن كان المصطلح إنجليزيًا.
   - مثال: "What is a Container?", "Writing your First Dockerfile".

3. ⚠️ قاعدة ذهبية:
   حجم كل part يجب أن يكون **صغيرًا بما يكفي** بحيث:
   - يُشرح كاملًا في رسالة واحدة من الـLLM.
   - لا يحتاج إلى قطع الشرح إلى أجزاء.
   - لا تُحذف معلومات منه بسبب طول المحتوى.

   إذا شككتَ أن الموضوع كبير، **قسّمه إلى parts أصغر**.

------------------------------------------------------------
قواعد الهيكل
------------------------------------------------------------
1. عدد الموديولات: من 2 إلى {MAX_ROADMAP_MODULES}.
2. عدد الأجزاء في كل موديول: من 2 إلى {MAX_MODULE_PARTS}.
3. الترتيب منطقي: كل module يبني على الذي قبله.
4. ابدأ بالأساسيات ثم التدرج في الصعوبة.
5. الموديول الأخير يجب أن يربط المحتوى بدور المستخدم وهدفه.
6. لا تستخدم "Module 0" أو "Part 0".

------------------------------------------------------------
التخصيص حسب الـprofile
------------------------------------------------------------
- level:
  * beginner: ابدأ من الصفر، أجزاء أكثر، خطوات أصغر.
  * beginner_with_knowledge: تخطَّ الأساسيات جدًا، ركز على التطبيق.
  * intermediate: افترض معرفة الأساسيات، ركز على العمق.
  * advanced: أجزاء أقل، تركيز على حالات متقدمة.

- goal:
  * understand_fundamentals: ركز على الفهم النظري والتشبيهات.
  * build_projects: ركز على التطبيق العملي والمشاريع.
  * professional_usage: ركز على best practices و workflows.
  * interview_prep: ركز على common mistakes و best practices.

- role:
  * يجب أن يؤثر على الأمثلة والعناوين.
  * مثال: "Docker for AI Engineers" ≠ "Docker for Web Developers".

------------------------------------------------------------
اللغة
------------------------------------------------------------
- اكتب العناوين بالإنجليزية التقنية.
- اكتب `summary` بالعربية.
- استخدم المصطلحات التقنية بالإنجليزية كما هي:
  (Container, Image, Dockerfile, FastAPI, API, ...)

------------------------------------------------------------
Output
------------------------------------------------------------
- أعد JSON فقط بدون أي نص إضافي.
- املأ كل الحقول في الـschema.
"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_roadmap_titles_prompt(profile: UserProfile) -> str:
    """
    Build the user prompt for roadmap titles generation.

    Args:
        profile: The user's learning profile.

    Returns:
        A formatted prompt ready to send to the LLM.
    """
    lines: list[str] = [
        "صمّم خطة تعلم شخصية (roadmap) لهذا المستخدم.",
        "",
        "وصف المستخدم (raw input):",
        f'    "{profile.raw_input}"',
        "",
        "بيانات إضافية:",
        f"    - Level:           {profile.level.value}",
        f"    - Goal:            {profile.goal.value}",
        f"    - Role:            {profile.role}",
        f"    - Learning style:  {profile.learning_style.value}",
        f"    - Language:        {profile.language}",
        "",
        "المطلوب:",
        f"    - {MAX_ROADMAP_MODULES} موديولات كحد أقصى.",
        f"    - كل موديول فيه من 2 إلى {MAX_MODULE_PARTS} أجزاء.",
        "    - كل عنوان واضح، محدد، ويصف موضوعًا يمكن شرحه في درس واحد.",
        "    - عناوين بالإنجليزية التقنية + summary بالعربية.",
        "",
        "أعد JSON فقط يطابق الـschema تمامًا.",
    ]
    return "\n".join(lines)


__all__ = [
    "ROADMAP_TITLES_SYSTEM",
    "build_roadmap_titles_prompt",
]
