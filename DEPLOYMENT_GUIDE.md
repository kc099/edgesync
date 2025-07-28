# Deployment Guide: Edgesync Backend

This guide outlines the steps to deploy the `edgesync` Django application on a production-like environment, specifically a single AWS Lightsail instance.

It covers:
1.  Setting up a robust database (PostgreSQL).
2.  Configuring Django Channels with Redis.
3.  Running the application using the Daphne ASGI server.

## Step 1: Prerequisites & Dependencies

Ensure the following are installed on your server (e.g., Ubuntu):

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip postgresql postgresql-contrib redis-server
```

## Step 2: Project Setup

1.  **Clone the repository** and navigate into the `edgesync` directory.
2.  **Create a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install daphne channels_redis psycopg2-binary
    ```

## Step 3: Database Configuration (PostgreSQL)

Using SQLite in production is not recommended. Follow these steps to migrate to PostgreSQL.

1.  **Create a PostgreSQL database and user:**
    ```sql
    sudo -u postgres psql
    CREATE DATABASE edgesync_db;
    CREATE USER edgesync_user WITH PASSWORD 'your-secure-password';
    ALTER ROLE edgesync_user SET client_encoding TO 'utf8';
    ALTER ROLE edgesync_user SET default_transaction_isolation TO 'read committed';
    ALTER ROLE edgesync_user SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE edgesync_db TO edgesync_user;
    \q
    ```

2.  **Update `edgesync/settings.py`:** Replace the `DATABASES` configuration.

    ```python
    # edgesync/settings.py

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'edgesync_db',
            'USER': 'edgesync_user',
            'PASSWORD': 'your-secure-password',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }
    ```

## Step 4: Channels & Redis Configuration

1.  **Ensure Redis is running:**
    ```bash
    sudo systemctl status redis-server
    ```
2.  **Update `edgesync/settings.py`** to use `RedisChannelLayer`:

    ```python
    # edgesync/settings.py

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [("127.0.0.1", 6379)],
            },
        },
    }
    ```

## Step 5: Running the Application with Daphne

1.  **Apply migrations** to the new PostgreSQL database:
    ```bash
    python manage.py migrate
    ```
2.  **Collect static files:**
    ```bash
    python manage.py collectstatic
    ```
3.  **Run the Daphne server:**
    ```bash
    daphne -b 0.0.0.0 -p 8001 edgesync.asgi:application
    ```
    *   `-b 0.0.0.0`: Binds to all network interfaces.
    *   `-p 8001`: Runs on port 8001. Nginx will proxy requests to this port.

For production, you should run this Daphne command using a process manager like `systemd` or `supervisor` to ensure it runs as a background service and restarts on failure.
