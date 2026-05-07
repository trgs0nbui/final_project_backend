#!/bin/sh
# docker/scripts/entrypoint.dev.sh
# Entrypoint script cho môi trường development

set -e

echo "==> [DEV] Chờ PostgreSQL sẵn sàng..."
until python -c "
import psycopg2, os
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('PostgreSQL sẵn sàng!')
except Exception as e:
    raise SystemExit(1)
" 2>/dev/null; do
    echo "PostgreSQL chưa sẵn sàng, thử lại sau 2 giây..."
    sleep 2
done

if [ "${SKIP_MIGRATE}" != "1" ]; then
    echo "==> [DEV] Chạy database migrations..."
    python manage.py migrate --noinput
else
    echo "==> [DEV] Bỏ qua migrate (SKIP_MIGRATE=1)..."
fi

echo "==> [DEV] Khởi động..."
exec "$@"
