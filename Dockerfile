FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
COPY wheels/ /app/wheels/

RUN pip install --no-index --find-links=/app/wheels -r requirements.txt

COPY docs/ /app/docs/
COPY . .

EXPOSE 8000

CMD ["streamlit", "run", "app.py", "--server.port=8000", "--server.address=0.0.0.0"]


