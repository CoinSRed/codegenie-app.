# 🧞 CodeGenie AI

تطبيق ويب عربي (RTL) يولّد أكواداً برمجية احترافية باستخدام نموذج **Llama 3.3 70B** عبر **Groq API** المجاني.

- **Backend:** Python + FastAPI + Uvicorn
- **Frontend:** HTML/CSS/JS داخل نفس الملف `main.py`
- **بدون قواعد بيانات** — كل شيء في الذاكرة

## 📁 ملفات المشروع

```
main.py             ← التطبيق كاملاً (Backend + Frontend)
requirements.txt    ← المكتبات المطلوبة
README.md           ← هذا الملف
```

---

## 🔑 1) الحصول على GROQ_API_KEY (مجاناً)

1. افتح: **https://console.groq.com/keys**
2. سجّل دخولك بحساب Google أو GitHub (أو أنشئ حساباً بالبريد).
3. اضغط **Create API Key** وأعطه أي اسم (مثلاً `codegenie`).
4. انسخ المفتاح فوراً (يبدأ بـ `gsk_...`) — لن يظهر لك مرة أخرى.

> ⚠️ لا تشارك المفتاح مع أحد ولا تضعه داخل الكود.

---

## 📱 2) التشغيل على Replit (من الجوال)

1. افتح تطبيق **Replit** (أو replit.com من المتصفح) وسجّل دخولك.
2. أنشئ مشروعاً جديداً: **Create Repl** ← اختر قالب **Python**.
3. أنشئ/افتح الملفات وانسخ المحتوى:
   - `main.py` ← الصق الكود الكامل (احذف أي محتوى قديم).
   - `requirements.txt` ← الصق محتواه.
4. أضف المفتاح السري:
   - اضغط **Tools** ← **Secrets** (أيقونة القفل 🔒).
   - اضغط **New Secret**:
     - **Key:** `GROQ_API_KEY`
     - **Value:** مفتاحك `gsk_...`
5. اضغط زر **Run ▶️**. ستُثبَّت المكتبات تلقائياً في أول مرة.
6. افتح تبويب **Webview** (أو الرابط الذي يظهر) وستجد التطبيق جاهزاً.

> إن لم تُثبَّت المكتبات تلقائياً: افتح **Shell** ونفّذ  
> `pip install -r requirements.txt` ثم اضغط Run.

---

## 🤖 3) التشغيل على Termux (أندرويد)

> حمّل Termux من **F-Droid** (نسخة Google Play قديمة ولا تعمل جيداً).

```bash
# 1) تحديث الحزم وتثبيت بايثون
pkg update -y && pkg upgrade -y
pkg install -y python

# 2) الانتقال لمجلد المشروع (أنشئه أولاً وضع فيه الملفات الثلاثة)
mkdir -p ~/codegenie && cd ~/codegenie
# أنشئ الملفات بمحرر nano:
#   nano main.py            (الصق الكود ثم Ctrl+X ثم Y ثم Enter)
#   nano requirements.txt

# 3) تثبيت المكتبات
pip install -r requirements.txt

# 4) ضبط مفتاح Groq (استبدل gsk_... بمفتاحك)
export GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxx"

# 5) تشغيل التطبيق
python main.py
```

ثم افتح متصفح الجوال على: **http://localhost:8000**

### 💡 نصائح Termux

- **حفظ المفتاح بشكل دائم** (حتى لا تكتبه كل مرة):
  ```bash
  echo 'export GROQ_API_KEY="gsk_xxxxxxxx"' >> ~/.bashrc
  source ~/.bashrc
  ```
  أو أنشئ ملف `.env` بجانب `main.py` يحتوي سطراً واحداً:
  ```
  GROQ_API_KEY=gsk_xxxxxxxx
  ```
  (التطبيق يقرأه تلقائياً.)
- **إن فشل تثبيت `pydantic-core`** (يحتاج بناء Rust):
  ```bash
  pkg install -y rust binutils clang make
  pip install -r requirements.txt
  ```
  أو ثبّت الحزمة الجاهزة أولاً: `pkg install -y python-pydantic` ثم أعد `pip install -r requirements.txt`.
- لإبقاء التطبيق يعمل والشاشة مطفأة: `termux-wake-lock`.
- لتغيير المنفذ: `PORT=9000 python main.py`.

---

## 💻 4) التشغيل على الكمبيوتر

```bash
pip install -r requirements.txt
export GROQ_API_KEY="gsk_..."      # على ويندوز PowerShell: $env:GROQ_API_KEY="gsk_..."
python main.py
```

افتح: **http://localhost:8000**

---

## ✨ طريقة الاستخدام

1. اكتب طلبك بالعربي في المربع الكبير (أو اضغط أحد الأمثلة السريعة).
2. اختر لغة البرمجة: **Lua (Roblox) / Python / JavaScript / HTML/CSS / Flutter / C#**.
3. اضغط **✨ ولّد الكود** (أو `Ctrl + Enter`).
4. اضغط **📋 نسخ الكود** لنسخه، أو **🔄 مسح** لتفريغ كل شيء.

## ⚙️ متغيرات بيئة اختيارية

| المتغير | الوصف | الافتراضي |
|---|---|---|
| `GROQ_API_KEY` | مفتاح Groq (**إلزامي**) | — |
| `GROQ_MODEL` | اسم النموذج | `llama-3.3-70b-versatile` |
| `MAX_TOKENS` | الحد الأقصى لطول الرد | `4096` |
| `PORT` | منفذ التشغيل | `8000` |

## 🛠️ حل المشاكل

| المشكلة | الحل |
|---|---|
| «لم يتم ضبط GROQ_API_KEY» | أضف المفتاح في Secrets (Replit) أو `export` (Termux) ثم أعد التشغيل |
| «مفتاح غير صحيح» | أنشئ مفتاحاً جديداً من console.groq.com/keys |
| «تجاوزت الحد المجاني» | انتظر دقيقة؛ الخطة المجانية لها حد طلبات في الدقيقة |
| الكود مقطوع | زِد `MAX_TOKENS` (مثلاً 6000) أو اطلب الكود على أجزاء |
| فحص الحالة | افتح `/api/health` للتأكد من أن المفتاح مضبوط |
