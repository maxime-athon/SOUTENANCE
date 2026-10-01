"""Couverture minimale de l'audit pour toutes les opérations HTTP qui modifient des données."""

from .models import AuditLog
from .services import get_client_ip


class AuditMutationMiddleware:
    """Journalise les mutations non déjà couvertes par un log métier détaillé.

    Les vues qui créent un AuditLog précis restent prioritaires. Cette couche
    couvre les actions oubliées (notamment les formulaires d'administration),
    sans créer un doublon quand la vue a déjà produit son propre journal.
    """

    MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = getattr(request, 'user', None)
        initial_log_count = (
            AuditLog.objects.filter(user=actor).count()
            if request.method in self.MUTATING_METHODS and getattr(actor, 'is_authenticated', False)
            else None
        )

        response = self.get_response(request)

        if (
            initial_log_count is None
            or request.method not in self.MUTATING_METHODS
            or response.status_code >= 400
            or AuditLog.objects.filter(user=actor).count() > initial_log_count
        ):
            return response

        match = getattr(request, 'resolver_match', None)
        view_name = getattr(match, 'view_name', None) or request.path
        normalized_name = view_name.lower()
        if 'delete' in normalized_name:
            action = 'DELETE'
        elif any(word in normalized_name for word in ('add', 'create', 'upload')):
            action = 'CREATE'
        else:
            action = 'UPDATE'

        if normalized_name.startswith('document_archive:'):
            module = 'DOCUMENT'
        elif normalized_name.startswith('audio_archive:'):
            module = 'AUDIO'
        elif normalized_name.startswith('admin:'):
            module = 'ADMINISTRATION'
        else:
            module = 'CORE'

        AuditLog.objects.create(
            user=actor,
            action=action,
            module=module,
            description=f'Action {request.method} effectuée via « {view_name} ».',
            ip_address=get_client_ip(request),
        )
        return response
