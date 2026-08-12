"""
check_setup.py - بيتأكد إن كل حاجة جاهزة قبل ما تشغّل الشات أو التست.

بيفحص 5 حاجات بالترتيب وبيقولك بالظبط اللي ناقص وإزاي تظبطه:
    1) مكتبة openai متثبتة
    2) ملف .env موجود وفيه GEMINI_API_KEY
    3) قاعدة البيانات dataco.db موجودة والـ 7 Views جواها
    4) المفتاح شغال فعلاً (نداء صغير جداً للـ API)
    5) الـ Agent بيرد على سؤال حقيقي

التشغيل: دبل كليك على CHECK.bat
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OK, BAD = "  [OK]  ", "  [!!]  "
failures: list[str] = []


def fail(step: str, what: str, how: str) -> None:
    failures.append(step)
    print(f"{BAD}{what}")
    print(f"         الحل: {how}")


print("\n" + "=" * 60)
print("  فحص إعدادات DataCo Ask the Data")
print("=" * 60 + "\n")

# ---------------------------------------------------------------- 1
print("[1/5] مكتبة openai")
try:
    import openai

    print(f"{OK}متثبتة (نسخة {openai.__version__})")
except ImportError:
    fail("1", "مكتبة openai مش متثبتة",
         r".venv\Scripts\python.exe -m pip install openai")

# ---------------------------------------------------------------- 2
print("\n[2/5] ملف .env والمفتاح")
env_path = ROOT / ".env"
if not env_path.exists():
    fail("2", "ملف .env مش موجود خالص",
         "اتبع خطوة 3 في رسالة Claude (أمر cmd اللي بينشئ الملف)")
else:
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        fail("2", "GEMINI_API_KEY مش موجود جوه .env",
             "افتح .env وتأكد إن فيه سطر GEMINI_API_KEY=... من غير مسافات")
    elif key.startswith("gsk_"):
        fail("2", "ده مفتاح Groq قديم مش مفتاح Gemini",
             "اعمل مفتاح جديد من https://aistudio.google.com/apikey")
    elif key in ("AIza...", "المفتاح_اللي_نسخته"):
        fail("2", "المفتاح لسه القيمة النموذجية مش مفتاحك الحقيقي",
             "حط المفتاح اللي نسخته من aistudio.google.com/apikey")
    else:
        print(f"{OK}المفتاح موجود ({key[:6]}...{key[-4:]}، طوله {len(key)} حرف)")
        if key.startswith("AQ."):
            # الشكل الجديد من Google. رسمياً هو البديل للشكل القديم AIza،
            # لكن فيه بلاغات كتير إنه بيترفض على generativelanguage.googleapis.com
            # بـ 401. مش بنوقف الفحص هنا - بنكمل ونجرب فعلاً في خطوة 4.
            print("         ملاحظة: ده الشكل الجديد (AQ.). لو خطوة 4 رجعت 401،")
            print("         الحل في رسالة Claude (مفتاح AIza من Google Cloud Console).")

# ---------------------------------------------------------------- 3
print("\n[3/5] قاعدة البيانات والـ Views")
db_path = ROOT / "dataco.db"
if not db_path.exists():
    fail("3", "ملف dataco.db مش موجود",
         r".venv\Scripts\python.exe build_db.py")
else:
    expected = {"vw_FactOrderItem", "vw_DimCustomer", "vw_DimProduct",
                "vw_DimGeography", "vw_DimShippingMode", "vw_DimOrderStatus",
                "vw_DimOrderType"}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    found = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
    rows = conn.execute("SELECT COUNT(*) FROM vw_FactOrderItem").fetchone()[0] if expected <= found else 0
    conn.close()
    missing = expected - found
    if missing:
        fail("3", f"ناقص Views: {', '.join(sorted(missing))}",
             r".venv\Scripts\python.exe build_db.py")
    else:
        print(f"{OK}الـ 7 Views موجودة، و vw_FactOrderItem فيه {rows:,} صف")

# ---------------------------------------------------------------- 4
print("\n[4/5] المفتاح شغال فعلاً؟")
if failures:
    print("         (اتخطت - ظبّط اللي فوق الأول)")
else:
    try:
        from agent import MODEL_NAME, _client

        client = _client()
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=5,
            messages=[{"role": "user", "content": "Reply with the word OK only."}],
        )
        print(f"{OK}الاتصال بـ Gemini نجح (موديل: {MODEL_NAME})")
        print(f"         رد الموديل: {resp.choices[0].message.content!r}")
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__
        if name in ("AuthenticationError", "PermissionDeniedError"):
            if os.environ.get("GEMINI_API_KEY", "").startswith("AQ."):
                fail("4", "المفتاح مرفوض (401) - وده الشكل الجديد AQ. اللي فيه مشكلة معروفة",
                     "اعمل مفتاح AIza من console.cloud.google.com بدل AI Studio "
                     "(الخطوات في رسالة Claude)")
            else:
                fail("4", "المفتاح مرفوض من Google",
                     "اتأكد إنك نسخت المفتاح كامل من aistudio.google.com/apikey")
        elif name == "NotFoundError":
            fail("4", f"اسم الموديل غلط: {os.environ.get('GEMINI_MODEL')}",
                 "شيل سطر GEMINI_MODEL من .env عشان ياخد الافتراضي")
        else:
            fail("4", f"{name}: {str(e)[:120]}",
                 "صوّر الرسالة دي وابعتها لـ Claude")

# ---------------------------------------------------------------- 5
print("\n[5/5] الـ Agent بيرد على سؤال حقيقي؟")
if failures:
    print("         (اتخطت - ظبّط اللي فوق الأول)")
else:
    try:
        from agent import ask_agent

        answer, queries = ask_agent("كام عميل عندنا في مصر؟")
        print(f"{OK}رد: {answer[:90]}")
        for q in queries:
            print(f"         SQL: {' '.join(q.split())[:100]}")
        if "389" in answer:
            print(f"{OK}الرقم صح (389 - متأكد منه يدوياً من القاعدة)")
        else:
            print("  [??]  الرقم مش 389 - ابعت النتيجة دي لـ Claude يراجعها")
    except Exception as e:  # noqa: BLE001
        fail("5", f"{type(e).__name__}: {str(e)[:120]}",
             "صوّر الرسالة دي وابعتها لـ Claude")

# ---------------------------------------------------------------- النتيجة
print("\n" + "=" * 60)
if failures:
    print(f"  فيه {len(failures)} مشكلة محتاجة تتظبط (الخطوات: {', '.join(failures)})")
    print("  ظبّطها وشغّل CHECK.bat تاني.")
    sys.exit(1)
print("  كل حاجة تمام. تقدر تشغّل TEST.bat أو START.bat دلوقتي.")
print("=" * 60 + "\n")
