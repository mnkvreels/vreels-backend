Prerequisites:

Before you begin, ensure you have the following installed:

Python 3.9.9
pip (Python package installer)
Virtualenv (optional but recommended)
SQL Server (or a compatible database)
Django 4.0 

1. Clone the Repository

git clone <repository-url>
cd <project-folder>

2. Set Up a Virtual Environment
Create and activate a virtual environment to isolate the dependencies:

For macOS/Linux:

python3 -m venv venv
source venv/bin/activate

For Windows:

python -m venv venv
venv\Scripts\activate

3. Install Dependencies
Install the required packages for the project:

pip install -r requirements.txt

4. Set Up Database Configuration
The application uses SQL Server. Update the database settings in the settings.py file with your database credentials:

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mssql',
        'NAME': '<your-database-name>',
        'USER': '<your-username>',
        'PASSWORD': '<your-password>',
        'HOST': '<your-server>',
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
        },
    }
}

Make sure to replace <your-database-name>, <your-username>, <your-password>, and <your-server> with your actual database information.

5. Migrate the Database
Run the database migrations to set up the necessary tables:

python manage.py migrate

6. Create a Superuser
Create a superuser account to access the Django admin panel:

python manage.py createsuperuser (Easy for development)

You'll be prompted to enter a username, email address, and password.

7. Collect Static Files
Collect all static files into a single directory so they can be served efficiently:

python manage.py collectstatic

8. Run the Development Server
Start the development server to run the application locally:

python manage.py runserver

You should now be able to access the application at http://127.0.0.1:8000/

