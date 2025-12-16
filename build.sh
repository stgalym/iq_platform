#!/usr/bin/env bash
# Выход при ошибке
set -o errexit

# Установка библиотек
pip install -r requirements.txt

# Сбор статики (CSS/JS)
python manage.py collectstatic --no-input

# Применение миграций базы данных
python manage.py migrate