from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST, require_http_methods

import os
from django.conf import settings

from document_archive.models import Favorite as DocumentFavorite
from document_archive.forms import CategoryForm as DocCategoryForm
from audio_archive.forms import CategoryForm as AudioCategoryForm
from .forms import UserForm
from document_archive.models import Document, Category as DocCategory, DocumentView, Favorite
from audio_archive.models import AudioFile, AudioView, Category as AudioCategory, Language
from core.models import AuditLog, UserProfile
import csv 
import json
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from .pagination import build_pagination

# Dépendances optionnelles pour PDF / DOCX (installer reportlab et python-docx)
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    SimpleDocTemplate = None

try:
    import docx
except ImportError:
    docx = None


URL_GLOBAL_CATEGORIES = 'global_manage_categories'
URL_MANAGE_USERS = 'manage_users'


def is_admin(user):
    return user.is_active and (user.is_superuser or user.groups.filter(name='Admin').exists())



# -------------------------------------------------------------------
#  Authentification & Dashboard
# -------------------------------------------------------------------

# Dictionnaire en mémoire ou champ UserProfile pour suivre les tentatives (max 5)
# Temporary lockout is disabled for now. Keep this setting for a future,
# database-backed lockout with an expiry instead of account deactivation.
# MAX_LOGIN_ATTEMPTS = 5

def _handle_failed_login(request, username):
    """Show a generic error without disabling the account."""
    # Previous lockout logic, intentionally retained but disabled:
    # user_obj = User.objects.filter(username=username).first()
    # failed_attempts = request.session.get('failed_attempts', 0) + 1
    # request.session['failed_attempts'] = failed_attempts
    # if user_obj and failed_attempts >= MAX_LOGIN_ATTEMPTS:
    #     user_obj.is_active = False
    #     user_obj.save(update_fields=['is_active'])
    messages.error(
        request, 
        "Nom d'utilisateur ou mot de passe incorrect."
    )
    
# Fonction utilitaire pour récupérer l'IP du client
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method != 'POST':
        return render(request, 'core/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')

    user = authenticate(request, username=username, password=password)

    if user is not None:
        # request.session['failed_attempts'] = 0  # only needed if lockout is restored
        login(request, user)
        
        # --- CREATION DU LOG D'AUDIT ---
        AuditLog.objects.create(
            user=user,
            action='LOGIN',
            module='AUTH',
            description=f"Connexion réussie de l'utilisateur {user.username}",
            ip_address=get_client_ip(request)
        )
        
        return redirect('dashboard')

    _handle_failed_login(request, username)
    return render(request, 'core/login.html')


@login_required
def logout_view(request):
    # --- CREATION DU LOG D'AUDIT AVANT LA DECONNEXION ---
    AuditLog.objects.create(
        user=request.user,
        action='LOGOUT',
        module='AUTH',
        description=f"Déconnexion de l'utilisateur {request.user.username}",
        ip_address=get_client_ip(request)
    )
    
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    if is_admin(user):
        # Calcul de la taille totale des fichiers téléversés dans MEDIA_ROOT
        total_size_bytes = 0
        media_path = settings.MEDIA_ROOT
        if os.path.exists(media_path):
            for dirpath, dirnames, filenames in os.walk(media_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size_bytes += os.path.getsize(fp)

        used_storage_mb = round(total_size_bytes / (1024 * 1024), 1)
        max_storage_gb = 5.0
        max_storage_mb = max_storage_gb * 1024
        storage_percent = round((used_storage_mb / max_storage_mb) * 100, 1) if max_storage_mb > 0 else 0

        context = {
            'role': 'ADMIN',
            'total_docs': Document.objects.count(),
            'total_audios': AudioFile.objects.count(),
            'total_archives': Document.objects.count() + AudioFile.objects.count(),
            'total_cats': DocCategory.objects.count() + AudioCategory.objects.count(),
            'total_users': User.objects.count(),
            'total_languages': Language.objects.filter(is_active=True).count(),
            'audio_listens': AudioView.objects.count(),
            'doc_views': DocumentView.objects.count(),
            'recent_documents': Document.objects.select_related('category', 'uploaded_by').order_by('-uploaded_at')[:6],
            'recent_audios': AudioFile.objects.select_related('category', 'uploaded_by').order_by('-uploaded_at')[:6],
            'recent_logs': AuditLog.objects.select_related('user').order_by('-timestamp')[:5],
            
            # Nouvelles variables calculées
            'used_storage_mb': used_storage_mb,
            'max_storage_gb': max_storage_gb,
            'storage_percent': storage_percent,
        }
        return render(request, 'core/dashboard_admin.html', context)
        
    # 2. Dashboard Archiviste
    elif user.groups.filter(name='Archiviste').exists() or getattr(user, 'profile', None) and user.profile.role == 'ARCHIVISTE':
        audio_listens = AudioView.objects.count()
        doc_views = DocumentView.objects.count()

        # Récupération des fichiers téléversés par l'archiviste
        my_audios = AudioFile.objects.filter(uploaded_by=user).select_related('category')
        my_docs = Document.objects.filter(uploaded_by=user).select_related('category')

        # Annotation / marquage du type de fichier
        my_recent_uploads = []
        for audio in my_audios:
            audio.file_type = 'audio'
            my_recent_uploads.append(audio)

        for doc in my_docs:
            doc.file_type = 'document'
            my_recent_uploads.append(doc)

        # Tri des fichiers combinés par date de téléversement (du plus récent au plus ancien)
        my_recent_uploads = sorted(
            my_recent_uploads,
            key=lambda item: item.uploaded_at,
            reverse=True
        )[:3]  # Prendre les 5 plus récents
        
        context = {
            'role': 'ARCHIVISTE',
            'total_archives': Document.objects.count() + AudioFile.objects.count(),
            'total_audios': AudioFile.objects.count(),
            'total_documents': Document.objects.count(),
            'audio_listens': audio_listens,
            'doc_views': doc_views,
            'my_audio_additions': my_audios.count(),
            'my_document_additions': my_docs.count(),
            'recent_audios': AudioFile.objects.select_related('category', 'uploaded_by').order_by('-uploaded_at')[:2],
            'recent_documents': Document.objects.select_related('category', 'uploaded_by').order_by('-uploaded_at')[:2],
            'my_recent_uploads': my_recent_uploads,
        }
        return render(request, 'core/dashboard_archiviste.html', context)
        
    # 3. Dashboard Journaliste / Lecteur
    total_audios = AudioFile.objects.count()
    total_documents = Document.objects.count()
    total_archives = total_audios + total_documents

    # Audios écoutés (somme des lectures)
    audio_listens = AudioView.objects.filter(user=user).count()

    # Compteurs spécifiques à l'utilisateur connecté
    my_document_views_count = DocumentView.objects.filter(user=user).count()
    my_audio_views_count = AudioView.objects.filter(user=user).count()
    views_total = my_document_views_count + my_audio_views_count

    # Si vous disposez de relations de favoris sur vos modèles (ex: AudioFavorite / DocumentFavorite)
    # Adaptez ces requêtes selon vos modèles réels :
    my_audio_favorites = getattr(user, 'audio_favorites', AudioFile.objects.none()).count() if hasattr(user, 'audio_favorites') else 0
    my_document_favorites = DocumentFavorite.objects.filter(user=user).count()
    favorite_total = my_audio_favorites + my_document_favorites

    # Vues récentes des documents par l'utilisateur
    my_recent_views = DocumentView.objects.filter(user=user).select_related('document').order_by('-viewed_at')[:3]
    my_recent_audio_views = AudioView.objects.filter(user=user).select_related('audio_file').order_by('-listened_at')[:3]

    context = {
        'role': 'JOURNALISTE',
        'total_archives': total_archives,
        'total_audios': total_audios,
        'total_documents': total_documents,
        'audio_listens': audio_listens,
        'my_audio_favorites': my_audio_favorites,
        'my_document_favorites': my_document_favorites,
        'my_recent_views': my_recent_views,
        'my_document_views_count': my_document_views_count,
        'my_audio_views_count': my_audio_views_count,
        'my_recent_audio_views': my_recent_audio_views,
        'favorite_total': favorite_total,
        'views_total': views_total,
    }
    return render(request, 'core/dashboard_journaliste.html', context)


# ==========================================
# VUE MES FAVORIS
# ==========================================
@login_required
def favoris_view(request):
    user = request.user

    # Récupération des favoris Audio (modèle Favorite de l'app audio_archive)
    audio_favorites = user.audio_favorites.select_related('audio_file').order_by('-added_at')

    # Récupération des favoris Documents
    document_favorites = DocumentFavorite.objects.filter(user=user).select_related('document').order_by('-added_at')

    audio_page_obj = Paginator(audio_favorites, 10).get_page(request.GET.get('audio_page'))
    document_page_obj = Paginator(document_favorites, 10).get_page(request.GET.get('document_page'))
    active_tab = 'documents' if request.GET.get('tab') == 'documents' else 'audios'

    # Compteurs
    my_audio_favorites_count = audio_page_obj.paginator.count
    my_document_favorites_count = document_page_obj.paginator.count
    favorite_total = my_audio_favorites_count + my_document_favorites_count

    context = {
        'favorite_audios': audio_page_obj.object_list,
        'favorite_documents': document_page_obj.object_list,
        'audio_page_obj': audio_page_obj,
        'document_page_obj': document_page_obj,
        'audio_pagination': build_pagination(request, audio_page_obj, 'audio_page', 'audios'),
        'document_pagination': build_pagination(request, document_page_obj, 'document_page', 'documents'),
        'active_favorites_tab': active_tab,
        'my_audio_favorites_count': my_audio_favorites_count,
        'my_document_favorites_count': my_document_favorites_count,
        'favorite_total': favorite_total,
    }
    return render(request, 'core/favoris.html', context)


#==========================================
# VUE HISTORIQUE DES CONSULTATIONS
#==========================================
@login_required
def historique_view(request):
    user = request.user

    # Recherche optionnelle dans l'historique
    query = request.GET.get('q', '').strip()

    # Récupération de l'historique des consultations documents et audios
    doc_history = DocumentView.objects.filter(user=user).select_related('document')
    audio_history = AudioView.objects.filter(user=user).select_related('audio_file')

    if query:
        doc_history = doc_history.filter(document__title__icontains=query)
        audio_history = audio_history.filter(audio_file__title__icontains=query)

    # Tri par date de consultation/écoute récente
    doc_history = doc_history.order_by('-viewed_at')
    audio_history = audio_history.order_by('-listened_at')

    doc_page_obj = Paginator(doc_history, 10).get_page(request.GET.get('doc_page'))
    audio_page_obj = Paginator(audio_history, 10).get_page(request.GET.get('audio_page'))
    total_doc_views = doc_page_obj.paginator.count
    total_audio_views = audio_page_obj.paginator.count
    total_history = total_doc_views + total_audio_views
    active_tab = 'documents' if request.GET.get('tab') == 'documents' else 'audios'

    context = {
        'doc_history': doc_page_obj.object_list,
        'audio_history': audio_page_obj.object_list,
        'doc_page_obj': doc_page_obj,
        'audio_page_obj': audio_page_obj,
        'audio_pagination': build_pagination(request, audio_page_obj, 'audio_page', 'audios'),
        'doc_pagination': build_pagination(request, doc_page_obj, 'doc_page', 'documents'),
        'active_history_tab': active_tab,
        'total_doc_views': total_doc_views,
        'total_audio_views': total_audio_views,
        'total_history': total_history,
        'current_query': query,
    }
    return render(request, 'core/historique.html', context)


@login_required
@require_POST
def clear_history(request):
    """Clear only the connected user's audio and document history."""
    DocumentView.objects.filter(user=request.user).delete()
    AudioView.objects.filter(user=request.user).delete()
    messages.success(request, "Votre historique de consultation et d'écoute a été effacé.")
    return redirect('historique')

# -------------------------------------------------------------------
#  Gestion centralisée des Catégories (Document & Audio)
# -------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def global_manage_categories(request):
    context = {
        'doc_categories': DocCategory.objects.all(),
        'audio_categories': AudioCategory.objects.all(),
        'doc_form': DocCategoryForm(),
        'audio_form': AudioCategoryForm(),
    }
    return render(request, 'core/category_management.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def add_doc_category(request):
    form = DocCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Catégorie de document ajoutée avec succès.")
    else:
        messages.error(request, "Erreur lors de l'ajout de la catégorie de document.")
    return redirect(URL_GLOBAL_CATEGORIES)


@login_required
@user_passes_test(is_admin)
@require_POST
def add_audio_category(request):
    form = AudioCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Catégorie audio ajoutée avec succès.")
    else:
        messages.error(request, "Erreur lors de l'ajout de la catégorie audio.")
    return redirect(URL_GLOBAL_CATEGORIES)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def doc_edit_category(request, pk):
    category = get_object_or_404(DocCategory, pk=pk)
    if request.method == 'POST':
        form = DocCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie de document mise à jour.')
            return redirect(URL_GLOBAL_CATEGORIES)
    else:
        form = DocCategoryForm(instance=category)
    return render(request, 'core/edit_category.html', {'form': form, 'category': category, 'type_label': 'Document'})


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def audio_edit_category(request, pk):
    category = get_object_or_404(AudioCategory, pk=pk)
    if request.method == 'POST':
        form = AudioCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie audio mise à jour.')
            return redirect(URL_GLOBAL_CATEGORIES)
    else:
        form = AudioCategoryForm(instance=category)
    return render(request, 'core/edit_category.html', {'form': form, 'category': category, 'type_label': 'Audio'})


@login_required
@user_passes_test(is_admin)
@require_POST
def doc_delete_category(request, pk):
    get_object_or_404(DocCategory, pk=pk).delete()
    messages.success(request, 'Catégorie de document supprimée.')
    return redirect(URL_GLOBAL_CATEGORIES)


@login_required
@user_passes_test(is_admin)
@require_POST
def audio_delete_category(request, pk):
    get_object_or_404(AudioCategory, pk=pk).delete()
    messages.success(request, 'Catégorie audio supprimée.')
    return redirect(URL_GLOBAL_CATEGORIES)


# -------------------------------------------------------------------
#  Gestion des Utilisateurs
# -------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def manage_users(request):
    users_query = User.objects.select_related('profile').all().order_by('username')
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')

    if query:
        users_query = users_query.filter(
            Q(username__icontains=query) | Q(email__icontains=query) |
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        )

    if role in {'ADMIN', 'ARCHIVISTE', 'JOURNALISTE', 'LECTEUR'}:
        users_query = users_query.filter(profile__role=role)

    if status == 'active':
        users_query = users_query.filter(is_active=True)
    elif status == 'inactive':
        users_query = users_query.filter(is_active=False)

    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Utilisateur créé avec succès.')
            return redirect(URL_MANAGE_USERS)
        messages.error(request, 'Le compte n’a pas été créé. Corrigez les champs signalés ci-dessous.')
    else:
        form = UserForm()

    page_obj = Paginator(users_query, 20).get_page(request.GET.get('page'))

    return render(request, 'core/user_management.html', {
        'users': page_obj.object_list,
        'page_obj': page_obj,
        'pagination': build_pagination(request, page_obj),
        'total_users': page_obj.paginator.count,
        'form': form,
        'current_query': query,
        'current_role': role,
        'current_status': status,
    })


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET", "POST"])
def edit_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Utilisateur mis à jour.')
            return redirect(URL_MANAGE_USERS)
        messages.error(request, 'Les modifications n’ont pas été enregistrées. Corrigez les champs signalés.')
    else:
        form = UserForm(instance=user_obj)
    return render(request, 'core/edit_user.html', {'form': form, 'user_obj': user_obj})


@login_required
@user_passes_test(is_admin)
def delete_user(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, 'Utilisateur supprimé.')
        return redirect(URL_MANAGE_USERS)
    return render(request, 'core/delete_user.html', {'user_obj': user_obj})



#-------------------------------------------------------------------
#  Journaux d'Audit
#-------------------------------------------------------------------


@login_required
@user_passes_test(is_admin)
def audit_log_list(request):
    """
    Vue d'administration pour la consultation et le filtrage avancé des journaux d'audit.
    """
    logs = AuditLog.objects.select_related('user').all()

    # --- Filtres ---
    q = request.GET.get('q', '').strip()
    action = request.GET.get('action', '')
    module = request.GET.get('module', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if q:
        logs = logs.filter(
            Q(description__icontains=q) | 
            Q(user__username__icontains=q) | 
            Q(ip_address__icontains=q)
        )
    if action:
        logs = logs.filter(action=action)
    if module:
        logs = logs.filter(module__icontains=module)
    if date_from:
        logs = logs.filter(timestamp__date__gte=parse_date(date_from))
    if date_to:
        logs = logs.filter(timestamp__date__lte=parse_date(date_to))

    # --- Gestion des Exports ---
    export_format = request.GET.get('export', '')
    if export_format:
        AuditLog.objects.create(
            user=request.user,
            action='CONSULT',
            module='AUDIT',
            description=f'Export du journal d’audit au format {export_format.upper()}.',
            ip_address=get_client_ip(request),
        )
        return _export_audit_logs(logs, export_format)

    # --- Pagination ---
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Modules uniques pour le filtre HTML
    modules_list = AuditLog.objects.values_list('module', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'action_choices': AuditLog.ACTION_CHOICES,
        'modules_list': modules_list,
        'current_q': q,
        'current_action': action,
        'current_module': module,
        'current_date_from': date_from,
        'current_date_to': date_to,
    }
    return render(request, 'core/audit_log_list.html', context)


def _export_audit_logs(queryset, export_format):
    """Générateur d'exportation pour le journal d'audit."""
    filename = "audit_journal_radio_kara"

    # Le format Word est volontairement retiré : seuls CSV, PDF et JSON sont pris en charge.
    if export_format == 'docx':
        return HttpResponse("L'export Word n'est plus disponible.", status=400)

    # Export JSON
    if export_format == 'json':
        data = list(queryset.values(
            'id', 'timestamp', 'user__username', 'action', 'module', 'description', 'ip_address'
        ))
        response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2, 'default': str})
        response['Content-Disposition'] = f'attachment; filename="{filename}.json"'
        return response

    # Export CSV (Lisible dans Excel)
    elif export_format == 'excel' or export_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID', 'Horodatage', 'Utilisateur', 'Action', 'Module', 'Description', 'Adresse IP'])

        for log in queryset:
            writer.writerow([
                log.id,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.username if log.user else 'Système',
                log.get_action_display(),
                log.module,
                log.description,
                log.ip_address or 'N/A'
            ])
        return response

    # Export DOCX (Word)
    elif export_format == 'docx' and docx:
        doc = docx.Document()
        doc.add_heading("Journal d'Audit - Radio Kara Archive", 0)
        table = doc.add_table(rows=1, cols=6)
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Date/Heure'
        hdr_cells[1].text = 'Utilisateur'
        hdr_cells[2].text = 'Action'
        hdr_cells[3].text = 'Module'
        hdr_cells[4].text = 'Description'
        hdr_cells[5].text = 'IP'

        for log in queryset[:500]: # Limité pour la performance du document
            row_cells = table.add_row().cells
            row_cells[0].text = log.timestamp.strftime('%Y-%m-%d %H:%M')
            row_cells[1].text = log.user.username if log.user else 'Système'
            row_cells[2].text = log.get_action_display()
            row_cells[3].text = log.module
            row_cells[4].text = log.description
            row_cells[5].text = log.ip_address or 'N/A'

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
        doc.save(response)
        return response

    # Export PDF (ReportLab)
    elif export_format == 'pdf' and SimpleDocTemplate:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        
        elements.append(Paragraph("<b>Journal d'Audit de Sécurité - Radio Kara</b>", styles['Title']))
        elements.append(Spacer(1, 12))

        data = [['Date/Heure', 'Utilisateur', 'Action', 'Module', 'Description', 'IP']]
        for log in queryset[:300]:
            data.append([
                log.timestamp.strftime('%d/%m/%Y %H:%M'),
                log.user.username if log.user else 'Système',
                log.get_action_display(),
                log.module,
                Paragraph(log.description[:60], styles['Normal']),
                log.ip_address or '-'
            ])

        t = Table(data, colWidths=[100, 80, 80, 80, 250, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#225A40')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(t)
        doc.build(elements)
        return response

    return HttpResponse("Format d'export non supporté ou module manquant.", status=400)
