# Radio Kara Archive Project

Application Django de gestion, consultation et préservation des archives audio et documentaires de Radio Kara.

## Fonctions principales

- Archivage des documents, extraction OCR, miniatures et recherche plein texte.
- Archivage audio, métadonnées radio, durée automatique, écoute, téléchargement et favoris.
- Rôles `ADMIN`, `ARCHIVISTE`, `JOURNALISTE` et `LECTEUR`.
- Historique personnel des documents consultés et audios écoutés.
- Journal d'audit filtrable : connexions, opérations métier, consultations, favoris, export du journal et mutations non couvertes par une vue métier.
- Tableaux de bord adaptés au rôle de l'utilisateur.

## Architecture

| Élément | Responsabilité |
| --- | --- |
| `core` | Authentification, profils/rôles, tableaux de bord, audit et gestion des utilisateurs. |
| `audio_archive` | Archives audio, langues, catégories, playlists, favoris et historique d'écoute. |
| `document_archive` | Documents, OCR, catégories, favoris, historique de consultation et API REST. |
| `templates/` | Interfaces Django HTML. |
| `static/` | JavaScript, CSS, images et outils d'enregistrement/édition audio. |
| `config/` | Configuration Django, routage WSGI/ASGI et paramètres de déploiement. |

Le journal métier est stocké dans `core.AuditLog`. Les actions détaillées sont écrites par les vues et signaux ; `core.middleware.AuditMutationMiddleware` couvre les opérations HTTP de modification qui auraient été oubliées.

## Installation locale

Pré-requis : Python 3.13, FFmpeg (conversion audio) et, si l'OCR est utilisé, Tesseract OCR avec les langues requises.

```powershell
py -3.13 -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

L'application est ensuite disponible sur `http://127.0.0.1:8000/`.

## Configuration

Les variables sont chargées depuis `.env` ; ce fichier ne doit jamais être versionné.

| Variable | Usage |
| --- | --- |
| `DJANGO_ENV` | `development` ou `production`. |
| `DJANGO_DEBUG` | `True` uniquement en développement. |
| `DJANGO_SECRET_KEY` | Clé Django longue, aléatoire et secrète. Obligatoire en production. |
| `DJANGO_ALLOWED_HOSTS` | Noms DNS/IP publics séparés par des virgules. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origines HTTPS autorisées, séparées par des virgules. |
| `DJANGO_DB_PATH` | Chemin SQLite, uniquement adapté à un pilote ou faible charge. |
| `TESSERACT_CMD` | Chemin de l'exécutable Tesseract sous Windows si nécessaire. |
| `DJANGO_USE_PROXY_SSL_HEADER` | `True` derrière un proxy TLS qui fournit `X-Forwarded-Proto`. |

En production, les réglages HTTPS, HSTS et cookies sécurisés sont activés par défaut lorsque `DJANGO_ENV=production` (ou `DJANGO_DEBUG=False`).

## Modèle de données

### Core

- `UserProfile` : rôle applicatif et téléphone, lié un-à-un à `User`.
- `AuditLog` : acteur, action, module, description, IP et horodatage.

### Audio

- `Category`, `Language`, `AudioFile` : métadonnées et fichier de l'archive.
- `AudioView` : une entrée par écoute utilisateur.
- `Favorite`, `Playlist`, `PlaylistItem` : organisation personnelle des audios.

### Documents

- `Category`, `Document` : fichier, métadonnées, miniature et texte OCR.
- `DocumentView` : une entrée par consultation.
- `Favorite` : favoris de documents.

## Routes métier

| Préfixe | Description |
| --- | --- |
| `/` | Authentification et dashboards. |
| `/audio/` | Recherche, gestion et streaming audio. |
| `/documents/` | Documents, OCR, recherche et API REST (`/documents/api/`). |
| `/admin/` | Administration Django. |
| `/audit/` | Journal d'audit réservé aux administrateurs. |

Les fichiers audio/documents sont placés sous `media/`. En production, ils doivent être servis par Nginx, Apache ou un stockage objet, jamais par `runserver`.

## Tests

```powershell
.\env\Scripts\python.exe manage.py test core audio_archive document_archive
.\env\Scripts\python.exe manage.py check
.\env\Scripts\python.exe manage.py check --deploy
```

La suite actuelle vérifie les accès protégés, la connexion, l'audit, les favoris, les consultations et écoutes, l'historique audio/document et le blocage de l'export DOCX du journal.

## Production

La procédure complète, les sauvegardes et la checklist de mise en ligne sont dans [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Commandes utiles

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py test
```

## Licence et données

Les archives de Radio Kara et les données personnelles des utilisateurs doivent être sauvegardées, protégées par des accès appropriés et exploitées conformément aux règles de l'institution.
