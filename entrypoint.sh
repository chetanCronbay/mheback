#!/bin/bash

# Exit the script on any error
set -o errexit

# Apply database migrations
python manage.py migrate --noinput

# Collect static files (optional, useful in production)
python manage.py collectstatic --noinput

# Start the Django application with Gunicorn
exec gunicorn mhe_backend.wsgi:application --bind 0.0.0.0:8000