FROM python:3.11-slim

# تنظیم متغیرهای محیطی
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# کپی کردن نیازمندی‌ها و پوشه فایل‌های دانلود شده
COPY requirements.txt .
COPY wheels/ /app/wheels/

# نصب پکیج‌ها کاملاً آفلاین (بدون مراجعه به اینترنت)
RUN pip install --no-index --find-links=/app/wheels -r requirements.txt

# کپی کردن بقیه فایل‌های پروژه
COPY docs/ /app/docs/
COPY . .

EXPOSE 8000

CMD ["streamlit", "run", "app.py", "--server.port=8000", "--server.address=0.0.0.0"]


