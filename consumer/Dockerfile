FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY setup_tables.py consumer.py ./

# Create the raw-layer tables (idempotent), then run the consumer loop (SPEC §22.3).
CMD ["sh", "-c", "python setup_tables.py && python consumer.py"]
