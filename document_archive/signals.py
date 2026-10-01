"""Audit des actions liées directement à un utilisateur."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import AuditLog
from document_archive.models import DocumentView, Favorite


# Les opérations de gestion sont journalisées par le middleware HTTP : il peut
# ainsi retenir l'utilisateur réellement à l'origine de la requête.
@receiver(post_save, sender=Favorite)
def log_favorite_add(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=instance.user,
            action='UPDATE',
            module='FAVORIS_DOCUMENT',
            description=f'Ajout aux favoris du document « {instance.document.title} »',
        )


@receiver(post_delete, sender=Favorite)
def log_favorite_remove(sender, instance, **kwargs):
    AuditLog.objects.create(
        user=instance.user,
        action='UPDATE',
        module='FAVORIS_DOCUMENT',
        description=f'Retrait des favoris du document « {instance.document.title} »',
    )


@receiver(post_save, sender=DocumentView)
def log_document_view(sender, instance, created, **kwargs):
    if created:
        AuditLog.objects.create(
            user=instance.user,
            action='CONSULT',
            module='DOCUMENT',
            description=f'Consultation du document « {instance.document.title} »',
        )
