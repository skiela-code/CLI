#!/bin/sh
set -e

echo "Waiting for database..."
python -c "
import time, socket, os
host = os.environ.get('DB_HOST', 'db')
port = int(os.environ.get('DB_PORT', '5432'))
for i in range(30):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        break
    except OSError:
        time.sleep(1)
else:
    print('Database not reachable after 30s')
    exit(1)
"
echo "Database ready."

echo "Running migrations..."
alembic upgrade head

echo "Running seed data..."
python -m app.seed_data

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" "$@"
