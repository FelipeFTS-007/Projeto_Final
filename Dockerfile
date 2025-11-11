FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências e instalar pacotes Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o script de espera ANTES de dar chmod
COPY wait_for_db.sh .
RUN chmod +x wait_for_db.sh

# Copiar o restante do projeto
COPY . .

CMD ["./wait_for_db.sh"]
