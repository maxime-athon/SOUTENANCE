# Guide de déploiement et exploitation

## Décision de mise en production

Le code et les tests permettent un pilote interne. Avant exposition sur Internet, tous les points de la checklist ci-dessous doivent être validés par la personne responsable de l'infrastructure.

Le projet utilise SQLite. C'est acceptable pour une démonstration ou un petit nombre d'utilisateurs avec peu d'écritures concurrentes. Pour une exploitation radio avec uploads, OCR, audit et écoutes simultanés, migrez vers PostgreSQL avant la mise en service.

## Checklist obligatoire

- [ ] `DJANGO_ENV=production` et `DJANGO_DEBUG=False`.
- [ ] `DJANGO_SECRET_KEY` est une clé aléatoire d'au moins 50 caractères, stockée hors du dépôt.
- [ ] `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` contiennent le domaine HTTPS final.
- [ ] Un certificat TLS est installé ; le proxy transmet correctement `X-Forwarded-Proto`.
- [ ] `python manage.py check --deploy` ne retourne aucune alerte.
- [ ] Les migrations sont appliquées et vérifiées avec `python manage.py showmigrations`.
- [ ] Les fichiers statiques ont été générés avec `python manage.py collectstatic --noinput`.
- [ ] Les médias sont servis par Nginx/Apache ou un stockage objet.
- [ ] Une sauvegarde chiffrée et restaurable de la base et du répertoire médias est planifiée.
- [ ] Les tests automatisés passent.
- [ ] Les comptes administrateurs, mots de passe et droits de groupes ont été revus.
- [ ] La supervision des erreurs, de l'espace disque et des journaux est en place.

## Variables de production

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<clé-unique-et-secrète>
DJANGO_ALLOWED_HOSTS=archives.example.tg
DJANGO_CSRF_TRUSTED_ORIGINS=https://archives.example.tg
DJANGO_USE_PROXY_SSL_HEADER=True
DJANGO_USE_X_FORWARDED_HOST=True
```

Ne copiez jamais une clé de production dans un fichier suivi par Git, une capture d'écran ou un message.

## Processus de déploiement

```bash
python -m venv env
source env/bin/activate
pip install --requirement requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py test core audio_archive document_archive
python manage.py check --deploy
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
```

Placez Nginx devant Gunicorn pour terminer TLS et servir `/static/` et `/media/`. Adaptez le nombre de workers à la RAM, au CPU et à la charge observée. Sous Windows, utilisez un serveur WSGI compatible ou déployez l'application sur Linux ; Gunicorn est principalement destiné aux environnements Unix.

## Médias et traitements lourds

- Limitez la taille des uploads au niveau Nginx et Django selon la capacité serveur.
- Servez les gros audios avec prise en charge HTTP `Range` via le serveur de médias ; la vue actuelle charge le contenu en mémoire.
- Déplacez OCR et conversion FFmpeg dans une file de tâches (Celery/RQ + worker) si les fichiers deviennent volumineux ou les utilisateurs nombreux.
- Contrôlez l'espace libre : les uploads, ZIP, OCR et conversions génèrent des fichiers temporaires.

## Sauvegarde et restauration

Sauvegardez quotidiennement :

1. La base de données (SQLite : copie cohérente ; PostgreSQL : `pg_dump`).
2. Le répertoire `media/`.
3. Les variables de configuration stockées dans un gestionnaire de secrets sécurisé.

Testez régulièrement une restauration complète sur un environnement isolé. Une sauvegarde non testée ne constitue pas une stratégie de reprise.

## Maintenance

```bash
python manage.py showmigrations
python manage.py check
python manage.py check --deploy
python manage.py test core audio_archive document_archive
```

Surveillez la croissance de `AuditLog`, de `media/`, l'espace disque, les erreurs OCR/FFmpeg et les échecs de connexion. Définissez une durée de conservation et une procédure d'archivage des anciens journaux d'audit conformément aux besoins institutionnels.
