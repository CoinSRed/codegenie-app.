# -*- coding: utf-8 -*-
"""
🧞 CodeGenie AI
تطبيق ويب عربي (RTL) يولّد أكواداً برمجية احترافية باستخدام Groq API
النموذج: llama-3.3-70b-versatile

التشغيل:
    export GROQ_API_KEY="gsk_..."
    python main.py
ثم افتح:  http://localhost:8000
"""

import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel


# ════════════════════════════════════════════════════════════
# 1) الإعدادات
# ════════════════════════════════════════════════════════════
def _load_env_file() -> None:
    """قراءة ملف .env (اختياري) الموجود بجانب main.py دون أي مكتبة إضافية."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.replace("export ", "").strip()
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_env_file()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4096"))
MAX_PROMPT_CHARS = 4000


# ════════════════════════════════════════════════════════════
# 2) الـ System Prompts المتخصصة لكل لغة
# ════════════════════════════════════════════════════════════
BASE_RULES = (
    "\n\nقواعد إلزامية يجب الالتزام بها دائماً:\n"
    "1. اكتب جميع التعليقات داخل الكود باللغة العربية (واضحة ومختصرة)، "
    "وأبقِ أسماء المتغيرات والدوال بالإنجليزية.\n"
    "2. أعد الكود كاملاً وجاهزاً للتشغيل مباشرة، دون استخدام \"...\" أو TODO "
    "أو أجزاء ناقصة أو أمثلة مبتورة.\n"
    "3. أعد الكود فقط داخل كتلة كود واحدة بصيغة Markdown (```اسم_اللغة)، "
    "بدون أي شرح أو مقدمة أو خاتمة قبل الكتلة أو بعدها. "
    "ضع كل الشرح اللازم داخل التعليقات العربية.\n"
    "4. اتبع أفضل الممارسات: كود نظيف، أسماء واضحة، معالجة الأخطاء، وأمان.\n"
    "5. إن كان الطلب غامضاً فاختر أبسط تفسير معقول ونفّذه كاملاً.\n"
    "6. إن كان الطلب غير برمجي إطلاقاً، فاكتب كوداً بسيطاً يخدم أقرب فكرة برمجية له "
    "مع تعليق عربي في أوله يوضح ذلك."
)

LANGUAGES = {
    "lua": {
        "label": "Lua (Roblox Studio)",
        "fence": "lua",
        "system": (
            "أنت خبير محترف في Roblox Studio ولغة Luau/Lua. "
            "تكتب سكربتات جاهزة للصق داخل Roblox Studio مباشرة. "
            "في أول الكود بتعليق عربي، حدّد نوع السكربت (Script أو LocalScript أو ModuleScript) "
            "ومكان وضعه الصحيح (مثل ServerScriptService أو StarterPlayerScripts أو StarterGui أو داخل Part). "
            "استخدم task.wait و task.spawn بدل wait و spawn القديمتين، "
            "واستخدم game:GetService(...) للخدمات، "
            "والـ RemoteEvent/RemoteFunction للتواصل بين السيرفر والعميل مع التحقق من المدخلات على السيرفر. "
            "تجنّب الثقة بالعميل، وراعِ الأداء وتنظيف الاتصالات (Disconnect) عند الحاجة."
            + BASE_RULES
        ),
    },
    "python": {
        "label": "Python",
        "fence": "python",
        "system": (
            "أنت خبير Python (الإصدار 3.10 فما فوق). "
            "اكتب كوداً نظيفاً يتبع PEP 8 مع Type Hints عند الفائدة، "
            "واستخدم المكتبة القياسية قدر الإمكان، وإن احتجت مكتبة خارجية فاذكر أمر تثبيتها في تعليق عربي في أول الكود. "
            "ضع نقطة الدخول داخل if __name__ == \"__main__\": وعالج الاستثناءات بشكل مناسب."
            + BASE_RULES
        ),
    },
    "javascript": {
        "label": "JavaScript",
        "fence": "javascript",
        "system": (
            "أنت خبير JavaScript الحديثة (ES2022+). "
            "استخدم const/let وarrow functions وasync/await والـ modules عند الحاجة، "
            "وعالج الأخطاء بـ try/catch. "
            "إن كان الطلب للمتصفح فاكتب كوداً يعمل مباشرة في المتصفح، "
            "وإن كان لـ Node.js فاذكر ذلك في تعليق عربي في أول الكود وكيفية تشغيله."
            + BASE_RULES
        ),
    },
    "html": {
        "label": "HTML/CSS",
        "fence": "html",
        "system": (
            "أنت خبير واجهات ويب (HTML5 وCSS3 وJavaScript الخفيف). "
            "اكتب صفحة واحدة كاملة في ملف HTML واحد تحتوي <style> و<script> داخلياً، "
            "متجاوبة مع الجوال (meta viewport + Flexbox/Grid)، "
            "وبتصميم عصري أنيق، وبعناصر HTML دلالية (semantic) وسهلة الوصول (accessibility). "
            "إن كان المحتوى عربياً فاستخدم lang=\"ar\" وdir=\"rtl\". "
            "لا تعتمد على مكتبات خارجية إلا إذا طُلب ذلك صراحة."
            + BASE_RULES
        ),
    },
    "flutter": {
        "label": "Flutter (Dart)",
        "fence": "dart",
        "system": (
            "أنت خبير Flutter وDart (Null Safety وMaterial 3). "
            "اكتب ملف main.dart واحداً كاملاً يعمل مباشرة بعد لصقه في مشروع Flutter جديد، "
            "مع استخدام StatelessWidget/StatefulWidget بشكل صحيح، وconst constructors عند الإمكان، "
            "وفصل الواجهة إلى Widgets صغيرة مقروءة. "
            "إن احتجت حزمة خارجية فاذكر سطرها المطلوب في pubspec.yaml في تعليق عربي في أول الكود."
            + BASE_RULES
        ),
    },
    "csharp": {
        "label": "C#",
        "fence": "csharp",
        "system": (
            "أنت خبير C# و.NET الحديث (النسخة 8 فما فوق). "
            "اكتب كوداً نظيفاً يتبع اصطلاحات التسمية في C#، ويستخدم async/await وLINQ عند الحاجة، "
            "ومعالجة الاستثناءات. "
            "إن ذكر المستخدم Unity فاكتب سكربت MonoBehaviour صحيحاً مع [SerializeField] "
            "وذكر اسم الكائن الذي يوضع عليه السكربت في تعليق عربي؛ "
            "وإلا فاكتب برنامج Console كاملاً (ملف Program.cs) يعمل مباشرة."
            + BASE_RULES
        ),
    },
}


# ════════════════════════════════════════════════════════════
# 3) تطبيق FastAPI
# ════════════════════════════════════════════════════════════
class ApiError(Exception):
    """خطأ مخصص يحمل رمز الحالة ورسالة عربية واضحة للمستخدم."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@asynccontextmanager
async def lifespan(app: FastAPI):
    # عميل HTTP واحد مشترك طوال عمر التطبيق (كل شيء في الذاكرة)
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(75.0, connect=10.0)
    )
    if not os.environ.get("GROQ_API_KEY", "").strip():
        print("⚠️  تحذير: المتغير GROQ_API_KEY غير مضبوط. التوليد لن يعمل قبل ضبطه.")
    yield
    await app.state.client.aclose()


app = FastAPI(title="CodeGenie AI", lifespan=lifespan)


class GenerateRequest(BaseModel):
    prompt: str
    language: str


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "الطلب غير صالح. تأكد من كتابة وصف واضح واختيار لغة البرمجة."},
    )


def extract_code(text: str) -> str:
    """استخراج الكود من كتل Markdown (```) وإزالة أي كلام خارجها."""
    text = text.strip()
    blocks = re.findall(r"```[^\n`]*\n(.*?)```", text, flags=re.DOTALL)
    if blocks:
        return "\n\n".join(b.strip("\n") for b in blocks).strip()
    # حالة كتلة غير مغلقة (رد مقطوع)
    unclosed = re.match(r"^```[^\n`]*\n(.*)$", text, flags=re.DOTALL)
    if unclosed:
        return unclosed.group(1).strip()
    return text


def explain_groq_error(status: int, detail: str) -> ApiError:
    """تحويل أخطاء Groq إلى رسائل عربية مفهومة."""
    if status == 401:
        return ApiError(401, "مفتاح GROQ_API_KEY غير صحيح أو منتهي. أنشئ مفتاحاً جديداً من console.groq.com/keys.")
    if status == 403:
        return ApiError(403, "تم رفض الوصول من Groq. تحقق من صلاحيات المفتاح أو من قيود منطقتك.")
    if status == 404:
        return ApiError(502, "النموذج المطلوب غير متاح حالياً لدى Groq. جرّب ضبط GROQ_MODEL بنموذج آخر.")
    if status == 413:
        return ApiError(413, "الطلب كبير جداً. اختصر الوصف وحاول مرة أخرى.")
    if status == 429:
        return ApiError(429, "تجاوزت الحد المجاني للطلبات. انتظر دقيقة ثم حاول مجدداً.")
    if status >= 500:
        return ApiError(503, "خدمة Groq مشغولة أو متوقفة مؤقتاً. حاول بعد قليل.")
    return ApiError(502, "رفضت Groq الطلب: " + (detail or "خطأ غير معروف") + ".")


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(HTML_PAGE)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model": GROQ_MODEL,
        "api_key_configured": bool(os.environ.get("GROQ_API_KEY", "").strip()),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest, request: Request):
    prompt = req.prompt.strip()
    if len(prompt) < 3:
        raise ApiError(422, "اكتب وصفاً أوضح لما تريد برمجته (3 أحرف على الأقل).")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ApiError(422, f"الوصف طويل جداً. الحد الأقصى {MAX_PROMPT_CHARS} حرف.")

    lang = LANGUAGES.get(req.language)
    if lang is None:
        raise ApiError(400, "لغة البرمجة المختارة غير مدعومة.")

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ApiError(
            500,
            "لم يتم ضبط المتغير GROQ_API_KEY على الخادم. أضفه ثم أعد تشغيل التطبيق (راجع README.md).",
        )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": lang["system"]},
            {
                "role": "user",
                "content": (
                    f"اللغة المطلوبة: {lang['label']}\n"
                    f"المطلوب برمجته:\n{prompt}"
                ),
            },
        ],
        "temperature": 0.3,
        "max_tokens": MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "CodeGenie-AI/1.0",
    }

    try:
        resp = await request.app.state.client.post(GROQ_URL, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise ApiError(504, "انتهت مهلة الاتصال بـ Groq. حاول مرة أخرى أو اختصر طلبك.")
    except httpx.HTTPError:
        raise ApiError(502, "تعذّر الاتصال بخدمة Groq. تحقق من اتصال الإنترنت لديك.")

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except Exception:
            pass
        print(f"[Groq {resp.status_code}] {detail}")
        raise explain_groq_error(resp.status_code, detail)

    try:
        data = resp.json()
        choice = data["choices"][0]
        content = (choice["message"]["content"] or "").strip()
        finish = choice.get("finish_reason")
    except Exception:
        raise ApiError(502, "وصل رد غير متوقع من Groq. حاول مرة أخرى.")

    if not content:
        raise ApiError(502, "لم يُرجع النموذج أي كود. أعد المحاولة بوصف مختلف.")

    return {
        "code": extract_code(content),
        "language": req.language,
        "label": lang["label"],
        "truncated": finish == "length",
    }


# ════════════════════════════════════════════════════════════
# 4) الواجهة الأمامية (HTML/CSS/JS) داخل نفس الملف
# ════════════════════════════════════════════════════════════
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1117">
<title>CodeGenie AI — مولّد الأكواد الذكي</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  /* ===== المتغيرات والألوان ===== */
  :root{
    --bg:#0d1117; --card:#161b22; --card2:#0b0f14; --border:#30363d;
    --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff; --accent-h:#79b8ff;
    --danger:#f85149; --ok:#3fb950; --radius:16px;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;padding:0}
  body{
    background:var(--bg); color:var(--text);
    font-family:'Cairo',system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif;
    line-height:1.7; min-height:100vh;
    padding-bottom:env(safe-area-inset-bottom);
  }

  /* ===== الهيدر ===== */
  .hero{text-align:center;padding:28px 16px 8px}
  .hero h1{
    margin:0; font-size:clamp(28px,7vw,40px); font-weight:700; color:var(--accent);
    letter-spacing:.3px;
  }
  .hero p{margin:6px 0 0;color:var(--muted);font-size:15px}

  .wrap{max-width:900px;margin:0 auto;padding:16px}

  /* ===== البطاقات ===== */
  .card{
    background:var(--card); border:1px solid var(--border);
    border-radius:var(--radius); padding:18px; margin-bottom:16px;
    box-shadow:0 8px 24px rgba(0,0,0,.25);
  }
  label{display:block;font-weight:600;margin:0 0 8px;font-size:15px}

  textarea,select{
    width:100%; background:var(--card2); color:var(--text);
    border:1px solid var(--border); border-radius:12px;
    font-family:inherit; font-size:16px; padding:12px 14px; outline:none;
    transition:border-color .2s, box-shadow .2s;
  }
  textarea{min-height:150px;resize:vertical;line-height:1.7}
  textarea:focus,select:focus{
    border-color:var(--accent); box-shadow:0 0 0 3px rgba(88,166,255,.18);
  }
  select{
    appearance:none; -webkit-appearance:none; cursor:pointer; padding-left:40px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8'><path d='M1 1l5 5 5-5' stroke='%2358a6ff' stroke-width='2' fill='none' stroke-linecap='round'/></svg>");
    background-repeat:no-repeat; background-position:left 14px center;
  }
  .meta{display:flex;justify-content:flex-start;color:var(--muted);font-size:12px;margin:4px 2px 14px}

  /* ===== أمثلة سريعة ===== */
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
  .chip{
    background:transparent; color:var(--muted); border:1px solid var(--border);
    border-radius:999px; padding:6px 12px; font-family:inherit; font-size:13px;
    cursor:pointer; transition:all .15s;
  }
  .chip:hover{color:var(--accent);border-color:var(--accent)}
  .chip:active{transform:scale(.97)}

  /* ===== الأزرار ===== */
  .actions{display:flex;gap:12px;margin-top:16px}
  .btn{
    flex:1; min-height:52px; border-radius:12px; border:1px solid transparent;
    font-family:inherit; font-size:17px; font-weight:700; cursor:pointer;
    padding:10px 16px; transition:transform .1s, background .2s, opacity .2s, border-color .2s;
    touch-action:manipulation;
  }
  .btn:active:not(:disabled){transform:scale(.975)}
  .btn:disabled{opacity:.55;cursor:not-allowed}
  .btn.primary{background:var(--accent);color:#0d1117;flex:2}
  .btn.primary:hover:not(:disabled){background:var(--accent-h)}
  .btn.danger{background:transparent;color:var(--danger);border-color:rgba(248,81,73,.5)}
  .btn.danger:hover:not(:disabled){background:rgba(248,81,73,.1)}
  .btn.secondary{
    width:100%; margin-top:14px; background:transparent; color:var(--accent);
    border-color:var(--accent);
  }
  .btn.secondary:hover:not(:disabled){background:rgba(88,166,255,.1)}
  .btn.copied{color:var(--ok)!important;border-color:var(--ok)!important}

  /* ===== التنبيهات ===== */
  .alert{
    display:flex; gap:10px; align-items:flex-start;
    background:rgba(248,81,73,.1); border:1px solid rgba(248,81,73,.45);
    color:#ffa198; border-radius:12px; padding:12px 14px; margin-bottom:16px; font-size:15px;
  }
  .alert[hidden]{display:none}
  .alert.warn{background:rgba(210,153,34,.1);border-color:rgba(210,153,34,.5);color:#e3b341}

  /* ===== منطقة الكود ===== */
  .out-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-weight:600}
  .badge{
    background:rgba(88,166,255,.12); color:var(--accent); border:1px solid rgba(88,166,255,.35);
    border-radius:999px; padding:2px 12px; font-size:12px; font-weight:600;
  }
  .badge:empty{display:none}
  .empty{
    text-align:center; color:var(--muted); padding:42px 12px;
    border:1px dashed var(--border); border-radius:12px; background:var(--card2);
  }
  .empty.thinking{color:var(--accent);animation:pulse 1.2s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:.55}50%{opacity:1}}
  pre{
    margin:0; background:var(--card2); border:1px solid var(--border);
    border-radius:12px; padding:14px; overflow:auto; max-height:70vh;
    direction:ltr; text-align:left; -webkit-overflow-scrolling:touch;
  }
  pre[hidden]{display:none}
  code{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace;
    font-size:13.5px; line-height:1.65; white-space:pre; tab-size:4; color:#e6edf3;
  }
  /* تلوين بسيط */
  .t-c{color:#8b949e;font-style:italic}
  .t-s{color:#a5d6ff}
  .t-n{color:#79c0ff}
  .t-k{color:#ff7b72}

  /* ===== إشعار النسخ ===== */
  .toast{
    position:fixed; bottom:calc(24px + env(safe-area-inset-bottom)); left:50%;
    transform:translateX(-50%) translateY(20px); background:#238636; color:#fff;
    padding:10px 22px; border-radius:999px; font-weight:600; opacity:0;
    pointer-events:none; transition:all .25s; z-index:50; font-size:15px;
  }
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  .toast.bad{background:#da3633}

  footer{text-align:center;color:var(--muted);font-size:13px;padding:6px 16px 28px}

  @media (max-width:520px){
    .wrap{padding:12px}
    .card{padding:14px}
    .btn{font-size:16px}
  }
</style>
</head>
<body>

<header class="hero">
  <h1>🧞 CodeGenie AI</h1>
  <p>اكتب فكرتك بالعربي، وسيكتب لك الجني الكود جاهزاً ✨</p>
</header>

<main class="wrap">

  <!-- بطاقة الإدخال -->
  <section class="card">
    <label for="prompt">📝 صف ما تريد برمجته</label>
    <textarea id="prompt" maxlength="4000"
      placeholder="مثال: اكتب سكربت باب يفتح ويغلق عندما يلمسه اللاعب..."></textarea>
    <div class="meta"><span id="counter">0 / 4000</span></div>

    <label for="lang">💻 لغة البرمجة</label>
    <select id="lang">
      <option value="lua">Lua (Roblox)</option>
      <option value="python">Python</option>
      <option value="javascript">JavaScript</option>
      <option value="html">HTML/CSS</option>
      <option value="flutter">Flutter</option>
      <option value="csharp">C#</option>
    </select>

    <div class="chips" id="chips" aria-label="أمثلة سريعة"></div>

    <div class="actions">
      <button id="btnGen" class="btn primary" type="button">✨ ولّد الكود</button>
      <button id="btnClear" class="btn danger" type="button">🔄 مسح</button>
    </div>
  </section>

  <!-- رسائل الخطأ -->
  <div id="error" class="alert" role="alert" hidden></div>

  <!-- بطاقة الناتج -->
  <section class="card">
    <div class="out-head">
      <span>📄 الكود الناتج</span>
      <span id="badge" class="badge"></span>
    </div>
    <div id="empty" class="empty">سيظهر الكود هنا بعد التوليد ✨</div>
    <pre id="codeBox" hidden><code id="code"></code></pre>
    <button id="btnCopy" class="btn secondary" type="button" disabled>📋 نسخ الكود</button>
  </section>

</main>

<footer>صُنع بـ ❤️ — يعمل بنموذج Llama 3.3 70B عبر Groq</footer>
<div id="toast" class="toast" role="status"></div>

<script>
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var currentCode = "";   // الكود الحالي في الذاكرة
  var busy = false;

  /* ---------- أمثلة سريعة لكل لغة ---------- */
  var EXAMPLES = {
    lua: ["باب يفتح ويغلق عند لمسه", "نظام عملات يزيد عند لمس القطع ويظهر في leaderstats", "زر GUI يعطي اللاعب سرعة مؤقتة"],
    python: ["برنامج يقرأ ملف CSV ويحسب المتوسط", "لعبة تخمين الرقم في الطرفية", "سكربت يحمّل صفحة ويستخرج كل الروابط"],
    javascript: ["دالة debounce مع مثال استخدام", "قائمة مهام تحفظ في localStorage", "جلب بيانات من API وعرضها في جدول"],
    html: ["صفحة هبوط لمطعم متجاوبة مع الجوال", "نموذج تسجيل دخول أنيق", "بطاقة بروفايل بتأثيرات hover"],
    flutter: ["شاشة تسجيل دخول بتصميم Material 3", "قائمة مهام مع إضافة وحذف", "عدّاد بسيط بإدارة حالة"],
    csharp: ["فئة حساب بنكي مع إيداع وسحب", "برنامج طرفية لإدارة قائمة مهام", "سكربت Unity لحركة لاعب"]
  };

  /* ---------- تلوين الكود البسيط ---------- */
  var STR = /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/.source;
  var STR_BT = STR + "|" + /`(?:\\[\s\S]|[^`\\])*`/.source;
  var STR_PY = /"{3}[\s\S]*?"{3}|'{3}[\s\S]*?'{3}/.source + "|" + STR;
  var CMT_SLASH = /\/\/[^\n]*|\/\*[\s\S]*?\*\//.source;
  var CMT_LUA = /--\[\[[\s\S]*?\]\]|--[^\n]*/.source;
  var CMT_HASH = /#[^\n]*/.source;
  var CMT_HTML = /<!--[\s\S]*?-->|\/\*[\s\S]*?\*\//.source;
  var NUM = "\\b\\d+(?:\\.\\d+)?\\b";
  function kw(list) { return "\\b(?:" + list.split(" ").join("|") + ")\\b"; }
  function build(cmt, str, keys) {
    return "(" + cmt + ")|(" + str + ")|(" + NUM + ")|(" + keys + ")";
  }

  var SYNTAX = {
    lua: build(CMT_LUA, STR,
      kw("and break do else elseif end false for function goto if in local nil not or repeat return then true until while continue self game workspace script")),
    python: build(CMT_HASH, STR_PY,
      kw("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield self print")),
    javascript: build(CMT_SLASH, STR_BT,
      kw("const let var function return if else for while do switch case break continue new this class extends import export from async await try catch finally throw typeof instanceof true false null undefined default of in")),
    html: build(CMT_HTML, STR,
      "<\\/?[a-zA-Z][\\w-]*|\\/?>|" + kw("function const let var return if else for while document window")),
    flutter: build(CMT_SLASH, STR,
      kw("abstract as async await break case catch class const continue default do else enum extends final finally for if import in is late new null override required return static super switch this throw true false try var void while with yield int String bool double List Map Widget BuildContext State")),
    csharp: build(CMT_SLASH, STR,
      kw("using namespace class public private protected internal static void int string bool float double var new return if else for foreach while switch case break continue null true false this base override virtual abstract interface struct enum async await try catch finally throw readonly const"))
  };

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(code, lang) {
    var src = SYNTAX[lang];
    if (!src) { return esc(code); }
    var rx = new RegExp(src, "g");
    var out = "", last = 0, m;
    while ((m = rx.exec(code)) !== null) {
      if (m[0].length === 0) { rx.lastIndex++; continue; }
      var cls = m[1] !== undefined ? "c" : m[2] !== undefined ? "s" : m[3] !== undefined ? "n" : "k";
      out += esc(code.slice(last, m.index)) + '<span class="t-' + cls + '">' + esc(m[0]) + "</span>";
      last = m.index + m[0].length;
    }
    return out + esc(code.slice(last));
  }

  /* ---------- أدوات الواجهة ---------- */
  function showError(msg, warn) {
    var box = $("error");
    box.className = "alert" + (warn ? " warn" : "");
    box.textContent = (warn ? "⚠️ " : "❌ ") + msg;
    box.hidden = false;
  }
  function hideError() { $("error").hidden = true; }

  var toastTimer = null;
  function toast(msg, bad) {
    var t = $("toast");
    t.textContent = msg;
    t.className = "toast show" + (bad ? " bad" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.className = "toast" + (bad ? " bad" : ""); }, 1800);
  }

  function setLoading(on) {
    busy = on;
    var btn = $("btnGen");
    btn.disabled = on;
    $("btnClear").disabled = on;
    btn.textContent = on ? "⏳ يفكر..." : "✨ ولّد الكود";
    if (on) {
      $("codeBox").hidden = true;
      $("empty").hidden = false;
      $("empty").className = "empty thinking";
      $("empty").textContent = "⏳ يفكر... قد يستغرق الأمر بضع ثوانٍ";
      $("btnCopy").disabled = true;
    }
  }

  function renderCode(lang, label) {
    if (!currentCode) {
      $("codeBox").hidden = true;
      $("empty").hidden = false;
      $("empty").className = "empty";
      $("empty").textContent = "سيظهر الكود هنا بعد التوليد ✨";
      $("btnCopy").disabled = true;
      $("badge").textContent = "";
      return;
    }
    $("code").innerHTML = highlight(currentCode, lang);
    $("codeBox").hidden = false;
    $("empty").hidden = true;
    $("btnCopy").disabled = false;
    var lines = currentCode.split("\n").length;
    $("badge").textContent = (label || "") + " • " + lines + " سطر";
  }

  function renderChips() {
    var lang = $("lang").value;
    var box = $("chips");
    box.innerHTML = "";
    (EXAMPLES[lang] || []).forEach(function (txt) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = txt;
      b.addEventListener("click", function () {
        $("prompt").value = txt;
        updateCounter();
        $("prompt").focus();
      });
      box.appendChild(b);
    });
  }

  function updateCounter() {
    $("counter").textContent = $("prompt").value.length + " / 4000";
  }

  /* ---------- نسخ الكود (يعمل على الجوال) ---------- */
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;font-size:16px;";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  async function copyCode() {
    if (!currentCode) { return; }
    var ok = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(currentCode);
        ok = true;
      }
    } catch (e) { ok = false; }
    if (!ok) { ok = fallbackCopy(currentCode); }

    var btn = $("btnCopy");
    if (ok) {
      toast("✅ تم نسخ الكود");
      btn.classList.add("copied");
      btn.textContent = "✅ تم النسخ";
      setTimeout(function () {
        btn.classList.remove("copied");
        btn.textContent = "📋 نسخ الكود";
      }, 1600);
    } else {
      toast("تعذّر النسخ تلقائياً. حدّد الكود وانسخه يدوياً.", true);
    }
  }

  /* ---------- طلب التوليد ---------- */
  async function generate() {
    if (busy) { return; }
    var prompt = $("prompt").value.trim();
    var language = $("lang").value;

    if (prompt.length < 3) {
      showError("اكتب وصفاً أوضح لما تريد برمجته أولاً.");
      $("prompt").focus();
      return;
    }

    hideError();
    setLoading(true);
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, 90000);

    try {
      var res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt, language: language }),
        signal: ctrl.signal
      });
      var data = null;
      try { data = await res.json(); } catch (e) { data = null; }

      if (!res.ok) {
        currentCode = "";
        renderCode(language, "");
        showError((data && data.error) || ("حدث خطأ غير متوقع (الرمز " + res.status + ")."));
        return;
      }

      currentCode = data.code || "";
      renderCode(data.language || language, data.label || "");
      if (data.truncated) {
        showError("الرد طويل وتم قطعه. اطلب الكود على أجزاء أصغر للحصول على نتيجة كاملة.", true);
      }
    } catch (e) {
      currentCode = "";
      renderCode(language, "");
      if (e && e.name === "AbortError") {
        showError("انتهت مهلة الانتظار. حاول مرة أخرى بوصف أقصر.");
      } else {
        showError("تعذّر الاتصال بالخادم. تأكد من اتصالك بالإنترنت وأن التطبيق يعمل.");
      }
    } finally {
      clearTimeout(timer);
      setLoading(false);
      if (!currentCode) { renderCode(language, ""); }
    }
  }

  /* ---------- مسح ---------- */
  function clearAll() {
    $("prompt").value = "";
    currentCode = "";
    updateCounter();
    hideError();
    renderCode($("lang").value, "");
    $("prompt").focus();
  }

  /* ---------- ربط الأحداث ---------- */
  $("btnGen").addEventListener("click", generate);
  $("btnClear").addEventListener("click", clearAll);
  $("btnCopy").addEventListener("click", copyCode);
  $("prompt").addEventListener("input", updateCounter);
  $("lang").addEventListener("change", renderChips);
  $("prompt").addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); generate(); }
  });

  renderChips();
  updateCounter();
})();
</script>
</body>
</html>
"""


# ════════════════════════════════════════════════════════════
# 5) نقطة التشغيل
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"🧞 CodeGenie AI يعمل الآن على: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
