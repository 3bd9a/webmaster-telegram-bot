# استخدام صورة Playwright الرسمية
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# تعيين متغيرات البيئة
ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

# تعيين مجلد العمل
WORKDIR /app

# تثبيت تبعيات النظام
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# نسخ الملفات المطلوبة
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# إنشاء المجلدات اللازمة
RUN mkdir -p /app/data/downloads /app/data/temp /app/data/logs

# نسخ ملفات المشروع
COPY . .

# فتح منفذ لفحص الحالة
EXPOSE 8000

# تشغيل البوت
CMD ["python", "main.py"]