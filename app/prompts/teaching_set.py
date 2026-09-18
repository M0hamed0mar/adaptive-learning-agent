"""
Prompts for the Teaching Prompt Set Generator (Phase 11).

Generates SHORT "briefs" (200-400 chars each), NOT full teaching
prompts. The tutor expands each brief into a full lesson using the
global TUTOR_SYSTEM rules.

Why briefs?
    - Full prompts were ~1800 chars each → slow and token-heavy.
    - Briefs are 4-6x smaller → much faster, fewer tokens.
    - Style and format rules live in TUTOR_SYSTEM (fixed).
    - Quality is preserved: the tutor sees the full style guide.
"""

from __future__ import annotations

from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles


# ============================================================
# System Prompt
# ============================================================

TEACHING_SET_GENERATION_SYSTEM: str = """\
أنت مصمم تعليمي (instructional designer) لمنصة تعلم ذكية.

مهمتك: كتابة "brief" قصير لكل جزء في الـroadmap. الـbrief ده سيُسلَّم
لمدرّس AI (tutor)، الذي سيوسّعه إلى درس كامل.

------------------------------------------------------------
ما هو الـbrief المثالي؟
------------------------------------------------------------
الـbrief عبارة عن 200-400 حرف (سطرين إلى أربعة أسطر) يحتوي على:

1. جملة تمهيدية تذكر:
   - من هو المدرّس (مثال: "أنت مدرّس Docker").
   - من هو المتعلم (مثال: "للمهندس AI المبتدئ").
   - الموضوع بالضبط.

2. قائمة قصيرة (2-4 نقاط) بالمواضيع الفرعية التي يجب أن يتناولها الدرس.
   - مثال: "تعريف الـContainer، الفرق بينه وبين الـVM، مثال عملي".

3. متطلب خاص إن وُجد:
   - مثال: "استخدم code blocks".
   - مثال: "اذكر أخطاء شائعة".
   - مثال: "ركّز على تطبيقات ML".

------------------------------------------------------------
ما لا يجب أن يحتويه الـbrief
------------------------------------------------------------
❌ لا تكتب ROLE أو LESSON CONTEXT أو OUTPUT FORMAT — هذه في TUTOR_SYSTEM.
❌ لا تكرر قواعد اللغة أو الأسلوب — هذه ثابتة في TUTOR_SYSTEM.
❌ لا تكتب المقدمة/الخاتمة/الأمثلة الكاملة — الـtutor سيكتبها.
❌ لا تتجاوز 400 حرف.

------------------------------------------------------------
قواعد التخصيص
------------------------------------------------------------
- role: أمثلة الـbrief يجب أن تناسب دور المتعلم.
- level: عمق الشرح المطلوب في الـbrief.
- learning_style:
    * practical  → ركّز على الأمثلة العملية في الـbrief.
    * theoretical → ركّز على الشرح المفاهيمي.
    * balanced → توازن.
- raw_input: أي تفاصيل خاصة من وصف المستخدم.

------------------------------------------------------------
Output
------------------------------------------------------------
- أعد JSON فقط.
- املأ `part_id` و `title` من القائمة المعطاة.
- `prompt` = الـbrief القصير (200-400 حرف).
"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_teaching_set_prompt(
    profile: UserProfile,
    roadmap: RoadmapTitles,
    batch: list[tuple[str, str]],
) -> str:
    """
    Build the user prompt for a batch of briefs.

    Args:
        profile: The user's learning profile.
        roadmap: The roadmap skeleton (context).
        batch: List of (part_id, title) tuples to write briefs for.

    Returns:
        A formatted prompt ready to send to the LLM.
    """
    lines: list[str] = []
    lines.append("اكتب brief قصير لكل جزء من الأجزاء التالية.")
    lines.append("")

    # Profile context
    lines.append("بيانات المتعلم:")
    lines.append(f"    - Topic:           {profile.topic}")
    lines.append(f"    - Level:           {profile.level.value}")
    lines.append(f"    - Goal:            {profile.goal.value}")
    lines.append(f"    - Role:            {profile.role}")
    lines.append(f"    - Learning style:  {profile.learning_style.value}")
    lines.append("")

    # Full roadmap context (helps understand prerequisites)
    lines.append("الـroadmap الكامل (للسياق):")
    for i, module in enumerate(roadmap.modules, start=1):
        lines.append(f"    [M{i}] {module.title}")
        for j, part in enumerate(module.parts, start=1):
            lines.append(f"        [{i}-{j}] {part.title}")
    lines.append("")

    # The batch
    lines.append("-" * 60)
    lines.append(f"الأجزاء المطلوبة في هذه الدفعة ({len(batch)} أجزاء):")
    lines.append("-" * 60)
    for part_id, title in batch:
        lines.append(f"    - [{part_id}] {title}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("المطلوب:")
    lines.append("-" * 60)
    lines.append(f"- اكتب brief قصير (200-400 حرف) لكل جزء من الأجزاء {len(batch)}.")
    lines.append("- املأ `part_id` و `title` بنفس القيم من القائمة.")
    lines.append("- الشرح بالعربي + المصطلحات التقنية بالإنجليزية.")
    lines.append("- أعد JSON فقط.")

    return "\n".join(lines)


# ============================================================
# Refinement — System + User
# ============================================================

TEACHING_SET_REFINEMENT_SYSTEM: str = """\
أنت مصمم تعليمي مسؤول عن تحسين briefs موجودة.

مهمتك: تحسين briefs بناءً على ملاحظات ناقد (critic). لا تبدأ من الصفر.

------------------------------------------------------------
مبادئ التحسين
------------------------------------------------------------
1. حافظ على بنية الـbrief (جملة تمهيدية + 2-4 نقاط + متطلب خاص).
2. اجعل الـbrief أوضح وأكثر تحديدًا.
3. تأكد أن الـbrief لا يزال 200-400 حرف.
4. طبّق كل ملاحظة من الناقد.
5. لا تُضِف تفاصيل زيادة تخرج عن نطاق الـpart.

------------------------------------------------------------
Output
------------------------------------------------------------
- أعد JSON كاملًا بنفس بنية المدخل.
- لا تُعِد diff أو وصف التغييرات.
"""


def build_teaching_set_refinement_prompt(
    profile: UserProfile,
    roadmap: RoadmapTitles,
    current_briefs: list[tuple[str, str, str]],  # (part_id, title, brief)
    critique_score: float,
    issues: list[str],
    suggestions: list[str],
    reasoning: str,
) -> str:
    """Build the user prompt for brief refinement."""
    lines: list[str] = []
    lines.append("حسّن الـbriefs التالية بناءً على ملاحظات الناقد.")
    lines.append("")

    # Profile
    lines.append("بيانات المتعلم:")
    lines.append(f"    - Topic:           {profile.topic}")
    lines.append(f"    - Level:           {profile.level.value}")
    lines.append(f"    - Role:            {profile.role}")
    lines.append("")

    # Current briefs
    lines.append("-" * 60)
    lines.append("CURRENT BRIEFS")
    lines.append("-" * 60)
    for part_id, title, brief in current_briefs:
        lines.append("")
        lines.append(f"### [{part_id}] {title}")
        lines.append(brief)

    lines.append("")
    lines.append("-" * 60)
    lines.append("CRITIC FEEDBACK")
    lines.append("-" * 60)
    lines.append(f"    Score: {critique_score} / 10")
    lines.append("")
    lines.append("    Issues:")
    for issue in issues or ["(none)"]:
        lines.append(f"        - {issue}")
    lines.append("")
    lines.append("    Suggestions:")
    for sug in suggestions or ["(none)"]:
        lines.append(f"        - {sug}")
    lines.append("")
    lines.append(f"    Reasoning: {reasoning}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("المطلوب:")
    lines.append("-" * 60)
    lines.append("- طبّق كل suggestion.")
    lines.append("- عالج كل issue.")
    lines.append("- أعد الـbriefs الكاملة في JSON.")
    lines.append("- حافظ على البنية (200-400 حرف لكل brief).")

    return "\n".join(lines)


__all__ = [
    "TEACHING_SET_GENERATION_SYSTEM",
    "build_teaching_set_prompt",
    "TEACHING_SET_REFINEMENT_SYSTEM",
    "build_teaching_set_refinement_prompt",
]
