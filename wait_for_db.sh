#!/bin/sh

echo "⏳ Aguardando o banco de dados PostgreSQL iniciar..."

while ! nc -z db 5432; do
  sleep 1
done

echo "✅ Banco de dados pronto! Aplicando migrações e iniciando o Django..."
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
