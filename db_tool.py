"""
db_tool.py - الأداة الوحيدة اللي بيستخدمها الـ Agent عشان يقرأ من قاعدة البيانات.

النسخة دي بتشتغل على SQLite (dataco.db) بدل SQL Server، لأن ده هو
مصدر البيانات اللي الموقع اللايف (app.py على Render) شغال عليه بالفعل.

القيود الأمنية (متطابقة مع قرار الماستر برومبت):
    1) لازم يبدأ الكويري بـ SELECT فقط.
    2) ممنوع أكتر من جملة SQL واحدة.
    3) لازم يستخدم واحد على الأقل من الـ 7 Views المسموحة (vw_*)،
       مش الجداول الخام.
    4) أقصى 50 صف في الرد - متفروضة هنا جوه الـ SQL نفسه (LIMIT)،
       مش بعد ما البيانات تتسحب بالكامل من القاعدة.

تحصينات إضافية اتضافت هنا مش موجودة في النسخة الأصلية:
    - الاتصال بيتفتح دايماً READ-ONLY على مستوى SQLite نفسه
      (mode=ro) - يعني حتى لو فيه ثغرة في فحص الكلمات المحظورة،
      SQLite بيرفض أي كتابة على مستوى المحرك مش بس على مستوى الفحص النصي.
    - إصلاح ثغرة sp_/xp_: كانت \\b بعد الـ underscore بتمنع الفحص من
      اكتشاف sp_executesql أو xp_cmdshell لأن الـ underscore حرف "كلمة"
      زي أي حرف تاني، فمفيش حدود كلمة (word boundary) بين الـ _ والحرف
      اللي بعده.
    - إغلاق الاتصال بقى مضمون دايماً (try/finally)، حتى لو الكويري فشل.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "dataco.db"

MAX_ROWS = 50

ALLOWED_VIEWS = {
    "vw_FactOrderItem",
    "vw_DimCustomer",
    "vw_DimProduct",
    "vw_DimGeography",
    "vw_DimShippingMode",
    "vw_DimOrderStatus",
    "vw_DimOrderType",
}

# كلمات لازم تتفحص بحدود كلمة كاملة (\b...\b) - يعني "GRANT" ما تطابقش
# جوه كلمة تانية زي "GRANTED".
BLOCKED_KEYWORDS_WHOLE_WORD = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "EXEC", "EXECUTE", "TRUNCATE", "MERGE", "GRANT",
    "REVOKE", "CREATE", "ATTACH", "DETACH", "PRAGMA",
]

# sp_ و xp_ بادئات، مش كلمات كاملة - فحصها بحدود كلمة من الأول بس،
# عشان sp_executesql وxp_cmdshell يتصادوا صح (كانت النسخة القديمة
# بتفوّتهم بسبب \b بعد الـ underscore).
BLOCKED_PREFIXES = ["SP_", "XP_"]


def is_query_safe(sql_query: str) -> tuple[bool, str]:
    stripped = sql_query.strip().rstrip(";").strip()
    normalized = stripped.upper()

    if not normalized.startswith("SELECT"):
        return False, "الاستعلام مرفوض: يُسمح فقط بأوامر SELECT للقراءة"

    if ";" in stripped:
        return False, "الاستعلام مرفوض: غير مسموح بأكثر من جملة SQL واحدة"

    for keyword in BLOCKED_KEYWORDS_WHOLE_WORD:
        if re.search(r"\b" + keyword + r"\b", normalized):
            return False, f"الاستعلام مرفوض: الكلمة '{keyword}' غير مسموح بها"

    for prefix in BLOCKED_PREFIXES:
        if re.search(r"\b" + prefix, normalized):
            return False, f"الاستعلام مرفوض: البادئة '{prefix}' غير مسموح بها"

    found_any_view = any(
        re.search(r"\b" + view.upper() + r"\b", normalized) for view in ALLOWED_VIEWS
    )
    if not found_any_view:
        return False, "الاستعلام مرفوض: يجب استخدام أحد الـ Views المسموحة فقط"

    return True, ""


def run_sql_query(sql_query: str) -> dict:
    is_safe, reason = is_query_safe(sql_query)
    if not is_safe:
        return {"status": "rejected", "message": reason}

    stripped = sql_query.strip().rstrip(";").strip()
    # أقصى 50 صف مفروضة جوه الـ SQL نفسه (subquery + LIMIT)، مش بعد
    # ما كل الصفوف تتسحب من القاعدة - عشان كويري زي
    # "SELECT * FROM vw_FactOrderItem" (180 ألف صف) ما يعلقش السيرفر.
    capped_query = f"SELECT * FROM ({stripped}) AS _capped LIMIT {MAX_ROWS}"

    conn = None
    try:
        # mode=ro: حتى لو فيه ثغرة في الفحص النصي فوق، SQLite نفسه
        # هيرفض أي محاولة كتابة على مستوى المحرك.
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(capped_query)

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

        if len(rows) == 0:
            # الرسالة دي بتروح للموديل نفسه مش للمستخدم - فمكتوبة بالإنجليزي
            # (أرخص في التوكنز) وبتقوله يعمل إيه بدل ما تقوله "مفيش نتايج"
            # وخلاص. ده اللي بيخلي الـ Agent يصحح نفسه لما المستخدم يكتب
            # اسم بشكل مختلف عن المخزّن (إملاء مختلف، اسم إسباني، مسافات زايدة).
            return {
                "status": "no_results",
                "message": (
                    "Query ran successfully but matched 0 rows. The filter value is "
                    "probably spelled differently in the database (some values "
                    "contain stray spaces, and order_state uses local spellings). "
                    "Do NOT tell the user the answer is zero yet. First run "
                    "SELECT DISTINCT <column> FROM <view> WHERE <column> LIKE '%<part>%' "
                    "to find the exact stored value, then retry the original query."
                ),
            }

        results = [dict(zip(columns, row)) for row in rows]

        return {
            "status": "success",
            "row_count": len(results),
            "data": results,
        }

    except sqlite3.Error as e:
        return {"status": "error", "message": f"خطأ في تنفيذ الاستعلام: {str(e)}"}
    finally:
        if conn is not None:
            conn.close()
