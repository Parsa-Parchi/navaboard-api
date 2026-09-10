# راهنمای فرانت NavaBoard

مرجع فیلدها و پاسخ هر درخواست Swagger در `/api/docs/` است؛ `schema.yml` نیز برای
تولید کلاینت OpenAPI در مخزن قرار دارد. شناسه‌ها UUID هستند. شناسهٔ کاربر، عضویت
workspace، عضویت board و assignee با یکدیگر تفاوت دارند.

## ورود OTP و کوکی

۱. `GET /api/auth/csrf/` با `credentials: "include"` بفرستید. مقدار `csrfToken`
را در حافظه نگه دارید؛ مرورگر کوکی CSRF را ذخیره می‌کند.

۲. `POST /api/auth/otp/request/` با `{"phone_number":"09121234567"}`.
پاسخ ۲۰۱ شامل `expires_at` است. فقط در توسعه `development_otp_code` ممکن است
برگردد. کد دو دقیقه اعتبار دارد. برای ۴۲۹، هدر `Retry-After` را رعایت کنید.

۳. `POST /api/auth/otp/verify/` با شماره و `code` شش‌رقمی، کوکی و هدر `X-CSRFToken`.
شمارهٔ جدید در همین مرحله حساب می‌سازد. JSON شامل `access`، `token_type`،
`user_created` و `user` است. refresh فقط از طریق `Set-Cookie` با HttpOnly تنظیم
می‌شود؛ فرانت نباید آن را بخواند یا در localStorage ذخیره کند.

نمونهٔ پایه برای ارائهٔ API و فرانت از یک origin:

```javascript
let access = null, csrfToken = null, refreshing = null;

async function initializeSession() {
  const response = await fetch('/api/auth/csrf/', { credentials: 'include' });
  if (!response.ok) throw new Error('CSRF initialization failed');
  csrfToken = (await response.json()).csrfToken;
}

async function verifyPhone(phone_number, code) {
  await initializeSession();
  const response = await fetch('/api/auth/otp/verify/', {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ phone_number, code })
  });
  const data = await response.json();
  if (!response.ok) throw data;
  access = data.access;
  return data.user;
}

async function refreshAccess() {
  if (!refreshing) {
    refreshing = (async () => {
      if (!csrfToken) await initializeSession();
      const response = await fetch('/api/auth/token/refresh/', {
        method: 'POST', credentials: 'include',
        headers: { 'X-CSRFToken': csrfToken }
      });
      if (!response.ok) { access = null; throw new Error('Sign in again'); }
      access = (await response.json()).access;
    })().finally(() => { refreshing = null; });
  }
  return refreshing;
}
```

برای مسیرهای محافظت‌شده `Authorization: Bearer <access>` بفرستید. عمر access
پانزده دقیقه و refresh چهارده روز است. بعد از ۴۰۱ حداکثر یک بار refresh و یک بار
تکرار درخواست انجام دهید؛ retry بی‌پایان نسازید. بعد از reload صفحه ابتدا CSRF
و سپس refresh را امتحان کنید. refreshهای همزمان باید یک درخواست مشترک داشته باشند.

خروج: `POST /api/auth/logout/` با کوکی و `X-CSRFToken`؛ سپس access حافظه را پاک کنید.
با access منقضی‌شده هم کار می‌کند. access صادرشده تا انقضای عادی معتبر می‌ماند؛
refresh این مرورگر باطل می‌شود.

در توسعه `/api` را در dev server فرانت به Django proxy کنید. برای origin مجزا،
reverse proxy باید CORS را فقط برای origin مجاز تنظیم کند؛ wildcard با credentials
کار نمی‌کند. `CSRF_TRUSTED_ORIGINS` نیز باید origin فرانت را داشته باشد. مسیر
پیش‌فرض این پروژه same-origin است؛ middleware مربوط به CORS در مخزن وجود ندارد.

## ایمیل اختیاری و پروفایل

- `GET /api/auth/me/`: پروفایل؛ PATCH/PUT با `full_name` برای تغییر نام.
- `POST /api/auth/email/verification/request/` با `email`: درخواست کد بعد از ورود تلفنی.
- `POST /api/auth/email/verification/confirm/` با `email` و `code`: ثبت ایمیل تأییدشده.
- `POST /api/auth/password/set/` با `password`: تعیین رمز اختیاری؛ سپس دوباره وارد شوید.
- `POST /api/auth/email/login/` با `email` و `password`: ورود بعدی با CSRF و کوکی.
- تغییر شماره: `/api/auth/phone/change/request/` و `/confirm/`؛ شمارهٔ مقصد فیلد `phone_number` است.
- بازیابی رمز: `/api/auth/password/reset/request/` با `phone_number`؛ `/confirm/` با شماره، `code` و `new_password`.

از مسیرهای قدیمی `email/signup` استفاده نکنید؛ پیش‌فرض ۴۱۰ می‌دهند. ایمیل، شماره
و وضعیت تأیید با PATCH پروفایل قابل تغییر نیستند.

## جریان ساخت برد

۱. `POST /api/workspaces/` با `name`؛ سازنده owner می‌شود.
۲. `POST /api/workspaces/{id}/members/` با `phone_number` و `role`؛ عضو باید قبلاً حساب داشته باشد.
۳. `POST /api/workspaces/{id}/boards/` با `name` و `visibility` از نوع `private` یا `workspace`.
۴. `POST /api/boards/{id}/lists/` با `title`.
۵. `POST /api/boards/{board_id}/lists/{list_id}/cards/` با `title`.

`GET /api/boards/{id}/` لیست‌ها و کارت‌های مرتب را برای نمایش اولیه می‌دهد.
برای همکاری‌ها از مسیرهای اختصاصی کامنت، لیبل، چک‌لیست و assignee استفاده کنید.
`due_at` تاریخ ISO 8601 با timezone است؛ برای پاک‌کردن آن `null` بفرستید.

| نقش | دسترسی |
| --- | --- |
| owner workspace | مدیریت workspace و همهٔ بردهای آن |
| admin workspace | ویرایش workspace و مدیریت اعضای عادی؛ دسترسی خودکار به برد خصوصی ندارد |
| عضو workspace | مشاهدهٔ workspace و بردهای workspace-visible |
| admin برد | مدیریت برد، اعضا، لیبل و assignee |
| عضو برد | ویرایش محتوای برد، کارت، چک‌لیست و ثبت کامنت |

عضو workspace بدون عضویت برد، روی برد workspace-visible فقط خواندن دارد.
کامنت فقط توسط نویسنده یا مدیر مجاز قابل تغییر است. assignee کردن کاربر، به او
دسترسی برد خصوصی نمی‌دهد؛ عضویت برد را جداگانه اضافه کنید.

## جابه‌جایی

`POST /api/boards/{board_id}/cards/{card_id}/move/`:

```json
{"destination_list_id":"UUID-of-list","position":0}
```

موقعیت از صفر شروع می‌شود. در همان لیست: صفر تا تعداد منهای یک؛ به لیست دیگر:
صفر تا تعداد کارت مقصد. مقصد باید روی همان برد باشد. بعد از موفقیت یا خطای تغییر
همزمان، لیست‌های درگیر را دوباره دریافت کنید. لیست و چک‌لیست نیز `move/` با position دارند.

## اعلان و تاریخچه

- `GET /api/notifications/?unread=true`: اعلان خوانده‌نشدهٔ کاربر.
- `GET /api/notifications/unread-count/`: مقدار `count` نشان اعلان.
- `POST /api/notifications/{id}/read/`: خوانده‌شدن یک اعلان، بدون بدنه.
- `POST /api/notifications/read-all/`: خوانده‌شدن همه؛ پاسخ `updated`.
- فیدها: `/api/workspaces/{id}/activity/`، `/api/boards/{id}/activity/` و `/api/cards/{id}/activity/`.

فیدها جدیدترین را اول می‌دهند و پاسخ `count/next/previous/results` دارند.
پارامترهای `page` و `page_size`، اندازهٔ پیش‌فرض ۳۰ و سقف ۱۰۰ هستند. دریافت اعلان
با polling است؛ WebSocket یا push پیاده نشده.

عملیات کارت/همکاری به assignee و سازندهٔ کارت اعلان می‌دهد؛ تغییر عضویت به مالک
و عضو موجود در پاسخ عملیات. برای اقدام خود کاربر اعلان نمی‌سازیم. دسترسی در هر
بار خواندن بررسی می‌شود. history از زمان نصب ثبت می‌شود و شامل تغییر مستقیم ORM/admin نیست.
`action` نام namespace، مسیر و متد است؛ `resource_id` شیء تغییرکرده است.
بدنهٔ کامل درخواست یا متن کامنت در history ذخیره نمی‌شود.

## جست‌وجو و فایل

`GET /api/cards/` صفحه‌بندی دارد؛ فیلترها: `q`، `workspace_id`، `board_id`،
`assigned_to_me`، `due_before` و `due_after`. فیلترها همزمان اعمال می‌شوند.

پیوست: `POST /api/cards/{id}/attachments/` به شکل multipart با `file`؛ پیش‌فرض
حداکثر ۱۰ MiB. GET همان مسیر متادیتا می‌دهد. دانلود با Bearer از
`/api/cards/{id}/attachments/{attachment_id}/content/` و دریافت blob انجام می‌شود.
URL عمومی وجود ندارد. DELETE مسیر جزئیات، پیوست را حذف نرم می‌کند.

## خطاها

- ۴۰۰: ورودی/کد/refresh نامعتبر؛ بدنه نگاشت فیلد به لیست خطا یا لیست پیام‌هاست.
- ۴۰۱: access نامعتبر؛ یک بار refresh کنید.
- ۴۰۳: نقش کافی نیست یا CSRF نامعتبر؛ refresh مشکل مجوز را رفع نمی‌کند.
- ۴۰۴: شیء موجود، فعال یا برای کاربر قابل مشاهده نیست.
- ۴۱۰: مسیر قدیمی ثبت‌نام ایمیلی غیرفعال است.
- ۴۲۹: `Retry-After` را رعایت کنید.
- ۵۰۳: سرویس ارسال کد خطا داده است.

DELETE معمولاً ۲۰۴ بدون بدنه دارد؛ روی آن `response.json()` اجرا نکنید. حذف نرم
والد، دسترسی زیرمجموعه را هم می‌بندد. endpoint عمومی برای restore وجود ندارد.
