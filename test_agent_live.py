"""
test_agent_live.py - اختبار حقيقي للـ Agent بأسئلة "زي ما الناس بتكتب".

بيشغّل أسئلة فيها عامية مصرية، أخطاء إملائية، حروف ناقصة، Arabizi،
عربي مخلوط بإنجليزي، واختصارات - وبيطبع لكل سؤال: الكويري اللي اتنفذ
فعلاً + الإجابة، عشان تشوف بنفسك هل فهم المقصود ولا لأ.

التشغيل (من مجلد المشروع، والـ .venv مفعّل):
    .venv\\Scripts\\python.exe test_agent_live.py          <- 4 أسئلة (الافتراضي)
    .venv\\Scripts\\python.exe test_agent_live.py 3        <- 3 أسئلة بس
    .venv\\Scripts\\python.exe test_agent_live.py all      <- كل الأسئلة (بيستهلك كتير)

مهم - استهلاك الخطة المجانية:
السؤال الواحد بياخد حوالي 5,000-8,000 توكن (نداءين، أو 3 لو احتاج مراجعة ذاتية).
الحدود المجانية: 12,000 توكن/دقيقة و100,000 توكن/يوم.
يعني عملياً حوالي 15-18 سؤال في اليوم كحد أقصى. عشان كده السكريبت بيستنى
بين كل سؤال والتاني، ومابيشغلش كل الأسئلة إلا لما تطلب كده صراحة.

النتيجة بتتحفظ كمان في ملف test_results.txt جنب السكريبت.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from agent import ask_agent

# أسئلة مكتوبة بالظبط زي ما مستخدم حقيقي هيكتبها - مش أسئلة مثالية.
# جنب كل سؤال المتوقع منه، عشان تقدر تحكم بسرعة صح ولا غلط.
QUESTIONS: list[tuple[str, str]] = [
    ("كام عميل عندنا ف افريقيا والايراد بتاعهم كام",
     "عدد العملاء المختلفين في سوق Africa + إجمالي المبيعات"),

    ("3ayez a3raf el late delivery rate",
     "نسبة التأخير (Arabizi - عربي بحروف إنجليزي)"),

    ("ايه اكتر منتج بيتباع",
     "أعلى منتج مبيعاً (سؤال قصير وبدون علامات ترقيم)"),

    ("متوسط قيمه الاوردر كام",
     "SUM(sales)/COUNT(DISTINCT order_id) - مش AVG(sales)"),

    ("عاوز اعرف ايراد قسم الtechnology",
     "عربي + إنجليزي في نفس الجملة"),

    ("انهي دوله بتجبلنا اكبر ربح",
     "أعلى دولة في الربح - فيها أخطاء إملائية"),

    ("كام اوردر اتأخر الشهر ده",
     "عدد الطلبات المتأخرة (ممكن يطلب توضيح عن الشهر)"),

    ("el customers bto3 corporate 3adadhom kam",
     "عدد عملاء شريحة Corporate بالـ Arabizi"),

    ("مبيعات مصر vs المكسيك",
     "مقارنة بين دولتين - اسمين مخزنين بالإسباني"),

    ("شحن same day بياخد كام يوم فالمتوسط",
     "متوسط أيام الشحن لطريقة Same Day"),

    ("عندنا كام منتج مختلف",
     "COUNT(DISTINCT product_id) - مش COUNT(*)"),

    ("ايه احسن 3 اقسام من ناحيه الربح",
     "أعلى 3 أقسام في الربح"),

    ("الطقس عامل ايه النهارده",
     "سؤال خارج نطاق البيانات - المفروض يرفض بأدب من غير ما ينفذ كويري"),

    ("asdkjh askdjh",
     "كلام عشوائي - المفروض يطلب سؤال واضح"),
]


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "4"
    if arg == "all":
        chosen = QUESTIONS
    else:
        try:
            chosen = QUESTIONS[: int(arg)]
        except ValueError:
            print(f"وسيط غير مفهوم: {arg!r}. استخدم رقم أو 'all'.")
            return

    print(f"هيتم تشغيل {len(chosen)} سؤال.")
    print("تقدير الاستهلاك: حوالي", len(chosen) * 6, "ألف توكن من حد الـ 100 ألف اليومي.\n")

    lines: list[str] = []
    for i, (question, expected) in enumerate(chosen, 1):
        header = f"\n{'='*70}\n[{i}/{len(chosen)}] السؤال كما كتبه المستخدم:\n  {question}\n  المتوقع: {expected}"
        print(header)
        lines.append(header)

        started = time.time()
        try:
            answer, queries = ask_agent(question)
        except Exception as e:  # noqa: BLE001
            answer, queries = f"[استثناء] {type(e).__name__}: {e}", []
        took = time.time() - started

        block = [f"\n  الإجابة ({took:.1f} ثانية):\n    {answer}"]
        if queries:
            block.append("  الكويري اللي اتنفذ فعلاً:")
            block.extend(f"    {q}" for q in queries)
        else:
            block.append("  (مفيش كويري اتنفذ - وده صح لو السؤال خارج نطاق البيانات)")

        out = "\n".join(block)
        print(out)
        lines.append(out)

        # استنى بين الأسئلة عشان مانعديش حد التوكنز في الدقيقة (12,000).
        if i < len(chosen):
            print("\n  ...استنى 20 ثانية عشان حد الـ rate limit")
            time.sleep(20)

    path = Path(__file__).resolve().parent / "test_results.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n\nالنتايج اتحفظت في: {path}")


if __name__ == "__main__":
    main()
