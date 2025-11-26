# Imagem base
FROM python:3.11-slim

# Variáveis de ambiente do Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1



# Instalar dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential libpq-dev netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copia requirements primeiro
COPY requirements.txt /app/
RUN apt-get update \
    && apt-get install -y build-essential libpq-dev python3-dev \
    && apt-get clean

RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia todo o projeto
COPY . /app/

# Permissão no entrypoint
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
