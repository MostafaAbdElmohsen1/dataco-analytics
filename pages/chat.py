"""
pages/chat.py - Ask the Data.

الواجهة الثابتة (العناوين، الأزرار، الاقتراحات) بالإنجليزي عشان تتسق مع
باقي صفحات الموقع (Home, Executive, Network...). المحادثة نفسها (سؤال
المستخدم ورد الموديل) ثنائية اللغة - بتتجاوب بنفس لغة السؤال (عربي أو
إنجليزي)، لأن ده أصل فكرة الأداة.

كل رد هنا رقم حقيقي جه من dataco.db عن طريق أحد الـ 7 Views المسموحة،
مش نص اتولّد من الموديل. زر "Show SQL" تحت كل رد بيوري الكويري الفعلي
اللي اتنفذ - ده بديل الملاحظة العامة اللي كانت تحت الصفحة قبل كده،
وبيدي دليل لكل إجابة لوحدها بدل جملة عامة محدش بيقراها.

الذاكرة: كل تاريخ المحادثة متخزن في dcc.Store (جوه المتصفح بس، مش على
السيرفر) عشان أسئلة المتابعة تفهم السياق، وبيتصفر لما تعمل refresh
للصفحة.
"""

from __future__ import annotations

import traceback

import dash
from dash import dcc, html, Input, Output, State, callback

import theme as T
from agent import ask_agent

dash.register_page(__name__, path="/chat", name="Ask the data")

SUGGESTIONS = [
    "How many customers do we have in Egypt?",
    "What are the top 5 best-selling products?",
    "What's our late delivery rate?",
    "Which country generates the most profit?",
]


def _sql_disclosure(sql_queries: list[str]):
    """
    عنصر <details>/<summary> أصلي في المتصفح - بيدي زر "Show SQL"
    قابل للطي من غير ما نحتاج أي callback إضافي أو JavaScript.
    """
    if not sql_queries:
        return None
    return html.Details(
        className="sql-disclosure",
        children=[
            html.Summary("Show SQL", className="sql-toggle"),
            html.Div(
                className="sql-block",
                children=[
                    html.Pre(html.Code(q)) for q in sql_queries
                ],
            ),
        ],
    )


def _bubble(role: str, text: str, sql_queries: list[str] | None = None):
    is_user = role == "user"
    children = [
        html.Div("You" if is_user else "Data Assistant", className="chat-bubble-role"),
        html.Div(text, className="chat-bubble-text"),
    ]
    disclosure = _sql_disclosure(sql_queries) if not is_user else None
    if disclosure is not None:
        children.append(disclosure)

    return html.Div(
        className="chat-bubble chat-bubble-user" if is_user else "chat-bubble chat-bubble-bot",
        children=children,
    )


layout = html.Div(
    className="page",
    children=[
        T.page_head(
            "Ask the Data",
            "Ask a question about your business data in Arabic or English. "
            "The assistant writes and runs a real SQL query against the "
            "database and answers with actual numbers - not a guess.",
        ),
        dcc.Store(id="chat-history", data=[]),  # [{"role":..,"content":..}, ...]
        html.Div(
            className="panel panel-wide chat-panel",
            children=[
                dcc.Loading(
                    type="dot",
                    color=T.M1,
                    # اللف هنا حوالين chat-log نفسه (مش عنصر فاضي منفصل) -
                    # عشان Dash يعرف يورّي مؤشر التحميل طول ما الـ callback
                    # اللي بيغيّر محتوى chat-log لسه شغال.
                    children=html.Div(id="chat-log", className="chat-log", children=[
                        html.Div(
                            className="chat-empty",
                            children=[
                                "Start with a question, or try one of these:",
                                html.Div(
                                    className="chat-suggestions",
                                    children=[
                                        html.Button(s, id={"type": "chat-suggest", "index": i},
                                                    className="chat-suggest-btn", n_clicks=0)
                                        for i, s in enumerate(SUGGESTIONS)
                                    ],
                                ),
                            ],
                        )
                    ]),
                ),
                html.Div(
                    className="chat-input-row",
                    children=[
                        dcc.Input(
                            id="chat-input",
                            type="text",
                            placeholder="Ask a question about your data...",
                            className="chat-input",
                            debounce=False,
                            n_submit=0,
                        ),
                        html.Button("Send", id="chat-send", className="chat-send-btn", n_clicks=0),
                    ],
                ),
            ],
        ),
    ],
)


@callback(
    Output("chat-log", "children"),
    Output("chat-history", "data"),
    Output("chat-input", "value"),
    Input("chat-send", "n_clicks"),
    Input("chat-input", "n_submit"),
    Input({"type": "chat-suggest", "index": dash.ALL}, "n_clicks"),
    State("chat-input", "value"),
    State("chat-history", "data"),
    State("chat-log", "children"),
    prevent_initial_call=True,
)
def send_message(_send_clicks, _enter, _suggest_clicks, typed_value, history, current_log):
    trig = dash.ctx.triggered_id
    question = typed_value

    if isinstance(trig, dict) and trig.get("type") == "chat-suggest":
        question = SUGGESTIONS[trig["index"]]

    if not question or not question.strip():
        return dash.no_update, dash.no_update, dash.no_update

    question = question.strip()
    history = history or []
    sql_queries: list[str] = []

    try:
        answer, sql_queries = ask_agent(question, history=history)
    except RuntimeError as e:
        # مشكلة إعدادات (زي مفتاح API ناقص) - التفاصيل التقنية تروح للـ
        # terminal/الـ logs بس، مش لواجهة المستخدم.
        print(f"[chat] config error: {e}")
        answer = "The service isn't ready right now - there's a server configuration issue. Contact the developer."
    except Exception as e:  # noqa: BLE001 - عايزين الصفحة متوقعش، بس التفاصيل في الـ log بس
        # traceback كامل في الـ terminal - من غيره أي خطأ جديد بيبقى
        # مستحيل تشخيصه، لأن المستخدم بيشوف رسالة عامة بس.
        traceback.print_exc()
        print(f"[chat] unexpected error: {e!r}")
        answer = (
            "معلش، حصلت مشكلة غير متوقعة. جرب تاني بعد شوية - "
            "ولو فضلت تحصل، شوف التفاصيل في نافذة الـ terminal."
        )

    new_history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]

    log = current_log if isinstance(current_log, list) else []
    # أول رسالة بتشيل بلوك الاقتراحات (chat-empty) - نشيله لما أول سؤال يتبعت
    log = [b for b in log if not (isinstance(b, dict) and
           b.get("props", {}).get("className") == "chat-empty")]

    log = log + [_bubble("user", question), _bubble("assistant", answer, sql_queries)]

    return log, new_history, ""
