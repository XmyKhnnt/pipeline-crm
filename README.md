# Pipeline CRM

Pipeline CRM is a small, server-rendered Django application for managing user-owned Kanban pipelines. Each new pipeline starts with **New**, **In Progress**, **Won**, and **Lost** stages. Cards can be created, edited, deleted, and moved or reordered by drag-and-drop.

## Screenshots

### Pipeline list

![Pipeline list](docs/screenshots/pipeline-list.png)

### Kanban board

![Kanban board](docs/screenshots/kanban-board.png)

## Requirements

- Python 3.12+
- PostgreSQL for production (SQLite is the default local database)
- pip

## Local setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies and initialise the database:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the superuser account. Django Admin is available at `/admin/`.

## Environment variables

See [`.env.example`](.env.example). The application reads standard environment variables directly; it intentionally does not add a dotenv dependency. Set values in your shell, process manager, container, or platform configuration.

For local development, no `DATABASE_URL` is needed and SQLite is used. To use PostgreSQL, create a database and set a URL before migrating:

```powershell
$env:DATABASE_URL = "postgresql://pipeline_crm:your-password@localhost:5432/pipeline_crm"
python manage.py migrate
```

Production requires `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `DATABASE_URL`, and (when relevant) `CSRF_TRUSTED_ORIGINS`. Enable `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE` only when HTTPS is correctly terminated.

## Development commands

```powershell
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

## Production

Install the same requirements, export the production environment variables, collect assets, and serve the WSGI app with Gunicorn:

```bash
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

WhiteNoise serves collected static assets. PostgreSQL is selected automatically when `DATABASE_URL` starts with `postgres://` or `postgresql://`.

## Project structure

```text
config/       Django project settings and root URLs
pipelines/    Models, forms, views, URLs, admin, migrations, and tests
templates/    Base, authentication, and pipeline templates
static/       Application CSS and Kanban JavaScript
```
