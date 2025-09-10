FROM python:3.11-slim

WORKDIR /app

# تثبيت dependencies النظام
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# تثبيت المتصفح أولاً
RUN pip install playwright && \
    playwright install chromium

# نسخ المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# إنشاء مجلدات البيانات
RUN mkdir -p data/temp data/downloads data/logs

# تشغيل البوت
CMD ["python", "main.py"]
