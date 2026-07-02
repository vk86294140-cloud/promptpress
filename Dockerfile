FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt openai
COPY . .
# data/ holds user resumes — mount a volume/disk here in production
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
