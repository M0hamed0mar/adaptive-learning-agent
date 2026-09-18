"""
Prompts for the TutorChat agent.

The tutor chat answers follow-up questions about a specific lesson.
It has access to:
    - the user's profile,
    - the part's brief,
    - the lesson content,
    - (optionally) a web search tool.
"""

from __future__ import annotations

from app.schemas.lesson import Lesson
from app.schemas.profile import UserProfile
from app.schemas.roadmap import ModuleTitle, PartTitle


# ============================================================
# System prompt
# ============================================================

TUTOR_CHAT_SYSTEM: str = """\
أنت مدرّس تقني خبير (technical tutor) في منصة تعلم ذكية.

طالبك أنهى للتو قراءة درس معين، والآن يطرح عليك سؤالًا محددًا
حول هذا الدرس. مهمتك أن تجيبه بدقة ووضوح.

------------------------------------------------------------
القواعد العامة
------------------------------------------------------------
1. اللغة: أجب **بالعربية**، والمصطلحات التقنية **بالإنجليزية** كما هي.
   - مثال: "الـContainer هو بيئة معزولة..."
   - مثال: "استخدم `docker build` لبناء الـimage..."

2. الطول: كن موجزًا ومركّزًا.
   - من فقرة إلى ثلاث فقرات.
   - لا تكتب مقالًا طويلًا.
   - لا تكرر محتوى الدرس حرفيًا.

3. الأسلوب: منظم وواضح.
   - استخدم Markdown (## و ### و - و `` ` `` للأكواد).
   - ابدأ بالإجابة المباشرة، ثم التفاصيل.
   - اذكر أمثلة عملية إن كان ذلك مفيدًا.

4. السياق: أنت تجيب عن **درس محدد**.
   - لا تنحرف عن الموضوع.
   - لو السؤال خارج نطاق الدرس، وجّه الطالب بلطف.

5. لا تخترع معلومات تقنية خاطئة.
   - إن لم تكن متأكدًا، قل "لست متأكدًا" أو استخدم البحث إن كان متاحًا.

------------------------------------------------------------
المرجعية
------------------------------------------------------------
- أنت تعرف مستوى الطالب ودوره (موجود في السياق).
- إن كان السؤال يحتاج معلومات حديثة (2024+، إصدارات جديدة، أخبار)
  ولم يكن لديك معلومات مؤكدة، **استخدم أداة `web_search`**.
- بعد استدعاء الأداة، ادمج النتائج في إجابتك بوضوح.

------------------------------------------------------------
Output
------------------------------------------------------------
- أعد الإجابة كنص Markdown عادي.
- لا preamble ولا توقيع.
- لا تستخدم code fences حول الرد بالكامل.
"""


# ============================================================
# User prompt builder
# ============================================================

def build_tutor_chat_user_prompt(
    *,
    question: str,
    profile: UserProfile,
    module: ModuleTitle,
    part: PartTitle,
    part_id: str,
    lesson: Lesson | None,
) -> str:
    """
    Build the user prompt for the chat.

    Includes the profile + part + lesson content + question.
    """
    lines: list[str] = []

    # --- Context header ---
    lines.append("أنت تجيب عن سؤال حول الدرس التالي.")
    lines.append("")

    # --- Profile ---
    lines.append("## بيانات الطالب")
    lines.append(f"- Topic:    {profile.topic}")
    lines.append(f"- Level:    {profile.level.value}")
    lines.append(f"- Role:     {profile.role}")
    lines.append(f"- Language: {profile.language}")
    lines.append("")

    # --- Lesson context ---
    lines.append("## الدرس الحالي")
    lines.append(f"- Module:   {module.title}")
    lines.append(f"- Part ID:  {part_id}")
    lines.append(f"- Title:    {part.title}")
    lines.append("")

    # --- Lesson content (truncated) ---
    if lesson is not None and lesson.content:
        content_preview = lesson.content.strip()
        if len(content_preview) > 4000:
            content_preview = content_preview[:4000] + "\n\n[... الدرس طويل، مقتطف]"
        lines.append("## محتوى الدرس (للسياق)")
        lines.append(content_preview)
        lines.append("")

    # --- Question ---
    lines.append("## سؤال الطالب")
    lines.append(question)
    lines.append("")
    lines.append("------------------------------------------------------------")
    lines.append("Instructions:")
    lines.append("- أجب على السؤال بناءً على السياق أعلاه.")
    lines.append("- إن احتجت معلومات حديثة، استخدم أداة `web_search`.")
    lines.append("- كن موجزًا وواضحًا. الشرح عربي + المصطلحات الإنجليزية.")
    lines.append("- استخدم Markdown.")

    return "\n".join(lines)


__all__ = [
    "TUTOR_CHAT_SYSTEM",
    "build_tutor_chat_user_prompt",
]
