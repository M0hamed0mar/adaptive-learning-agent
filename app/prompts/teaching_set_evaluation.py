"""
Prompts for the Teaching Prompt Set Critic (Phase 11).

The critic evaluates a whole batch of teaching prompts and returns
ONE score + issues + suggestions.
"""

from __future__ import annotations

from app.config.constants import PROMPT_SET_APPROVAL_THRESHOLD
from app.schemas.profile import UserProfile
from app.schemas.roadmap import RoadmapTitles


# ============================================================
# System Prompt
# ============================================================

TEACHING_SET_EVALUATION_SYSTEM: str = f"""\
أنت ناقد جودة teaching prompts لمنصة تعلم ذكية.

مهمتك: تقييم مجموعة كاملة من الـteaching prompts (batch) قبل
إرسالها إلى الـtutor agent.

⚠️ أنت لا تعيد كتابة الـprompts. أنت فقط:
    - تصف المشاكل بدقة.
    - تقترح تحسينات قابلة للتنفيذ.

------------------------------------------------------------
معايير التقييم
------------------------------------------------------------
قيّم كل prompt فرديًا ثم أعطِ score عامًا للمجموعة:

1. جودة البنية (Structure Quality)
   - هل يحتوي كل prompt على الأقسام المطلوبة:
     * ROLE
     * LESSON CONTEXT
     * TEACHING REQUIREMENTS
     * STYLE AND CONSTRAINTS
     * OUTPUT FORMAT?

2. التخصيص (Tailoring)
   - هل الـprompt مخصص لـrole المستخدم؟
   - هل العمق مناسب لـlevel؟
   - هل التوازن يناسب learning_style؟

3. اللغة (Language)
   - هل الشرح بالعربي؟
   - هل المصطلحات التقنية بالإنجليزية كما هي؟
   - هل الأسلوب سلس ومقروء؟

4. الاستقلالية (Self-Containment)
   - هل الـprompt مستقل بذاته؟
   - هل يحتاج الـtutor لمعلومات إضافية؟
   - هل هناك placeholders أو JSON غير مقصود؟

5. الحجم والتركيز (Size & Focus)
   - هل الـprompt مركّز على الـpart فقط؟
   - هل حجم الدرس صغير (رسالة واحدة)؟
   - هل هناك تفاصيل زيادة لا لزوم لها؟

6. عدم التكرار (No Redundancy)
   - هل هناك prompts متشابهة جدًا؟
   - هل هناك أجزاء تم تجاهلها؟

------------------------------------------------------------
Scoring Rubric (0-10)
------------------------------------------------------------
9.0 - 10.0  ممتاز: كل الـprompts عالية الجودة ومُخصصة.
8.0 -  8.9  جيد: تحسينات طفيفة ممكنة لكنه مقبول.
6.5 -  7.9  متوسط: بعض الـprompts تحتاج تحسين.
4.5 -  6.4  ضعيف: مشاكل متعددة في عدة prompts.
0.0 -  4.4  غير قابل للاستخدام: مشاكل جوهرية.

⚠️ اضبط `is_acceptable` = true فقط لو `score` >= {PROMPT_SET_APPROVAL_THRESHOLD}.

------------------------------------------------------------
قواعد
------------------------------------------------------------
1. اعتمد فقط على الـprompts والـprofile والـroadmap المعطاة.
2. المشاكل يجب أن تكون محددة: اذكر الـpart_id.
3. الاقتراحات قابلة للتنفيذ.
4. كن صارمًا: prompt عام وغير مُخصص يجب ألا يتعدى 7.0.
5. اكتب `reasoning` قصيرًا.
"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_teaching_set_evaluation_prompt(
    profile: UserProfile,
    roadmap: RoadmapTitles,
    prompts: list[tuple[str, str, str]],  # (part_id, title, prompt)
) -> str:
    """
    Build the user prompt for teaching prompt set evaluation.

    Args:
        profile: The user's learning profile.
        roadmap: The roadmap titles (context).
        prompts: List of (part_id, title, prompt) tuples.

    Returns:
        A formatted prompt for the critic.
    """
    lines: list[str] = []
    lines.append("قيّم مجموعة الـteaching prompts التالية.")
    lines.append("")

    # Profile
    lines.append("بيانات المتعلم:")
    lines.append(f"    - Topic:            {profile.topic}")
    lines.append(f"    - Level:            {profile.level.value}")
    lines.append(f"    - Goal:             {profile.goal.value}")
    lines.append(f"    - Role:             {profile.role}")
    lines.append(f"    - Learning style:   {profile.learning_style.value}")
    lines.append("")

    # Roadmap (context)
    lines.append("الـroadmap (للتوضيح):")
    for i, module in enumerate(roadmap.modules, start=1):
        lines.append(f"    [M{i}] {module.title}")
    lines.append("")

    # Prompts
    lines.append("------------------------------------------------------------")
    lines.append("PROMPTS TO EVALUATE")
    lines.append("------------------------------------------------------------")
    for part_id, title, prompt in prompts:
        lines.append("")
        lines.append(f"### [{part_id}] {title}")
        lines.append(prompt)

    lines.append("")
    lines.append("------------------------------------------------------------")
    lines.append("INSTRUCTIONS")
    lines.append("------------------------------------------------------------")
    lines.append("- أعطِ score من 0 إلى 10 للمجموعة كاملة.")
    lines.append(
        f"- اضبط `is_acceptable` = true فقط لو score >= "
        f"{PROMPT_SET_APPROVAL_THRESHOLD}."
    )
    lines.append("- اذكر issues محددة (مع part_id عند الإمكان).")
    lines.append("- اذكر suggestions قابلة للتنفيذ.")
    lines.append("- اكتب reasoning قصيرًا.")
    lines.append("- لا تعد كتابة الـprompts — فقط انقد.")
    return "\n".join(lines)


__all__ = [
    "TEACHING_SET_EVALUATION_SYSTEM",
    "build_teaching_set_evaluation_prompt",
]
