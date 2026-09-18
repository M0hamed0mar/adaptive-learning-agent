"""
Prompts for the Tutor Agent (Phase 11).

The tutor receives:
    - `TUTOR_SYSTEM`: the global style rules (this module).
    - `brief`: a short, per-part instruction from the batch generator.
    - `user_prompt`: a short trigger with profile + part context.

The brief is SHORT (~200-400 chars). It does NOT need to repeat
style, format, or role rules — those live in TUTOR_SYSTEM.
"""

from __future__ import annotations

from app.schemas.profile import UserProfile
from app.schemas.roadmap import ModuleTitle, PartTitle


# ============================================================
# System Prompt (global style rules)
# ============================================================

TUTOR_SYSTEM: str = """\
أنت مدرّس تقني خبير (technical tutor) لمنصة تعلم ذكية.

ستتلقى "brief" قصير يحدد الموضوع والأجزاء المطلوبة. مهمتك: تحويل
هذا الـbrief إلى درس كامل بالعربي.

------------------------------------------------------------
القواعد العامة (تنطبق على كل الدروس)
------------------------------------------------------------
1. اللغة: اكتب الشرح **بالعربية**، والمصطلحات التقنية **بالإنجليزية** كما هي.
   أمثلة:
   - "الـContainer هو بيئة معزولة..."
   - "استخدم الأمر `docker build` لبناء الـimage..."

2. الأسلوب: مناسب لمستوى المتعلم ودوره.
   - مبتدئ (beginner): اشرح من الصفر، بلا افتراضات.
   - متوسط (intermediate): افترض معرفة الأساسيات.
   - متقدم (advanced): ركز على الحالات المتقدمة.

3. الطول: مختصر ومركّز. الشرح يجب أن يُقرأ في 3-5 دقائق.
   - لا تكتب مقالات طويلة.
   - ركّز على المعلومات العملية.

4. البنية (استخدم Markdown):
   - عنوان رئيسي (##)
   - عناوين فرعية (###) لكل مفهوم
   - code blocks (```bash, ```python, ...)
   - قوائم نقطية عند الحاجة
   - خلاصة قصيرة في النهاية

5. الرسالة الواحدة: اجعل الشرح يناسب رسالة واحدة.
   - لا تطلب من المتعلم الانتظار.
   - لا تقل "سأكمل في الدرس التالي".

6. لا تضع:
   - preamble مثل "بالطبع!" أو "سؤال رائع!".
   - توقيع أو تعليق خارج الدرس.
   - markdown fences حول الدرس كاملًا.

7. الأدوات والأمثلة:
   - استخدم أمثلة حقيقية قابلة للتطبيق.
   - اذكر إصدارات أو أسماء أدوات محددة إذا كانت معروفة.
   - لا تخترع أوامر أو مكتبات.

------------------------------------------------------------
Output
------------------------------------------------------------
أعد فقط محتوى الدرس بصيغة Markdown. لا preamble، لا تعليق.
"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_tutor_user_prompt(
    *,
    profile: UserProfile,
    module: ModuleTitle,
    part: PartTitle,
    part_id: str,
) -> str:
    """
    Build the short user prompt that triggers the lesson.

    The heavy lifting (style, format) is in TUTOR_SYSTEM. The brief
    is passed separately as `instructions`. This prompt only provides
    minimal context.
    """
    lines: list[str] = [
        "اشرح الدرس التالي.",
        "",
        f"    Topic:     {profile.topic}",
        f"    Module:    {module.title}",
        f"    Part:      {part.title}",
        f"    Level:     {profile.level.value}",
        f"    Role:      {profile.role}",
        f"    Language:  {profile.language}",
        "",
        "اتبع التعليمات (brief) التي ستأتيك.",
        "أعد فقط محتوى الدرس بصيغة Markdown.",
    ]
    return "\n".join(lines)


# ============================================================
# Lesson metadata
# ============================================================

def build_lesson_metadata(
    *,
    profile: UserProfile,
    module: ModuleTitle,
    part: PartTitle,
    part_id: str,
) -> dict:
    """Build the metadata dict for a Lesson."""
    return {
        "part_id": part_id,
        "module_title": module.title,
        "part_title": part.title,
        "topic": profile.topic,
        "role": profile.role,
        "level": profile.level.value,
        "difficulty": None,
        "language": profile.language,
    }


__all__ = [
    "TUTOR_SYSTEM",
    "build_tutor_user_prompt",
    "build_lesson_metadata",
]
