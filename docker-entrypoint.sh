#!/bin/bash
set -e

# Wait for PostgreSQL to be available
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up - executing command"

# Create database tables if they don't exist
python -c "from app import db; from models import User, Calendar, SharedLink, Booking; db.create_all()"

# Start application
exec "$@"