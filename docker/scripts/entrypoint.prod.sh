#!/bin/sh
# docker/scripts/entrypoint.prod.sh
# Entrypoint script cho môi trường production

set -e

echo "==> [PROD] Chờ PostgreSQL sẵn sàng..."
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
    echo "==> [PROD] Chạy database migrations..."
    python manage.py migrate --noinput

    echo "==> [PROD] Thu thập static files..."
    python manage.py collectstatic --noinput --clear
else
    echo "==> [PROD] Bỏ qua migrate và collectstatic (SKIP_MIGRATE=1)..."
fi

echo "==> [PROD] Khởi động Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --worker-class sync \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level ${GUNICORN_LOG_LEVEL:-info}
