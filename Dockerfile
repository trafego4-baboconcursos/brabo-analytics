FROM python:3.10-slim

WORKDIR /app

# Instala dependências do sistema necessárias para compilação/postgres se aplicável
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/analises

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "frontend.app:app", "--host", "0.0.0.0", "--port", "8000"]
