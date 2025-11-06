# WinScale Django Project Setup

This guide provides step-by-step instructions to set up the **WinScale** Django project with a PostgreSQL database.

## Prerequisites
Ensure you have the following installed:
- Python (>=3.8)
- PostgreSQL
- pip & virtualenv
- Git (optional, for version control)

## Installation Steps

### 1. Create and Activate a Virtual Environment
```sh
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 2. Clone the Repository
```sh
 git clone https://github.com/century-it-department/scrap-management-service.git
 cd winscale
```

### 3. Install Dependencies
```sh
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL Database
- Open PostgreSQL and create a database:
- winscale

- Update `settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'winscale',
        'USER': 'winscale_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 5. Run Migrations
```sh
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Development Server
```sh
python manage.py runserver
```

Access the project at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Additional Commands
- **Install a new package:** `pip install package_name && pip freeze > requirements.txt`
- **Run tests:** `python manage.py test`
- **Collect static files:** `python manage.py collectstatic`

## License
This project is licensed under the MIT License. Feel free to modify and distribute.

