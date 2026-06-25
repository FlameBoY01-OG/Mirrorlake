FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate.py .

# -u: unbuffered stdout so logs appear immediately in `docker compose logs`
CMD ["python", "-u", "generate.py"]
