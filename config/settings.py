"""
Django Settings pour l'Application de Gestion d'Archives Audiovisuelles et Documentaires.
Projet : Radio Kara Archive Project

Refactorisé pour combiner l'ensemble des optimisations avancées (SQLite WAL,
gestion de session, limites d'upload) avec le support complet de WhiteNoise et REST Framework.
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created
from django.dispatch import receiver

# Chargement optionnel de python-dotenv s'il est installé
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except ImportError:
    pass


# ==============================================================================
# 1. CHEMINS ET VARIABLES D'ENVIRONNEMENT
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name, default=False):
    val = os.environ.get(name, str(default)).lower()
    return val in {'1', 'true', 'yes', 'on', 't'}

ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development').lower()
DEBUG = env_bool('DJANGO_DEBUG', os.environ.get('DEBUG', ENVIRONMENT != 'production'))

# Clé secrète
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', os.environ.get('SECRET_KEY', ''))
if not SECRET_KEY:
    if ENVIRONMENT == 'production' or not DEBUG:
        raise ImproperlyConfigured("CRITIQUE : La variable DJANGO_SECRET_KEY / SECRET_KEY n'est pas définie.")
    SECRET_KEY = 'django-insecure-development-only-change-me'

# Hôtes autorisés
default_hosts = 'localhost,127.0.0.1,testserver' if DEBUG else ''
raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', os.environ.get('ALLOWED_HOSTS', default_hosts))
ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(',') if host.strip()]

if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must list the intranet DNS name in production.')

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]


# ==============================================================================
# 2. DEFINITION DES APPLICATIONS (INSTALLED_APPS)
# ==============================================================================

INSTALLED_APPS = [
    # Applications Django par défaut
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Librairies tierces
    'whitenoise.runserver_nostatic',
    'rest_framework',

    # Applications Métier (Architecture modulaire)
    'core.apps.CoreConfig',
    'audio_archive.apps.AudioArchiveConfig',
    'document_archive.apps.DocumentArchiveConfig',
]


# ==============================================================================
# 3. MIDDLEWARE & ROUTING
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# SÉCURITÉ DE SESSION (Déconnexion après inactivité)
SESSION_COOKIE_AGE = 900  # 15 minutes d'inactivité
SESSION_SAVE_EVERY_REQUEST = True  # Réinitialise le timer à chaque action
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# TENTATIVES DE CONNEXION (Django Axes / Paramètres d'échec)
AXES_FAILURE_LIMIT = 3
AXES_COOLOFF_TIME = 1

ROOT_URLCONF = os.environ.get('DJANGO_ROOT_URLCONF', 'config.urls')
WSGI_APPLICATION = os.environ.get('DJANGO_WSGI_APPLICATION', 'config.wsgi.application')


# ==============================================================================
# 4. TEMPLATES (MOTEUR DE RENDU)
# ==============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ==============================================================================
# 5. BASE DE DONNÉES (SQLITE OPTIMISÉE POUR LA CONCURRENCE)
# ==============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', BASE_DIR / 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 30,  # Évite les erreurs 'database is locked' sous charge
        },
        'CONN_MAX_AGE': 600,  # la connexion pendant 10 min
    }
}

@receiver(connection_created)
def configure_sqlite_performance(sender, connection, **kwargs):
    """
    Optimisation SQLite lors de l'établissement d'une connexion :
    - Mode WAL (Write-Ahead Logging) pour lectures/écritures simultanées
    - Cache RAM (-64000 = ~64Mo)
    - Tables temporaires en mémoire
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA cache_size=-64000;')
        cursor.execute('PRAGMA temp_store=MEMORY;')


# ==============================================================================
# 6. SÉCURITÉ ET VALIDATION DES MOTS DE PASSE
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ==============================================================================
# 7. INTERNATIONALISATION ET FUSEAU HORAIRE
# ==============================================================================

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Lome'

USE_I18N = True
USE_TZ = True


# ==============================================================================
# 8. FICHIERS STATIQUES ET MÉDIAS
# ==============================================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# radio_kara_archive_project/settings.py

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Outils complémentaires (OCR)
TESSERACT_CMD = os.environ.get('TESSERACT_CMD', '')

# Autorise l'affichage en iframe depuis le même domaine
X_FRAME_OPTIONS = 'SAMEORIGIN'

# ==============================================================================
# 9. LIMITES D'UPLOAD ET D'INJECTION DE DONNÉES
# ==============================================================================

# Support des gros fichiers audio / documents (500 Mo)
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760


# ==============================================================================
# 10. AUTHENTIFICATION & REST FRAMEWORK
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = os.environ.get('DJANGO_LOGIN_URL', 'login')
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Paramètres de proxy / SSL de production
USE_X_FORWARDED_HOST = env_bool('DJANGO_USE_X_FORWARDED_HOST', False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if env_bool('DJANGO_USE_PROXY_SSL_HEADER', False) else None
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', False)
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', False)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', False)
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)