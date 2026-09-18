"""
Prompts for the Roadmap Titles Critic (Phase 11).

The critic evaluates a roadmap skeleton (titles only) and decides
whether it's good enough to proceed to prompt generation.
"""

from __future__ import annotations

from app.config.constants import (
    MAX_MODULE_PARTS,
    MAX_ROADMAP_MODULES,
    ROADMAP_APPROVAL_THRESHOLD,
)
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles


# ============================================================
# System Prompt
# ============================================================

ROADMAP_TITLES_EVALUATION_SYSTEM: str = f"""\
أنت ناقد جودة مناهج (curriculum quality critic) لمنصة تعليمية ذكية.

مهمتك: تقييم **هيكل** خطة تعلم (roadmap skeleton) — فقط العناوين —
قبل تمريره لمرحلة إنشاء الـprompts.

⚠️ أنت لا تعيد كتابة الـroadmap. أنت فقط:
    - تصف المشاكل بدقة.
    - تقترح تحسينات قابلة للتنفيذ.

------------------------------------------------------------
معايير التقييم
------------------------------------------------------------
قيّم الـroadmap من هذه الأبعاد:

1. التغطية (Coverage)
   - هل يغطي الموضوع end-to-end؟
   - هل هناك فجوات واضحة بالنظر لـrole و goal؟

2. الملاءمة للـprofile (Tailoring)
   - هل التسلسل مناسب لـlevel المستخدم؟
   - هل العناوين تعكس role و goal؟
   - هل تركيب الموديولات يناسب learning_style؟

3. الترتيب المنطقي (Logical Ordering)
   - هل كل module يبني على ما قبله؟
   - هل المتطلبات تأتي قبل المعتمدات؟
   - هل الصعوبة تزداد بشكل منطقي؟

4. جودة العناوين (Title Quality)
   - هل كل عنوان محدد (ليس عامًا)؟
   - هل يعكس فعلًا المحتوى المذكور في `summary`؟
   - هل يبدأ بفعل عند الإمكان؟
   - ⚠️ الأهم: هل كل part صغير بما يكفي ليُشرح في درس واحد؟
   - هل هناك عناوين مبهمة أو متكررة؟

5. التوازن (Balance)
   - هل التوزيع بين الموديولات متوازن؟
   - هل موديول معين أكبر بكثير من غيره بدون سبب؟

6. عدم التكرار (No Redundancy)
   - هل هناك عناوين متطابقة أو متقاربة؟

------------------------------------------------------------
Scoring Rubric (0-10)
------------------------------------------------------------
9.0 - 10.0  ممتاز: شامل، مُخصص، لا مشاكل.
8.0 -  8.9  جيد: تحسينات طفيفة ممكنة لكنه مقبول.
6.5 -  7.9  متوسط: ضعف ملحوظ؛ التحسين مُوصى به.
4.5 -  6.4  ضعيف: مشاكل متعددة؛ التحسين مطلوب.
0.0 -  4.4  غير قابل للاستخدام: غير منظم أو غير ملائم.

⚠️ اضبط `is_acceptable` = true فقط لو `score` >= {ROADMAP_APPROVAL_THRESHOLD}.

------------------------------------------------------------
قواعد
------------------------------------------------------------
1. اعتمد فقط على الـroadmap والـprofile المعطاة.
2. لا تخترع متطلبات غير مذكورة.
3. المشاكل يجب أن تكون محددة: اذكر اسم الـmodule أو الـpart.
4. الاقتراحات يجب أن تكون قابلة للتنفيذ.
5. كن صارمًا: roadmap عام وغير مُخصص لا يجب أن يتعدى 7.0.
6. اكتب `reasoning` قصيرًا وواقعيًا.
7. لا تنقد بنية الـJSON — افترض أنها صحيحة.
"""


# ============================================================
# User Prompt Builder
# ============================================================

def _render_profile_section(profile: UserProfile) -> list[str]:
    return [
        "USER PROFILE",
        f"    - Topic:           {profile.topic}",
        f"    - Level:           {profile.level.value}",
        f"    - Goal:            {profile.goal.value}",
        f"    - Role:            {profile.role}",
        f"    - Learning style:  {profile.learning_style.value}",
        f"    - Language:        {profile.language}",
        f'    - Raw input:       "{profile.raw_input[:300]}"',
    ]


def _render_roadmap_section(roadmap: RoadmapTitles) -> list[str]:
    lines: list[str] = [
        "ROADMAP SKELETON TO EVALUATE",
        f"    Title:             {roadmap.title}",
        f"    Summary:           {roadmap.summary}",
        f"    Total modules:     {roadmap.total_modules}",
        f"    Estimated hours:   {roadmap.estimated_hours}",
        "",
        f"    Modules ({len(roadmap.modules)}):",
    ]
    for i, module in enumerate(roadmap.modules, start=1):
        lines.append("")
        lines.append(f"        [M{i}] {module.title}")
        lines.append(f"            Parts ({len(module.parts)}):")
        for j, part in enumerate(module.parts, start=1):
            lines.append(f"                [{i}-{j}] {part.title}")
    return lines


def build_roadmap_titles_evaluation_prompt(
    profile: UserProfile,
    roadmap: RoadmapTitles,
) -> str:
    """
    Build the user prompt for roadmap titles evaluation.
    """
    lines: list[str] = []
    lines.append("قيّم هيكل خطة التعلم التالية (عناوين فقط).")
    lines.append("")
    lines.extend(_render_profile_section(profile))
    lines.append("")
    lines.extend(_render_roadmap_section(roadmap))
    lines.append("")
    lines.append("------------------------------------------------------------")
    lines.append("INSTRUCTIONS")
    lines.append("------------------------------------------------------------")
    lines.append("- أعطِ score من 0 إلى 10.")
    lines.append(
        f"- اضبط `is_acceptable` = true فقط لو score >= "
        f"{ROADMAP_APPROVAL_THRESHOLD}."
    )
    lines.append("- اذكر issues محددة (قائمة فارغة لو لا توجد).")
    lines.append("- اذكر suggestions قابلة للتنفيذ (قائمة فارغة لو لا توجد).")
    lines.append("- اكتب reasoning قصيرًا.")
    lines.append("- لا تعد كتابة الـroadmap — فقط انقد.")
    return "\n".join(lines)


__all__ = [
    "ROADMAP_TITLES_EVALUATION_SYSTEM",
    "build_roadmap_titles_evaluation_prompt",
]
