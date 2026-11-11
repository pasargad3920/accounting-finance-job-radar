# راهنمای نصب Accounting & Finance Job Radar در GitHub

این راهنما برای **نسخه آزمایشی با ۵۰ شرکت هدف** است: ۱۲ فید API از قبل تنظیم شده‌اند، اما تا اولین اسکن موفق «فعال و تأییدشده» محسوب نمی‌شوند؛ ۳۸ شرکت دیگر فقط در فهرست هدف هستند و هنوز به‌طور خودکار پایش نمی‌شوند.

## مرحله ۱ — بازکردن فایل پروژه

1. فایل `Accounting_Finance_Job_Radar_V2.zip` را دانلود کن.
2. روی کامپیوتر ویندوزی آن را **Extract All** کن. دقت کن که پوشه مخفی `.github` و زیرپوشه `workflows` در فایل‌های استخراج‌شده وجود داشته باشد.
3. اگر برنامه GitHub Desktop را نداری، آن را از https://desktop.github.com/ نصب کن و با GitHub وارد شو.

## مرحله ۲ — انتشار پروژه

**روش پیشنهادی با GitHub Desktop:**

1. از منوی **File → Add local repository** پوشه پروژه استخراج‌شده را انتخاب کن. اگر گفت Git repository نیست، گزینه **Create a repository here** را بزن.
2. نام مخزن را `accounting-finance-job-radar` بگذار و آن را ایجاد کن.
3. داخل GitHub Desktop ابتدا فایل‌ها را Commit کن (برای نمونه `Initial job radar pilot`).
4. روی **Publish repository** کلیک کن و اگر مخزن Private پیش‌فرض است، آن را **Public** کن؛ در نسخه GitHub Free، استفاده از یک مخزن عمومی برای GitHub Pages ساده‌ترین حالت است.
5. سایت پروژه عمومی است؛ در این بسته **نباید** رمز، رزومه یا اطلاعات شخصی داخل فایل‌ها وجود داشته باشد.

**روش جایگزین با Git:**

ابتدا یک مخزن **Public** خالی در GitHub ایجاد کن (بدون README جداگانه). سپس داخل پوشه استخراج‌شده در Terminal اجرا کن:

```bash
git init
git branch -M main
git add .
git commit -m "Initial Accounting Finance Job Radar"
git remote add origin https://github.com/YOUR_USERNAME/accounting-finance-job-radar.git
git push -u origin main
```

به‌جای `YOUR_USERNAME` نام کاربری GitHub خودت را قرار بده.

## مرحله ۳ — فعال‌کردن GitHub Pages

1. مخزن را در سایت GitHub باز کن.
2. به **Settings → Pages** برو.
3. در **Build and deployment** گزینه **Source → GitHub Actions** را انتخاب کن.
4. آدرس سایت معمولاً به این شکل خواهد بود:

`https://YOUR_USERNAME.github.io/accounting-finance-job-radar/`

این یک **الگوی آدرس** است؛ لینک دقیق را بعد از اولین استقرار موفق در قسمت **Settings → Pages** ببین.

## مرحله ۴ — تنظیم ایمیل (اختیاری، اما برای هشدارها لازم)

اگر Gmail داری، ابتدا **2-Step Verification** را فعال کن. در صورت پشتیبانی حساب، از صفحه رسمی https://myaccount.google.com/apppasswords رمز مخصوص برنامه (App Password) بگیر. این رمز را **در چت یا مخزن عمومی قرار نده**.

در مخزن GitHub:

1. به **Settings → Secrets and variables → Actions** برو.
2. روی **New repository secret** بزن.
3. سه مقدار زیر را جداگانه ایجاد کن:

| Secret name | چه چیزی وارد می‌شود؟ |
|---|---|
| `SMTP_USER` | آدرس Gmail فرستنده |
| `SMTP_APP_PASSWORD` | رمز App Password همین حساب (نه رمز اصلی Gmail) |
| `ALERT_TO` | آدرس ایمیلی که می‌خواهی اعلان‌ها به آن برسند؛ می‌تواند همان Gmail باشد |

این تنظیمات برای دریافت اعلان‌هاست؛ ایمیلی که سیستم ارسال می‌کند از طرف همان Gmail خواهد بود. اگر امکان App Password نداری، **به‌جای واردکردن رمز اصلی Gmail، این مرحله را رد کن**؛ داشبورد بدون ایمیل همچنان کار خواهد کرد و بعداً می‌توان روش OAuth یا سرویس SMTP دیگری را افزود.

## مرحله ۵ — اجرای آزمایشی و بررسی نتیجه

1. در مخزن، تب **Actions** را باز کن.
2. workflow با نام **Accounting & Finance Job Radar** را انتخاب کن.
3. روی **Run workflow** بزن؛ Branch باید `main` باشد.
4. در اجرای مربوط، مرحله‌های **Test scanner** و **Scan public career APIs** را بررسی کن.
5. اگر یک یا چند منبع خطا داد، وضعیت آن در جدول **Company coverage** به‌صورت `API · Error` نشان داده می‌شود؛ خطاها را نباید به «هیچ آگهی فعالی وجود ندارد» تعبیر کرد.
6. در پایان، مرحله **Deploy latest dashboard** باید موفق شود. آدرس سایت را از **Settings → Pages** باز کن.

**رفتار مهم اولین اجرا:** ابتدا آگهی‌های موجود ثبت می‌شوند، اما سیستم آنها را به عنوان آگهی «تازه پیدا شده پس از فعال‌سازی» ایمیل نمی‌کند. اعلان‌ها مربوط به فرصت‌هایی‌اند که در اسکن‌های بعدی برای اولین بار شناسایی می‌شوند.

## مرحله ۶ — کنترل عملکرد

در داشبورد سه بخش داری:

- **Corporate job feed**: موقعیت‌های شناسایی‌شده، فیلتر Lombardia / Rest of Italy / Location to verify و لینک Apply.
- **LinkedIn quick search**: شش گروه کلیدواژه با بازه‌های ۱، ۳ و ۲۴ ساعت. لینک‌های ۱ و ۳ ساعت غیررسمی هستند و ممکن است LinkedIn آنها را نادیده بگیرد.
- **Company coverage**: فهرست ۵۰ شرکت؛ وضعیت واقعی اتصال، آخرین اسکن موفق، و لینک Careers برای موارد شناخته‌شده.

سیستم تقریباً هر ساعت (دقیقه ۱۷ به وقت UTC) تلاش می‌کند اجرا شود؛ اجرای واقعی ممکن است با تأخیر انجام شود یا بعضی نوبت‌ها از دست بروند. هشدار جدید به‌صورت best-effort و خلاصه روزانه نزدیک ساعت **۰۸:۱۷ صبح به وقت ایتالیا** است (فقط در صورت وجود نتیجه و تنظیم ایمیل).

## مشکلات رایج

- **Pages URL خطای 404 می‌دهد:** صفحه `Settings → Pages` و موفقیت مرحله Deploy را بررسی کن. انتشار باید با `GitHub Actions` تنظیم شده باشد.
- **در Corporate jobs چیزی نیست:** در Company coverage بررسی کن چه تعداد فید موفق بوده‌اند. محل را به `All Italian matches` و زمان را `All active jobs` تغییر بده.
- **ایمیل نمی‌رسد:** وجود سه Secret، فعال‌بودن 2FA و مجازبودن App Password و لاگ `Send new matching job emails` را بررسی کن. اولین اسکن عمداً ایمیل «آگهی جدید» ارسال نمی‌کند.
- **یک شرکت معروف هنوز مانیتور نمی‌شود:** اگر وضعیت `Directory only` دارد، صرفاً در فهرست توسعه است. نمی‌توان بدون بررسی ATS/API/سیاست دسترسی آن، خودکار پایش‌شده معرفی‌اش کرد.
- **Rest of Italy در لینکدین Lombardia را هم نشان می‌دهد:** این محدودیت فیلتر لینکدین است و در داشبورد صریحاً اعلام شده است؛ در نتایج ATS فیلتر جغرافیایی جداگانه اعمال می‌شود.

## امنیت

**هیچ رمز عبور یا ایمیل شخصی را داخل `config/companies.json`، `state.json`، `docs/data.json` یا GitHub README وارد نکن.** تنظیمات حساس فقط داخل GitHub Actions Secrets ذخیره شوند.

## اطلاعات تکمیلی

درباره هزینه‌ها و محدودیت‌های API و مراحل توسعه به نسخه بزرگ‌تر، فایل `README.md` را ببین.
