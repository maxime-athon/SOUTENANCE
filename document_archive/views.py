from django.http import JsonResponse, HttpResponse
import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.core.files.base import ContentFile
from django.conf import settings
from django.db.models import Q, Count
from .models import Document, DocumentView, Favorite, Category
from .forms import DocumentForm, CategoryForm
from .models import Document, Favorite as DocumentFavorite
from core.forms import UserForm
from core.models import AuditLog
from core.services import get_client_ip
from audio_archive.models import AudioFile
import os
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import pytesseract
from datetime import timedelta
from django.utils import timezone
# Configuration optionnelle de Tesseract
# Pour les environement Linux, vous pouvez laisser cette configuration vide si Tesseract est dans le PATH.Sans quoi, Tesseract sera utilisé par défaut.Voici le mode d'integration de Tesseract pour Linux: En premier lieu, assurez-vous que Tesseract est installé sur votre système. Vous pouvez l'installer via le gestionnaire de paquets de votre distribution. Par exemple, sur Ubuntu/Debian, vous pouvez utiliser la commande suivante : sudo apt-get install tesseract-ocr. Ensuite, vous pouvez définir le chemin vers l'exécutable Tesseract dans votre fichier settings.py de Django. Par exemple : TESSERACT_CMD = '/usr/bin/tesseract'. Assurez-vous que le chemin correspond à l'emplacement réel de l'exécutable Tesseract sur votre système.
#pour Windows, vous pouvez définir le chemin complet vers l'exécutable Tesseract dans settings.py comme suit :
# TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if getattr(settings, 'TESSERACT_CMD', ''):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
from django.contrib import messages
from django.views.decorators.http import require_POST

# Importation des modèles de chaque application
from document_archive.models import Category as DocCategory
from audio_archive.models import Category as AudioCategory

# Importation des formulaires de chaque application
from document_archive.forms import CategoryForm as DocCategoryForm
from audio_archive.forms import CategoryForm as AudioCategoryForm

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
# views.py
from django.shortcuts import render
from django.db.models import Q
from .models import Document, Category  # Adaptez l'import de votre modèle Categorie selon votre projet

from django.shortcuts import render
from django.db.models import Q
from .models import Document, Category



# Configuration optionnelle de Tesseract pour les environnements Windows/Spécifiques
if getattr(settings, 'TESSERACT_CMD', ''):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


# ==============================================================================
# 1. HELPERS & FONCTIONS UTILITAIRES (Traitements de fichiers & OCR)
# ==============================================================================

def run_ocr_on_document(document):
    """
    Exécute automatiquement l'OCR sur un document (PDF ou Image)
    et enregistre le texte extrait dans le champ `ocr_text`.
    """
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, str(document.file))
        text = ""

        if document.file.name.lower().endswith('.pdf'):
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif document.file.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang='fra+eng')

        if text.strip():
            document.ocr_text = text
            document.save(update_fields=['ocr_text'])
    except Exception as e:
        print(f"Erreur OCR sur le document ID {document.id}: {e}")


def document_ocr_detail(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)

    ocr_text = document.ocr_text or ""

    # Nombre de caractères envoyés à chaque requête
    chunk_size = 20000

    # Position de départ demandée par le navigateur
    try:
        start = int(request.GET.get('start', 0))
    except (TypeError, ValueError):
        start = 0

    # Sécurité : on évite les positions négatives
    start = max(start, 0)

    # Si on dépasse la taille du texte
    if start >= len(ocr_text):
        return JsonResponse({
            'id': document.id,
            'title': document.title,
            'content': '',
            'start': start,
            'end': start,
            'total': len(ocr_text),
            'has_more': False,
        })

    end = min(start + chunk_size, len(ocr_text))

    return JsonResponse({
        'id': document.id,
        'title': document.title,
        'content': ocr_text[start:end],
        'start': start,
        'end': end,
        'total': len(ocr_text),
        'has_more': end < len(ocr_text),
    })
def compress_pdf(file_path):
    """Reconstruite et compresse un fichier PDF via PyPDF2."""
    try:
        reader = PdfReader(file_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buffer = BytesIO()
        writer.write(buffer)
        filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_compressed.pdf"
        return ContentFile(buffer.getvalue(), name=filename)
    except Exception as e:
        print(f"Erreur lors de la compression PDF: {e}")
        return None


def generate_thumbnail(file_path):
    """Génère une miniature au format JPEG (200x200) pour les images."""
    if file_path.lower().endswith('.pdf'):
        return None

    try:
        with Image.open(file_path) as source:
            image = source.convert('RGB')
            image.thumbnail((200, 200))
            buffer = BytesIO()
            image.save(buffer, 'JPEG')
        filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_thumbnail.jpg"
        return ContentFile(buffer.getvalue(), name=filename)
    except Exception as e:
        print(f"Erreur lors de la génération de la miniature: {e}")
        return None


# ==============================================================================
# 2. GESTION DES DOCUMENTS (CRUD & Consultation)
# ==============================================================================

@login_required
def document_list(request):
    
    if not (request.user.is_staff or request.user.is_superuser):
        messages.info(request, "Cette page est réservée à la gestion des archives. Redirection vers votre tableau de bord.")
        return redirect('search_document')
    
    """Affiche la liste complète des documents filtrable par catégorie."""
    documents = Document.objects.all().order_by('-uploaded_at')
    categories = Category.objects.all()
    category_id = request.GET.get('category')

    if category_id:
        documents = documents.filter(category_id=category_id)

    can_edit = request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists() or request.user.is_superuser
    
    return render(request, 'document_archive/document_list.html', {
        'documents': documents,
        'categories': categories,
        'can_edit': can_edit
    })


@login_required
def document_detail(request, pk):
    """Affiche le détail d'un document et enregistre l'historique de vue."""
    document = get_object_or_404(Document, pk=pk)
    tags_list = [tag.strip() for tag in document.tags.split(',')] if document.tags else []

    # Enregistrer la consultation dans l'historique
    DocumentView.objects.create(
    user=request.user,
    document=document
)

    can_edit = request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists()
    is_favorite = Favorite.objects.filter(user=request.user, document=document).exists()

    return render(request, 'document_archive/document_detail.html', {
        'document': document,
        'tags_list': tags_list,
        'is_favorite': is_favorite,
        'can_edit': can_edit
    })


@login_required
def upload_document(request):
    """Téléverse un document, applique la compression, la miniature et l'OCR."""
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists()):
        messages.error(request, 'Permission refusée.')
        return redirect('document_list')

    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()

            # 1. Compression PDF
            if doc.file.name.lower().endswith('.pdf'):
                compressed_file = compress_pdf(doc.file.path)
                if compressed_file:
                    doc.file.save(compressed_file.name, compressed_file, save=False)
                doc.compressed = True
                doc.save()
            else:
                doc.compressed = False
                doc.save(update_fields=['compressed'])

            # 2. Génération de miniature pour images
            if doc.file.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                thumbnail = generate_thumbnail(doc.file.path)
                if thumbnail:
                    doc.thumbnail.save(thumbnail.name, thumbnail, save=False)
                doc.save()

            # 3. Traitement OCR
            run_ocr_on_document(doc)
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='DOCUMENT',
                description=f'Téléversement et indexation du document « {doc.title} »',
                ip_address=get_client_ip(request),
            )

            messages.success(request, 'Document téléversé et indexé avec succès !')
            return redirect('document_list')
    else:
        form = DocumentForm()

    return render(request, 'document_archive/upload.html', {'form': form})


@login_required
def edit_document(request, pk):
    """Permet d'éditer les métadonnées d'un document existant."""
    if not (request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists()):
        messages.error(request, 'Permission refusée.')
        return redirect('document_list')

    document = get_object_or_404(Document, pk=pk)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='DOCUMENT',
                description=f'Modification du document « {document.title} »',
                ip_address=get_client_ip(request),
            )
            messages.success(request, 'Document mis à jour avec succès.')
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentForm(instance=document)

    return render(request, 'document_archive/edit_document.html', {'form': form})


@login_required
def delete_document(request, pk):
    """Supprime un document du système."""
    if not (request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists()):
        messages.error(request, 'Permission refusée.')
        return redirect('document_list')

    document = get_object_or_404(Document, pk=pk)
    if request.method == 'POST':
        title = document.title
        document.delete()
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            module='DOCUMENT',
            description=f'Suppression du document « {title} »',
            ip_address=get_client_ip(request),
        )
        messages.success(request, 'Document supprimé avec succès.')
        return redirect('document_list')

    return render(request, 'document_archive/delete_document.html', {'document': document})


# ==============================================================================
# 3. RECHERCHE & OCR
# ==============================================================================

@login_required
def search_document(request):
    """Moteur de recherche avancée filtrant par texte, OCR, catégorie et date."""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    ocr_only = request.GET.get('ocr_only', '')

    documents = Document.objects.all().order_by('-uploaded_at')

    if query:
        documents = documents.filter(
            Q(ocr_text__icontains=query) |
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(author__icontains=query) |
            Q(tags__icontains=query)
        )

    if category_id:
        documents = documents.filter(category_id=category_id)
    if date_from:
        documents = documents.filter(uploaded_at__gte=date_from)
    if date_to:
        documents = documents.filter(uploaded_at__lte=date_to)
    if ocr_only == '1':
        documents = documents.exclude(ocr_text__isnull=True).exclude(ocr_text__exact='')

    user_fav_ids = set(Favorite.objects.filter(user=request.user).values_list('document_id', flat=True))
    for doc in documents:
        doc.is_favorite_user = doc.id in user_fav_ids

    categories = Category.objects.all()

    return render(request, 'core/search_document.html', {
        'documents': documents,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'date_from': date_from,
        'date_to': date_to,
        'ocr_only': ocr_only,
    })


@login_required
def extract_ocr(request, pk):
    """Relance manuellement la reconnaissance de texte OCR sur un document."""
    document = get_object_or_404(Document, pk=pk)

    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Archiviste']).exists()):
        messages.error(request, 'Permission refusée.')
        return redirect('document_detail', pk=pk)
    
    

    try:
        run_ocr_on_document(document)
        AuditLog.objects.create(
            user=request.user,
            action='UPDATE',
            module='DOCUMENT',
            description=f'Relance de l’OCR pour le document « {document.title} »',
            ip_address=get_client_ip(request),
        )
        messages.success(request, 'Texte OCR extrait et mis à jour avec succès.')
    except Exception as e:
        messages.error(request, f"Erreur lors de l'extraction OCR: {str(e)}")

    return redirect('document_detail', pk=pk)

@login_required
@require_POST
def save_ocr(request, doc_id):
    """Enregistre une correction manuelle du texte OCR."""

    # Seuls les utilisateurs autorisés à modifier les documents
    # peuvent corriger le texte OCR.
    if not (
        request.user.is_superuser
        or request.user.is_staff
        or request.user.groups.filter(
            name__in=['Admin', 'Archiviste']
        ).exists()
    ):
        return JsonResponse({
            'success': False,
            'message': 'Permission refusée.'
        }, status=403)

    document = get_object_or_404(Document, pk=doc_id)

    # Récupération du texte OCR envoyé par le formulaire
    new_ocr_text = request.POST.get('ocr_text')

    if new_ocr_text is None:
        return JsonResponse({
            'success': False,
            'message': 'Aucun texte OCR fourni.'
        }, status=400)

    # Enregistrement de la correction
    document.ocr_text = new_ocr_text
    document.save(update_fields=['ocr_text'])

    # Journalisation de la modification
    AuditLog.objects.create(
        user=request.user,
        action='UPDATE',
        module='DOCUMENT',
        description=f'Modification manuelle de l’OCR du document « {document.title} »',
        ip_address=get_client_ip(request),
    )

    messages.success(
        request,
        'Texte OCR corrigé et enregistré avec succès.'
    )

    return redirect('document_detail', pk=document.pk)

# ==============================================================================
# 4. FAVORIS & HISTORIQUE
# ==============================================================================

@login_required
@require_POST
def toggle_document_favorite(request, pk):
    """Ajoute ou retire un document des favoris de l'utilisateur (Requête AJAX/JSON)."""
    document = get_object_or_404(Document, id=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, document=document)

    if not created:
        fav.delete()
        is_favorite = False
    else:
        is_favorite = True

    return JsonResponse({'is_favorite': is_favorite})


@login_required
def favorites(request):
    """Affiche la liste des documents favoris de l'utilisateur connecté."""
    favs = Favorite.objects.filter(user=request.user).select_related('document')
    documents = [f.document for f in favs]
    return render(request, 'core/favorites.html', {'documents': documents})


@login_required
def recent_views(request):
    """Affiche l'historique des 20 derniers documents consultés."""
    views_history = DocumentView.objects.filter(user=request.user).select_related('document').order_by('-viewed_at')[:20]
    documents = [v.document for v in views_history]
    return render(request, 'core/recent_views.html', {'documents': documents})


# ==============================================================================
# 5. GESTION CENTRALISÉE DES CATÉGORIES (Document & Audio)
# ==============================================================================

@login_required
def global_manage_categories(request):
    """Vue principale affichant les catégories de documents et d'audio."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        messages.error(request, "Permission refusée.")
        return redirect('dashboard')

    context = {
        'doc_categories': DocCategory.objects.all(),
        'audio_categories': AudioCategory.objects.all(),
        'doc_form': DocCategoryForm(),
        'audio_form': AudioCategoryForm(),
    }
    return render(request, 'categories/category_management.html', context)


@login_required
@require_POST
def add_doc_category(request):
    """Ajoute une catégorie de document."""
    form = DocCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Catégorie de document ajoutée avec succès.")
    else:
        messages.error(request, "Erreur lors de l'ajout de la catégorie.")
    return redirect('global_manage_categories')


@login_required
@require_POST
def add_audio_category(request):
    """Ajoute une catégorie audio."""
    form = AudioCategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Catégorie audio ajoutée avec succès.")
    else:
        messages.error(request, "Erreur lors de l'ajout de la catégorie audio.")
    return redirect('global_manage_categories')


@login_required
def doc_edit_category(request, pk):
    """Édition d'une catégorie de document."""
    category = get_object_or_404(DocCategory, pk=pk)
    if request.method == 'POST':
        form = DocCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie mise à jour.')
            return redirect('global_manage_categories')
    else:
        form = DocCategoryForm(instance=category)
    return render(request, 'categories/edit_category.html', {
        'form': form,
        'category': category,
        'type_label': 'Document'
    })


@login_required
def audio_edit_category(request, pk):
    """Édition d'une catégorie audio."""
    category = get_object_or_404(AudioCategory, pk=pk)
    if request.method == 'POST':
        form = AudioCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie audio mise à jour.')
            return redirect('global_manage_categories')
    else:
        form = AudioCategoryForm(instance=category)
    return render(request, 'categories/edit_category.html', {
        'form': form,
        'category': category,
        'type_label': 'Audio'
    })


@login_required
@require_POST
def doc_delete_category(request, pk):
    """Suppression d'une catégorie de document."""
    category = get_object_or_404(DocCategory, pk=pk)
    category.delete()
    messages.success(request, 'Catégorie supprimée.')
    return redirect('global_manage_categories')


@login_required
@require_POST
def audio_delete_category(request, pk):
    """Suppression d'une catégorie audio."""
    category = get_object_or_404(AudioCategory, pk=pk)
    category.delete()
    messages.success(request, 'Catégorie audio supprimée.')
    return redirect('global_manage_categories')


# ==============================================================================
# 6. STATISTIQUES, EXPORT & API DOCS
# ==============================================================================

@login_required
def statistics(request):
    """Tableau de bord statistique de l'archivage."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('dashboard')

    total_docs = Document.objects.count()
    total_cats = Category.objects.count()
    total_users = User.objects.count()

    category_stats = []
    for category in Category.objects.all():
        doc_count = Document.objects.filter(category=category).count()
        category_stats.append({
            'name': category.name,
            'count': doc_count,
            'percentage': (doc_count / total_docs * 100) if total_docs > 0 else 0
        })

    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_docs = Document.objects.filter(uploaded_at__gte=thirty_days_ago).count()
    recent_views_count = DocumentView.objects.filter(viewed_at__gte=thirty_days_ago).count()

    popular_docs = Document.objects.annotate(view_count=Count('documentview')).order_by('-view_count')[:10]
    favorite_docs = Document.objects.annotate(favorite_count=Count('favorite')).order_by('-favorite_count')[:10]

    return render(request, 'core/statistics.html', {
        'total_docs': total_docs,
        'total_cats': total_cats,
        'total_users': total_users,
        'category_stats': category_stats,
        'recent_docs': recent_docs,
        'recent_views': recent_views_count,
        'popular_docs': popular_docs,
        'favorite_docs': favorite_docs,
    })


@login_required
def export_data(request):
    """Exporte les données des documents au format CSV ou JSON."""
    if not (request.user.is_superuser or request.user.groups.filter(name='Admin').exists()):
        messages.error(request, 'Accès réservé aux administrateurs.')
        return redirect('dashboard')

    format_type = request.GET.get('format', 'csv')

    if format_type == 'json':
        documents = Document.objects.select_related('category', 'uploaded_by').all()
        data = {
            'documents': [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'author': doc.author,
                    'description': doc.description,
                    'category': doc.category.name if doc.category else None,
                    'tags': doc.tags,
                    'uploaded_by': doc.uploaded_by.username if doc.uploaded_by else None,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'compressed': doc.compressed,
                    'ocr_text': doc.ocr_text,
                } for doc in documents
            ],
            'categories': [
                {
                    'id': cat.id,
                    'name': cat.name,
                    'description': getattr(cat, 'description', ''),
                } for cat in Category.objects.all()
            ]
        }
        response = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="archive_export.json"'
        return response

    # Export CSV par défaut
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="archive_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Titre', 'Auteur', 'Description', 'Catégorie', 'Tags', 'Téléchargé par', 'Date d\'archivage', 'Compressé', 'Texte OCR'])

    documents = Document.objects.select_related('category', 'uploaded_by').all()
    for doc in documents:
        writer.writerow([
            doc.id,
            doc.title,
            doc.author or '',
            doc.description or '',
            doc.category.name if doc.category else '',
            doc.tags or '',
            doc.uploaded_by.username if doc.uploaded_by else '',
            doc.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Oui' if doc.compressed else 'Non',
            doc.ocr_text or '',
        ])

    return response


@login_required
def api_documentation(request):
    """Affiche la page d'aide et de documentation pour l'API REST."""
    return render(request, 'document_archive/api_docs.html')
