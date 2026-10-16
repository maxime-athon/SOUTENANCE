import io
import os
import zipfile
import mimetypes
import subprocess 
import tempfile

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db.models import Q, F
from django.views.decorators.http import require_POST, require_http_methods

from .models import Category, Language, AudioFile, AudioView, Favorite
from .forms import CategoryForm, AudioFileForm
from core.forms import UserForm
from core.models import AuditLog
from core.services import (
    get_client_ip, 
    generate_clean_title, 
    extract_audio_duration
)
from core.pagination import build_pagination


def is_staff_or_admin(user):
    return user.is_active and (user.is_staff or user.is_superuser)


# -------------------------------------------------------------------
#  Service Interne d'Extraction & Traitement Automatique
# -------------------------------------------------------------------

def _extract_and_populate_metadata(audio_instance, uploaded_file):
    """
    Traite le fichier téléversé pour extraire et renseigner automatiquement 
    les métadonnées (durée, titre automatique, etc.) avant sauvegarde.
    Agrandir cette fonction pour ajouter de futurs services d'extraction.
    """
    if not uploaded_file:
        return

    # 1. Génération automatique du titre si non renseigné
    if not audio_instance.title:
        audio_instance.title = generate_clean_title(uploaded_file.name)

    # 2. Extraction automatique de la durée
    tmp_path = None
    try:
        # Sauvegarde temporaire en mémoire/disque pour analyser le canal binaire
        uploaded_file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        extracted_duration = extract_audio_duration(tmp_path)
        if extracted_duration:
            audio_instance.duration = extracted_duration

    except Exception:
        # Sécurité pour ne pas bloquer l'upload si mutagen/l'extraction échoue
        pass
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        uploaded_file.seek(0)


# -------------------------------------------------------------------
#  Favoris & Recherche (AJAX / Client Public)
# -------------------------------------------------------------------

@login_required
@require_POST
def toggle_favorite(request, audio_id):
    audio = get_object_or_404(AudioFile, id=audio_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, audio_file=audio)
    
    if not created:
        fav.delete()
        is_fav = False
        description = f'Retrait des favoris de l\'archive audio "{audio.title}"'
    else:
        is_fav = True
        description = f'Ajout aux favoris de l\'archive audio "{audio.title}"'

    AuditLog.objects.create(
        user=request.user,
        action='UPDATE',
        module='AUDIO',
        description=description,
        ip_address=get_client_ip(request),
    )
        
    return JsonResponse({'is_favorite': is_fav})


@login_required
def check_favorite(request, audio_id):
    is_fav = Favorite.objects.filter(user=request.user, audio_file_id=audio_id).exists()
    return JsonResponse({'is_favorite': is_fav})


@login_required
def audio_list(request):
    """Liste globale des archives sonores paginée."""
    queryset = AudioFile.objects.select_related('category', 'language', 'uploaded_by').order_by('-uploaded_at')
    
    paginator = Paginator(queryset, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'audio_archive/audio_list.html', {
        'page_obj': page_obj,
        'pagination': build_pagination(request, page_obj),
        'categories': Category.objects.all(),
        'languages': Language.objects.filter(is_active=True),
    })


@login_required
def search_audio(request):
    """Moteur de recherche avancé multi-critères."""
    raw_query = request.GET.get('q', '')
    query = raw_query.strip()
    
    category_id = request.GET.get('category', '')
    language_id = request.GET.get('language', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    audios = AudioFile.objects.select_related('category', 'language', 'uploaded_by').all()

    if query:
        audios = audios.filter(
            Q(title__icontains=query) |
            Q(subtitle__icontains=query) |
            Q(description__icontains=query) |
            Q(producer__icontains=query) |
            Q(band_number__icontains=query) |
            Q(recording_number__icontains=query)
        )

    if category_id:
        audios = audios.filter(category_id=category_id)
    if language_id:
        audios = audios.filter(language_id=language_id)
    if date_from:
        audios = audios.filter(broadcast_date__gte=date_from)
    if date_to:
        audios = audios.filter(broadcast_date__lte=date_to)

    paginator = Paginator(audios.order_by('-broadcast_date'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'pagination': build_pagination(request, page_obj),
        'audios': page_obj,
        'categories': Category.objects.all(),
        'languages': Language.objects.filter(is_active=True),
        'query': query,
        'selected_category': category_id,
        'selected_language': language_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'audio_archive/search_audio.html', context)


# -------------------------------------------------------------------
#  Consultation & Catégories
# -------------------------------------------------------------------

@login_required
def categories(request):
    all_categories = Category.objects.all()
    return render(request, 'categories/categories.html', {'categories': all_categories})


@login_required
def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    audio_files = AudioFile.objects.filter(category=category).select_related('language', 'uploaded_by')
    
    paginator = Paginator(audio_files, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'categories/category_detail.html', {
        'category': category,
        'page_obj': page_obj,
        'pagination': build_pagination(request, page_obj),
        'audio_files': page_obj.object_list,
    })


@login_required
def audio_detail(request, audio_id):
    audio = get_object_or_404(AudioFile.objects.select_related('category', 'language', 'uploaded_by'), id=audio_id)
    is_fav = Favorite.objects.filter(user=request.user, audio_file=audio).exists()
    return render(request, 'audio_archive/audio_detail.html', {
        'audio': audio,
        'is_favorite': is_fav
    })


# -------------------------------------------------------------------
#  Streaming & Téléchargement
# -------------------------------------------------------------------

@login_required
def stream_audio(request, audio_id):
    audio = get_object_or_404(AudioFile, id=audio_id)
    if not audio.file:
        raise Http404("Fichier sonore inexistant.")

    content, filename, ctype = decompress_file(audio.file)
    total_size = len(content)
    content_type = ctype or mimetypes.guess_type(filename)[0] or 'audio/mpeg'
    range_header = request.headers.get('Range')

    # Le lecteur HTML5 demande des plages d'octets lorsqu'on avance dans la piste.
    # Sans réponse 206/Content-Range, certains navigateurs redémarrent le flux au début.
    response_status = 200
    response_headers = {'Accept-Ranges': 'bytes'}
    body = content
    if range_header:
        try:
            unit, range_value = range_header.strip().split('=', 1)
            if unit != 'bytes' or ',' in range_value:
                raise ValueError
            first, last = range_value.split('-', 1)
            if first:
                start = int(first)
                end = int(last) if last else total_size - 1
            else:
                suffix_length = int(last)
                if suffix_length <= 0:
                    raise ValueError
                start = max(0, total_size - suffix_length)
                end = total_size - 1
            if start < 0 or start >= total_size or end < start:
                raise IndexError
            end = min(end, total_size - 1)
            body = content[start:end + 1]
            response_status = 206
            response_headers['Content-Range'] = f'bytes {start}-{end}/{total_size}'
        except IndexError:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{total_size}'
            response['Accept-Ranges'] = 'bytes'
            return response
        except (ValueError, TypeError):
            # Ignore malformed or unsupported Range headers and return the full file.
            pass

    response = HttpResponse(body, status=response_status, content_type=content_type)
    for header, value in response_headers.items():
        response[header] = value
    response['Content-Length'] = str(len(body))

    if response_status == 200 or response_headers.get('Content-Range', '').startswith('bytes 0-'):
        AudioFile.objects.filter(id=audio_id).update(play_count=F('play_count') + 1)
        AudioView.objects.create(user=request.user, audio_file=audio)
        AuditLog.objects.create(
            user=request.user,
            action='CONSULT',
            module='AUDIO',
            description=f'Écoute de l\'archive audio "{audio.title}"',
            ip_address=get_client_ip(request),
        )

    return response


@login_required
def download_audio(request, audio_id):
    audio = get_object_or_404(AudioFile, id=audio_id)
    if not audio.file:
        raise Http404("Fichier sonore inexistant.")

    content, filename, ctype = decompress_file(audio.file)
    
    if not filename.lower().endswith('.mp3'):
        content = convert_to_mp3(content, filename)
        filename = os.path.splitext(filename)[0] + '.mp3'
    
    AuditLog.objects.create(
        user=request.user,
        action='CONSULT',
        module='audio_archive',
        description=f'Téléchargement de l\'archive audio "{audio.title}"',
        ip_address=get_client_ip(request)
    )

    response = HttpResponse(content, content_type='audio/mpeg')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# -------------------------------------------------------------------
#  Gestion Staff (CRUD Audio & Traitements)
# -------------------------------------------------------------------

@login_required
@user_passes_test(is_staff_or_admin)
def audio_management(request):
    audios = AudioFile.objects.select_related('category', 'language', 'uploaded_by').order_by('-uploaded_at')
    
    paginator = Paginator(audios, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'audio_archive/audio_management.html', {
        'page_obj': page_obj,
        'pagination': build_pagination(request, page_obj),
        'audio_files': page_obj.object_list,
        'total_audio_files': page_obj.paginator.count,
        'categories': Category.objects.all()
    })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from .models import AudioFile
from .forms import AudioFileForm
from core.models import AuditLog
from core.services import get_client_ip

def is_staff_or_admin(user):
    return user.is_active and (user.is_staff or user.is_superuser)

@login_required
@user_passes_test(is_staff_or_admin)
@require_http_methods(["GET", "POST"])
def add_audio(request):
    # Gestion du mode édition transféré (studio / enregistrement micro)
    edit_id = request.GET.get('edit_id') or request.POST.get('edit_id')
    audio_instance = None
    is_editing = False

    if edit_id:
        audio_instance = get_object_or_404(AudioFile, id=edit_id)
        is_editing = True

    if request.method == 'POST':
        # Instanciation dynamique avec ou sans objet existant
        form = AudioFileForm(request.POST, request.FILES, instance=audio_instance)
        if form.is_valid():
            uploaded_file = request.FILES.get('file')
            audio = form.save(commit=False)
            
            # Ne définit l'auteur que lors d'une création
            if not is_editing:
                audio.uploaded_by = request.user
            
            # Traitement du fichier audio
            if uploaded_file:
                _extract_and_populate_metadata(audio, uploaded_file)
                audio.file = compress_upload(uploaded_file)
            elif is_editing and audio_instance:
                # Préservation du fichier audio existant si aucun nouveau n'a été fourni dans le formulaire
                audio.file = audio_instance.file

            audio.save()

            action_type = 'UPDATE' if is_editing else 'CREATE'
            action_label = 'Modification' if is_editing else 'Ajout'
            msg_text = f'L\'archive "{audio.title}" a été mise à jour.' if is_editing else f'L\'archive "{audio.title}" a été ajoutée avec succès.'
            
            AuditLog.objects.create(
                user=request.user,
                action=action_type,
                module='audio_archive',
                description=f'{action_label} de l\'archive audio "{audio.title}"',
                ip_address=get_client_ip(request)
            )
            messages.success(request, msg_text)
            return redirect('audio_management')
        else:
            messages.error(request, "Veuillez corriger les erreurs indiquées ci-dessous.")
    else:
        form = AudioFileForm(instance=audio_instance)

    # Récupération de l'URL du flux si un fichier d'origine est présent
    audio_stream_url = None
    if is_editing and audio_instance and audio_instance.file:
        audio_stream_url = reverse('stream_audio', kwargs={'audio_id': audio_instance.id})

    return render(request, 'audio_archive/add_audio.html', {
        'form': form,
        'audio': audio_instance,
        'is_editing': is_editing,
        'audio_stream_url': audio_stream_url
    })

@login_required
@user_passes_test(is_staff_or_admin)
@require_http_methods(["GET", "POST"])
def edit_audio(request, audio_id):
    # Redirection propre vers le studio add_audio si appel du mode micro
    if request.GET.get('mode') == 'mic':
        return redirect(f"{reverse('add_audio')}?edit_id={audio_id}&autostart=mic")

    audio = get_object_or_404(AudioFile, id=audio_id)
    
    if request.method == 'POST':
        files = request.FILES if ('file' in request.FILES and request.FILES['file']) else None
        form = AudioFileForm(request.POST, files, instance=audio)
        
        if form.is_valid():
            audio_instance = form.save(commit=False)
            
            if files and 'file' in request.FILES:
                uploaded_file = request.FILES['file']
                _extract_and_populate_metadata(audio_instance, uploaded_file)
                compressed = compress_upload(uploaded_file)
                audio_instance.file.save(compressed.name, compressed, save=False)
            else:
                audio_instance.file = audio.file
                
            audio_instance.save()

            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='audio_archive',
                description=f'Modification de l\'archive audio "{audio.title}"',
                ip_address=get_client_ip(request)
            )
            messages.success(request, f'L\'archive "{audio.title}" a été mise à jour.')
            return redirect('audio_management')
        else:
            messages.error(request, "Veuillez corriger les erreurs indiquées ci-dessous.")
    else:
        form = AudioFileForm(instance=audio)
        
    audio_stream_url = reverse('stream_audio', kwargs={'audio_id': audio.id}) if audio.file else None

    return render(request, 'audio_archive/edit_audio.html', {
        'form': form, 
        'audio': audio,
        'audio_url': audio_stream_url
    })

@login_required
@user_passes_test(is_staff_or_admin)
@require_http_methods(["GET", "POST"])
def delete_audio(request, audio_id):
    audio = get_object_or_404(AudioFile, id=audio_id)

    if request.method == 'POST':
        title = audio.title
        if audio.file:
            audio.file.delete(save=False)
            
        audio.delete()
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            module='audio_archive',
            description=f'Suppression de l\'archive "{title}"',
            ip_address=get_client_ip(request)
        )
        messages.success(request, f'L\'élément audio "{title}" a été supprimé.')
        return redirect('audio_management')

    return render(request, 'audio_archive/delete_confirm.html', {'audio': audio})


@login_required
@user_passes_test(is_staff_or_admin)
@require_POST
def delete_bulk_audio(request):
    audio_ids = request.POST.getlist('audio_ids')
    if audio_ids:
        deleted_count, _ = AudioFile.objects.filter(id__in=audio_ids).delete()
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            module='audio_archive',
            description=f'Suppression en masse de {deleted_count} archive(s) audio',
            ip_address=get_client_ip(request)
        )
        messages.success(request, f'{deleted_count} archive(s) audio supprimée(s).')
    return redirect('audio_management')


@login_required
@user_passes_test(is_staff_or_admin)
@require_POST
def normalize_bulk_audio(request):
    audio_ids = request.POST.getlist('audio_ids')
    if audio_ids:
        updated_count = AudioFile.objects.filter(id__in=audio_ids).update(play_count=0, is_featured=False)
        AuditLog.objects.create(
            user=request.user,
            action='UPDATE',
            module='audio_archive',
            description=f'Réinitialisation des compteurs pour {updated_count} archive(s) audio',
            ip_address=get_client_ip(request)
        )
        messages.success(request, f'{updated_count} archive(s) réinitialisée(s).')
    return redirect('audio_management')


# -------------------------------------------------------------------
#  Gestion des Catégories
# -------------------------------------------------------------------

@login_required
@user_passes_test(is_staff_or_admin)
def category_management(request):
    categories_list = Category.objects.all()
    return render(request, 'categories/category_management.html', {'categories': categories_list})


@login_required
@user_passes_test(is_staff_or_admin)
@require_http_methods(["GET", "POST"])
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='audio_archive',
                description=f'Création de la catégorie audio "{category.name}"',
                ip_address=get_client_ip(request)
            )
            messages.success(request, 'Catégorie créée avec succès.')
            return redirect('audio_category_management')
    else:
        form = CategoryForm()
    return render(request, 'categories/add_category.html', {'form': form})


@login_required
@user_passes_test(is_staff_or_admin)
@require_http_methods(["GET", "POST"])
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='audio_archive',
                description=f'Modification de la catégorie audio "{category.name}"',
                ip_address=get_client_ip(request)
            )
            messages.success(request, 'Catégorie mise à jour.')
            return redirect('audio_category_management')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'categories/edit_category.html', {'form': form, 'category': category})


@login_required
@user_passes_test(is_staff_or_admin)
@require_POST
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    name = category.name
    category.delete()
    AuditLog.objects.create(
        user=request.user,
        action='DELETE',
        module='audio_archive',
        description=f'Suppression de la catégorie audio "{name}"',
        ip_address=get_client_ip(request)
    )
    messages.success(request, 'Catégorie supprimée.')
    return redirect('audio_category_management')


@login_required
def audit_logs(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
    logs = AuditLog.objects.select_related('user').all()
    return render(request, 'core/audit_logs.html', {'logs': logs})


# -------------------------------------------------------------------
#  Fonctions Utilitaires ZIP & FFmpeg
# -------------------------------------------------------------------
#  Fonctions Utilitaires ZIP & FFmpeg
def compress_upload(uploaded_file):
    buffer = io.BytesIO()
    uploaded_file.seek(0)
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(uploaded_file.name, uploaded_file.read())
    buffer.seek(0)
    zipped_name = f"{uploaded_file.name}.zip"
    return ContentFile(buffer.getvalue(), name=zipped_name)
def decompress_file(file_field):
    file_field.open('rb')
    data = file_field.read()
    file_field.close()

    if not zipfile.is_zipfile(io.BytesIO(data)):
        guessed_type, _ = mimetypes.guess_type(file_field.name)
        return data, file_field.name, guessed_type

    with zipfile.ZipFile(io.BytesIO(data), mode='r') as zf:
        names = zf.namelist()
        if not names:
            return data, file_field.name, None
        inner_name = names[0]
        inner_bytes = zf.read(inner_name)
    guessed_type, _ = mimetypes.guess_type(inner_name)
    return inner_bytes, inner_name, guessed_type
def convert_to_mp3(audio_content, original_filename):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'input_audio')
            output_path = os.path.join(temp_dir, 'output.mp3')
            
            with open(input_path, 'wb') as f:
                f.write(audio_content)
            
            subprocess.run([
                'ffmpeg', '-i', input_path, '-q:a', '0', '-map', 'a', 
                output_path, '-y'
            ], check=True, capture_output=True, timeout=60)
            
            with open(output_path, 'rb') as f:
                return f.read()
    except Exception:
        return audio_content
