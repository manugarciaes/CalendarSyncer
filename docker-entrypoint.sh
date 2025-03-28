#!/bin/bash
set -e

# Wait for PostgreSQL to be available
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up - executing command"

# Database tables creation is already handled in app.py within an app context
# Run a simple check to verify database connection
python -c "from app import app; print('Database connection verified successfully')"

# Start application
exec "$@"