"""
agent.py - الـ NL-to-SQL Agent (اسمه الصحيح ده، مش RAG - راجع الملاحظة
في نهاية الملف لو حابب تعرف الفرق).

بيستخدم Google Gemini API (مجاني بدون بطاقة ائتمان) بدل الموديل المحلي
(Ollama)، عشان يقدر يشتغل لايف على الموقع (Render) مش بس على جهاز الطالب.

ليه Gemini مش Groq؟ الاتنين مجانيين، بس حدود الخطة المجانية مختلفة تماماً:
    Groq  : 100,000 توكن في اليوم  -> حوالي 15-18 سؤال بس
    Gemini: 1,500 طلب في اليوم، ومفيش حد توكنز يومي -> ~500 سؤال
Groq أسرع، بس الحد اليومي بتاعه كان بيخلص في نص يوم شغل.

بنتكلم مع Gemini من خلال الـ OpenAI-compatible endpoint بتاعه، عشان شكل
الـ tool calling يفضل زي ما هو بالظبط (نفس الحلقة، نفس صيغة الأدوات)،
والفرق الوحيد هو الـ base_url واسم الموديل.

الفرق الجوهري عن النسخة القديمة: حلقة الأدوات هنا بتكرر لحد ما الموديل
يوصل لإجابة نهائية (مش تنفيذ واحد بس)، عشان سؤال زي "قارنلي مصر
بالمكسيك" اللي محتاج كذا كويري يشتغل صح.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# الـ SDK بتاع OpenAI بيتكلم مع Gemini عادي عن طريق base_url مخصص.
# أسماء الاستثناءات هنا هي نفسها اللي كانت في groq، فمنطق معالجة
# الأخطاء تحت اشتغل زي ما هو من غير تغيير.
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from db_tool import run_sql_query

load_dotenv()  # محلياً بيقرأ .env لو موجود - على Render مالوش تأثير لأن
# متغيرات البيئة بتتضبط من الـ Dashboard مباشرة، مفيش ملف .env أصلاً هناك

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# gemini-3.5-flash-lite: أسرع وأرخص موديل ثابت (مش preview) - مناسب
# لشغل زي بتاعنا: أسئلة قصيرة + استدعاء أدوات كتير.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_TOOL_ROUNDS = 6  # حماية من أي حلقة لا نهائية لو الموديل فضل يطلب أدوات
MAX_GENERATION_RETRIES = 2  # عدد إعادة المحاولات لو الموديل كتب استدعاء أداة بصيغة غلط
MAX_HISTORY_MESSAGES = 6  # آخر 3 أسئلة وردودها بس - حماية من تضخّم السياق

ROOT = Path(__file__).resolve().parent
AUDIT_LOG_PATH = ROOT / "agent_log.jsonl"

# ملاحظة مهمة عن الحجم: الـ system prompt ده بيتبعت للموديل مع *كل* نداء
# (يعني 2-3 مرات في السؤال الواحد)، فكل توكن هنا بيتضرب في عدد النداءات.
# مع Gemini الحدود واسعة، بس تقليل التوكنز لسه بيخلي الرد أسرع وأرخص.
# عشان كده اتكتب بالإنجليزي مش بالعربي: النص العربي بياخد تقريباً 4 أضعاف
# التوكنز مقارنة بنفس المعنى بالإنجليزي. ده مالوش أي تأثير على لغة الرد -
# الموديل لسه بيرد بالعربي لو السؤال عربي (أول قاعدة تحت).
# جدول الدول كمان اتقلّل: الدول اللي اسمها الإسباني = الإنجليزي اتشالت
# واتعوضت بسطر واحد، فمفيش أي معلومة ضاعت.
SCHEMA_DESCRIPTION = """
You are a data analyst for DataCo's supply chain database.
You have READ-ONLY access (SELECT) to exactly 7 views. Never write any
statement other than SELECT. Every query must reference one of the 7 views below.

ALWAYS reply in the SAME LANGUAGE the user asked in (if the user writes in
Arabic, answer in Arabic). Use only the exact numbers returned by the query.
Never estimate, guess, or invent a number.

RULE 0 (scope): If the question is not about DataCo data (general knowledge,
gibberish, random characters, or an unrelated topic), do NOT call the tool.
Reply briefly that you only cover DataCo data (sales, customers, products,
shipping, profit) and ask for a related question. If the question is ambiguous
but might be about the data, ask for clarification instead of guessing.

RULE 1 (which country column): For a general question like "how many customers
in <country>", always use vw_DimGeography.order_country_name - NOT
vw_DimCustomer.country. vw_DimCustomer.country only has two values
(EE. UU., Puerto Rico) and will give a wrong answer for any other country.

RULE 2 (country names are English): Country names are stored in ENGLISH
(Egypt, Germany, United States, Mexico...). They never contain Arabic. If the
user names a country in Arabic, translate it to English before writing WHERE:
"مصر" -> 'Egypt', "ألمانيا" -> 'Germany'. Never put Arabic inside a WHERE.
One legacy exception: order_state (province/state) is still in Spanish for some
countries, so use LIKE there and expect local spellings.

RULE 3 (grain - the most common mistake): Each row of vw_FactOrderItem is ONE
ORDER LINE, not a customer and not a whole order. One customer appears in many
rows; one order can span several rows.
- "how many customers"  -> COUNT(DISTINCT customer_id)  - NEVER COUNT(*)
- "how many orders"     -> COUNT(DISTINCT order_id)     - NEVER COUNT(*)
COUNT(*) on this view returns the number of order lines, which is neither the
customer count nor the order count.
Example: "كام عميل عندنا في مصر؟" -> SELECT COUNT(DISTINCT customer_id) ...

RULE 4 (same mistake, other shapes - count the right unit, not rows):
- "average order value" = SUM(sales) / COUNT(DISTINCT order_id)
  NEVER AVG(sales) directly (that averages a single line, a different number).
- "how many different products were sold" (variety) = COUNT(DISTINCT product_id)
- "how many units were sold" (quantity)  = SUM(order_item_quantity)
  Those last two are different questions with different answers - read carefully.
- Revenue and profit (SUM(sales), SUM(profit_amount)) are NOT affected by this;
  plain SUM is correct. The problem is only with COUNT and AVG.

RULE 5 (self-review): Before finalising any answer containing a "count" or an
"average", check yourself: is the question about distinct entities (customers /
orders / distinct products) rather than rows? Did you put DISTINCT in the right
place? If you find your query was wrong, write a corrected query and call the
tool again before answering. Never confirm a number you are not sure about.

RULE 6 (understand intent, not spelling): Real users write casually - Egyptian
dialect, heavy typos, missing or extra letters, Arabizi (Arabic in Latin
letters, e.g. "3ayez a3raf"), Arabic mixed with English, abbreviations, and
very short or ungrammatical questions. Work out what they MEAN and answer it.
Never comment on their spelling, never reject a question for how it is written,
and never show your internal correction. Map informal wording onto the schema:
"ف افريقيا" / "afriqya" -> market_name LIKE '%Africa%'
"الايراد" / "مبيعات" / "فلوس" / "revenue" -> SUM(sales)
"اتأخر" / "متأخر" / "late" -> delivery_status_name LIKE '%Late delivery%'
"كام" / "عدد" / "how many" -> a COUNT (apply RULE 3 to pick DISTINCT)
Ask for clarification ONLY if the meaning is genuinely ambiguous (RULE 0) -
never because of spelling or grammar.

TEXT MATCHING: always use LIKE '%value%', never '='. Some stored values contain
stray spaces (e.g. 'Health and Beauty ', 'South of  USA ') so '=' silently fails.
Allowed values you can filter on:
market_name: Africa, Europe, LATAM, Pacific Asia, USCA
customer_segment_name: Consumer, Corporate, Home Office
shipping_mode_name: First Class, Same Day, Second Class, Standard Class
delivery_status_name: Advance shipping, Late delivery, Shipping canceled, Shipping on time
department_name: Apparel, Book Shop, Discs Shop, Fan Shop, Fitness, Footwear,
Golf, Health and Beauty, Outdoors, Pet Shop, Technology

1) vw_FactOrderItem (fact table - sales, profit, shipping):
order_item_id, order_id, product_id, customer_id, destination_id,
shipping_mode_id, order_status_id, delivery_status_id, order_type_id,
order_date, shipping_date, order_item_quantity, unit_price_at_sale,
discount_amount, discount_rate, sales, item_total, profit_ratio,
profit_amount, days_for_shipping_real, days_for_shipment_scheduled
Late delivery is defined ONLY as:
days_for_shipping_real > days_for_shipment_scheduled

2) vw_DimProduct (products):
product_id, product_name, product_price, product_status,
category_id, category_name, department_id, department_name
When grouping by category use category_id, not category_name
(the name "Electronics" is reused by two different categories).

3) vw_DimCustomer (customers):
customer_id, customer_fname, customer_lname, customer_email,
customer_segment_name, customer_address_id, street, city, state,
zipcode, country, latitude, longitude
customer_email is always XXXXXXXXX (masked in the view) - never present it.
country holds only two values (United States, Puerto Rico) and refers to the
customer's own home address, NOT the shipping destination. Use LIKE.
If asked about any other country using this column, the honest answer is zero.

4) vw_DimGeography (geography):
destination_id, order_city, order_state, order_zipcode,
region_name, market_name, order_country_name
order_country_name is in English. order_state is still in local spelling for
some countries (e.g. Andalucía) - use LIKE with % there.
order_zipcode may be NULL for some countries - that is normal.
order_country_name is the ORDER'S SHIPPING DESTINATION (164 countries), not the
customer's home address. For a general "customers in <country>" question, use
this column - not vw_DimCustomer.country.
market_name groups countries into markets (e.g. Africa, Europe, LATAM, Pacific
Asia, USCA) - use it for continent/region-level questions.

5) vw_DimShippingMode:
shipping_mode_id, shipping_mode_name

6) vw_DimOrderStatus (order + delivery status):
OrderStatusKey, order_status_name, delivery_status_name
It has no separate order_status_id / delivery_status_id - only one composite key.

7) vw_DimOrderType:
order_type_id, order_type_name

Confirmed relationships between the views:
vw_FactOrderItem.product_id       = vw_DimProduct.product_id
vw_FactOrderItem.customer_id      = vw_DimCustomer.customer_id
vw_FactOrderItem.destination_id   = vw_DimGeography.destination_id
vw_FactOrderItem.shipping_mode_id = vw_DimShippingMode.shipping_mode_id
vw_FactOrderItem.order_type_id    = vw_DimOrderType.order_type_id
(vw_FactOrderItem.order_status_id * 100) + vw_FactOrderItem.delivery_status_id
    = vw_DimOrderStatus.OrderStatusKey

NEVER INVENT A JOIN. The six pairs above are the ONLY valid join paths. Do not
join two columns just because both are integer IDs with similar-sounding names:
SQLite will happily match them and return a meaningless number instead of an
error, so a wrong join looks exactly like a correct answer.
Specifically: vw_DimCustomer has NO direct link to vw_DimGeography.
customer_address_id is NOT a foreign key to destination_id - joining those two
returns 31 instead of the correct 389 customers for Egypt. To relate a customer
to a shipping destination you MUST go through vw_FactOrderItem.
Every join must have vw_FactOrderItem on one side; the dimension views are never
joined directly to each other.

"""

# شكل الأدوات ده هو شكل OpenAI القياسي، و Gemini بيدعمه من خلال
# الـ OpenAI-compatible endpoint بنفس الطريقة بالظبط.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": "ينفذ كويري SQL من نوع SELECT فقط على الـ Views المسموحة، ويرجع بيانات حقيقية من قاعدة البيانات.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_query": {
                        "type": "string",
                        "description": "كويري SQL كامل يبدأ بـ SELECT ويستخدم أحد الـ 7 Views المسموحة",
                    }
                },
                "required": ["sql_query"],
            },
        },
    }
]


def _client() -> OpenAI:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "متغير البيئة GEMINI_API_KEY مش موجود. "
            "محلياً: حطه في .env أو صدّره في الـ shell. "
            "على Render: ضيفه في Environment Variables بتاعة الخدمة. "
            "تعمل مفتاح مجاني من: https://aistudio.google.com/apikey"
        )
    return OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)


def _log(question: str, sql_queries: list[str], answer: str) -> None:
    """سجل تدقيق (audit log): كل سؤال + الكويري اللي اتكتب + الإجابة.

    ده الدليل اللي بيثبت قدام لجنة المناقشة إن الأرقام حقيقية من
    القاعدة، مش نص مُختلَق من الموديل.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "sql_queries": sql_queries,
        "answer": answer,
    }
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # فشل تسجيل الـ log مايوقفش الإجابة نفسها


def _call_model(client: OpenAI, messages: list[dict]):
    """
    نداء واحد للموديل، مع إعادة محاولة تلقائية لو حصل tool_use_failed.

    ده عطل معروف (مش دايماً بيحصل) بيظهر أحياناً مع الموديلات دي:
    الموديل بيحاول يستخدم الأداة لكن بيكتب استدعاءها بصيغة غلط
    (زي <function=...></function> بدل JSON منظم)، فالخدمة بترفض الطلب
    بـ HTTP 400. غالباً إعادة المحاولة بتظبط من غير أي تدخل تاني.
    """
    last_error: BadRequestError | None = None
    for attempt in range(MAX_GENERATION_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=1024,
                tools=TOOLS,
                messages=messages,
            )
        except RateLimitError as e:
            # 429: تعدينا حد التوكنز في الدقيقة (12,000 في الخطة المجانية).
            # الخدمة بتبعت هيدر retry-after بعدد الثواني المطلوب استناها.
            # بنستنى مرة واحدة بس ولو الوقت قصير - عشان المستخدم ميقعدش
            # مستني الصفحة واقفة، ولو الوقت طويل بنرجع رسالة واضحة.
            wait = _retry_after_seconds(e)
            if attempt < MAX_GENERATION_RETRIES and wait is not None and wait <= 12:
                time.sleep(wait + 0.5)
                continue
            raise
        except BadRequestError as e:
            code = None
            if isinstance(e.body, dict):
                code = (e.body.get("error") or {}).get("code")
            if code == "tool_use_failed" and attempt < MAX_GENERATION_RETRIES:
                last_error = e
                continue
            raise
    raise last_error  # pragma: no cover - مايوصلش هنا عملياً


def _retry_after_seconds(e: RateLimitError) -> float | None:
    """بيقرأ عدد الثواني المطلوب استناها من هيدر retry-after لو موجود."""
    try:
        raw = e.response.headers.get("retry-after")
        return float(raw) if raw is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _humanize_seconds(seconds: float) -> str:
    """2720 ثانية رقم مالوش معنى للمستخدم - نحوله لـ '45 دقيقة'."""
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds} ثانية"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} دقيقة"
    hours, mins = divmod(minutes, 60)
    return f"{hours} ساعة و{mins} دقيقة" if mins else f"{hours} ساعة"


def _is_daily_limit(e: RateLimitError) -> bool:
    """
    الخدمة بترجع نفس الكود (429) للحدين: حد الدقيقة وحد اليوم.
    الفرق بينهم كبير جداً بالنسبة للمستخدم - واحد يعني "استنى دقيقة"
    والتاني يعني "خلص رصيدك النهاردة"، فلازم نفرق بينهم في الرسالة.
    """
    try:
        message = (e.body or {}).get("error", {}).get("message", "")
    except AttributeError:
        message = ""
    text = f"{message} {e}".lower()
    return "per day" in text or "tpd" in text


def _friendly_error(e: Exception) -> str:
    """
    بيحوّل أخطاء الـ API لرسالة مفهومة للمستخدم بدل ما يشوف JSON خام أو
    رسالة عامة مالهاش معنى. الرسالة بتقول للمستخدم يعمل إيه بالظبط.
    """
    if isinstance(e, RateLimitError):
        wait = _retry_after_seconds(e)
        when = f" جرب تاني بعد حوالي {_humanize_seconds(wait)}." if wait else ""
        if _is_daily_limit(e):
            return (
                "خلص الرصيد اليومي المجاني (1500 طلب في اليوم)."
                f"{when} الرصيد بيتجدد تلقائياً."
            )
        return (
            "فيه ضغط على الخدمة دلوقتي (تعدينا حد التوكنز في الدقيقة)."
            f"{when or ' استنى شوية وحاول تاني.'}"
        )
    if isinstance(e, AuthenticationError):
        return "فيه مشكلة في مفتاح الـ API. راجع GEMINI_API_KEY في ملف .env."
    if isinstance(e, APIConnectionError):
        return "مفيش اتصال بالخدمة دلوقتي. اتأكد من الإنترنت وحاول تاني."
    if isinstance(e, APIStatusError):
        return (
            f"الخدمة ردت بخطأ (كود {e.status_code}). "
            "جرب تاني بعد شوية، ولو فضلت تحصل ابعتلي الكود ده."
        )
    return "حصلت مشكلة غير متوقعة. جرب تاني بعد شوية."


# كمان بالإنجليزي لنفس سبب الـ system prompt - ده بيتبعت كرسالة إضافية
# في جولة المراجعة، فتوفير التوكنز هنا بيقلل ضغط الـ rate limit.
VERIFICATION_PROMPT = """
Before you confirm that as your final answer, re-check every SQL query you
wrote above:

1. If the question asks for a COUNT of entities (customers, orders, distinct
   products) - did you use COUNT(DISTINCT ...) on the right column, or did you
   wrongly use COUNT(*)? (COUNT(*) on vw_FactOrderItem returns the number of
   order lines, not customers and not orders.)
2. If the question asks for an AVERAGE at order level - did you compute
   SUM(...) / COUNT(DISTINCT order_id), or did you wrongly use AVG() directly?
3. Did you use the right view (customer home address vs shipping destination -
   these are two completely different columns)?
4. Is every JOIN one of the documented key pairs, with vw_FactOrderItem on one
   side? A join you invented between two dimension views returns a plausible but
   meaningless number - re-check this specifically.

If you find any mistake, call the tool again with a corrected query before
answering. If everything is genuinely correct, repeat the same answer unchanged.
"""


def _needs_verification(executed_queries: list[str]) -> bool:
    """
    المراجعة الذاتية بتكلف رحلة API كاملة (حوالي 2,500 توكن)، فبنطلبها
    بس لما يكون فيه سبب حقيقي للشك:

    - AVG( موجودة            -> شك (المفروض SUM/COUNT(DISTINCT order_id))
    - COUNT( من غير DISTINCT -> شك (ده بالظبط غلط COUNT(*) الشهير)
    - COUNT(DISTINCT ...) بس -> الموديل عمل الصح أصلاً، مفيش داعي نراجع

    قبل كده كنا بنراجع أي كويري فيه COUNT( حتى لو كان COUNT(DISTINCT
    صح من أول مرة - يعني كنا بندفع رحلة زيادة على فاضي في أغلب الأسئلة.
    """
    for query in executed_queries:
        upper = query.upper()
        if "AVG(" in upper:
            return True
        # نشيل الحالات الصح (COUNT(DISTINCT) الأول، ولو فضل أي COUNT( تاني
        # يبقى فيه COUNT(*) أو COUNT(col) محتاج مراجعة.
        without_distinct = upper.replace("COUNT(DISTINCT", "")
        if "COUNT(" in without_distinct:
            return True
    return False


def ask_agent(
    user_question: str, history: list[dict] | None = None
) -> tuple[str, list[str]]:
    """
    بيرجع (الإجابة النهائية، قائمة كويريات SQL اللي اتنفذت فعلياً) -
    القائمة دي المفروض تتعرض في الواجهة (زر "Show SQL") عشان أي حد
    (خصوصاً لجنة المناقشة) يقدر يتأكد بنفسه إن الرقم جه من قاعدة
    البيانات فعلاً، مش نص مُختلَق.

    history: قائمة أدوار سابقة بسيطة [{"role": "user"/"assistant", "content": "..."}]
    من نفس جلسة الشات، عشان أسئلة المتابعة زي "وإيه أعلى منتج فيهم؟" تفهم
    السياق. متعمداً بنمرر النص النهائي بس (مش تفاصيل الـ tool calls
    القديمة)، عشان السياق يفضل خفيف وميكبرش مع كل سؤال.

    مراجعة ذاتية: أول ما الموديل يوصل لإجابة نهائية، مش بنرجعها فوراً -
    بنبعتله طلب مراجعة (VERIFICATION_PROMPT) يتأكد فيه بنفسه من منطق
    COUNT/DISTINCT قبل التأكيد. لو لقى غلط، بيصحح الكويري ويجرب تاني.
    ده بيحصل مرة واحدة بس لكل سؤال (مش حلقة لا نهائية).
    """
    client = _client()
    # الـ system prompt بيتحط كرسالة عادية في أول القائمة.
    messages: list[dict] = [{"role": "system", "content": SCHEMA_DESCRIPTION}]
    # بناخد آخر كام رسالة بس من تاريخ المحادثة، مش التاريخ كله. من غير
    # الحد ده السياق بيكبر مع كل سؤال جديد لحد ما يعدي حد التوكنز في
    # الدقيقة (12,000) ويرجع 429 - وده اللي كان بيحصل فعلاً في السؤال
    # التاني أو التالت في نفس الجلسة.
    if history:
        messages.extend(history[-MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": user_question})
    executed_queries: list[str] = []
    verified = False

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            response = _call_model(client, messages)
        except BadRequestError as e:
            # فشلت كل المحاولات - نوري المستخدم رسالة مفهومة، مش JSON خام
            friendly = (
                "معلش، حصلت مشكلة مؤقتة في فهم السؤال ده. "
                "جرب تعيد صياغته بشكل أبسط، أو جرب تاني بعد شوية."
            )
            _log(user_question, executed_queries, f"[GENERATION_ERROR] {e}")
            return friendly, executed_queries
        except (RateLimitError, AuthenticationError, APIConnectionError,
                APIStatusError) as e:
            # أهم واحدة هنا هي RateLimitError (429): الخطة المجانية حدها
            # 12,000 توكن في الدقيقة، والسؤال الواحد بياخد 3-4 نداءات.
            # قبل كده الخطأ ده كان بيعدي من غير ما يتمسك وبيوصل للمستخدم
            # كرسالة عامة "Couldn't get an answer" مالهاش أي معنى.
            friendly = _friendly_error(e)
            _log(user_question, executed_queries, f"[API_ERROR] {type(e).__name__}: {e}")
            print(f"[agent] {type(e).__name__}: {e}")
            return friendly, executed_queries

        msg = response.choices[0].message

        if not msg.tool_calls:
            final_text = msg.content or ""

            if not verified and _needs_verification(executed_queries):
                # فيه COUNT( أو AVG( في الكويري - ده بالظبط النوع اللي
                # ممكن يغلط، فنبعته لمراجعة ذاتية مرة واحدة قبل التأكيد.
                verified = True
                messages.append({"role": "assistant", "content": final_text})
                messages.append({"role": "user", "content": VERIFICATION_PROMPT})
                continue

            _log(user_question, executed_queries, final_text)
            return final_text, executed_queries

        # الموديل طلب استخدام الأداة - ممكن أكتر من مرة في نفس الرد
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            }
        )

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            sql_query = args.get("sql_query", "")
            executed_queries.append(sql_query)

            tool_result = run_sql_query(sql_query)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                }
            )

    # لو الموديل فضل يطلب أدوات أكتر من MAX_TOOL_ROUNDS مرة - وقف الحلقة
    fallback = "معلش، السؤال ده معقد أكتر من اللازم واحتاج استعلامات كتير. جرب تبسّطه؟"
    _log(user_question, executed_queries, fallback)
    return fallback, executed_queries


if __name__ == "__main__":
    test_question = "كام عميل عندنا في مصر؟"
    answer, sql_queries = ask_agent(test_question)
    print("=== رد الموديل ===")
    print(answer)
    print("=== الكويريات اللي اتنفذت ===")
    for q in sql_queries:
        print(q)

# ---------------------------------------------------------------------
# ملاحظة عن التسمية: النظام ده NL-to-SQL Agent، مش RAG.
#
# RAG (Retrieval-Augmented Generation) معناه استرجاع دلالي (embeddings +
# vector search) من بيانات نصية غير منظمة قبل الرد. اللي بيحصل هنا
# مختلف: السكيما كاملة (7 Views ثابتين ومعروفين مقدماً) متكتوبة في
# system prompt، والموديل بيكتب SQL وينفذه مباشرة على بيانات منظمة.
# للسكيما الصغيرة والثابتة دي، الطريقة دي أدق من RAG حقيقي، مش أضعف منه.
# ---------------------------------------------------------------------
