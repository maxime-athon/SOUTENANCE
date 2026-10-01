from django.apps import AppConfig

class DocumentArchiveConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'document_archive'

    def ready(self):
        import document_archive.signals  # Import the signals module to register signal handlers