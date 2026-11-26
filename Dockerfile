# Mesma versão do Python da máquina de desenvolvimento (3.14) e do CI (.github/workflows/ci.yml): o pandas 3
# exige Python >= 3.11, e servidor com 3.10 + pandas 2.x diferente do local já quebrou o debriefing da BV-26.
# Ao trocar aqui, trocar no ci.yml junto.
FROM python:3.14-slim

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
