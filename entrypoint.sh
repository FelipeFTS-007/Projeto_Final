#!/bin/sh

# Para parar o script se der erro
set -e

echo "Aguardando o banco de dados PostgreSQL..."
while ! nc -z "$DATABASE_HOST" "$DATABASE_PORT"; do
  sleep 1
done
echo "PostgreSQL pronto!"

# Rodar migrações
python manage.py migrate --noinput

# Criar superuser automaticamente
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py shell << EOF
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
EOF
fi

# Coletar arquivos estáticos
python manage.py collectstatic --noinput

echo "Iniciando o servidor..."
exec "$@"
