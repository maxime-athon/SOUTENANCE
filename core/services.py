"""
Services d'extraction automatique de métadonnées pour les médias d'archive.
Projet : Radio Kara Archive Project
"""

import os
from datetime import timedelta
try:
    from mutagen import getattr_
    from mutagen.mp3 import MP3
    from mutagen.wave import WAVE
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


def extract_audio_duration(file_path):
    """
    Calcule la durée exacte d'un fichier audio et la retourne au format timedelta.
    """
    if not MUTAGEN_AVAILABLE or not os.path.exists(file_path):
        return None

    try:
        ext = os.path.splitext(file_path)[1].lower()
        duration_seconds = 0

        if ext == '.mp3':
            audio = MP3(file_path)
            duration_seconds = audio.info.length
        elif ext == '.wav':
            audio = WAVE(file_path)
            duration_seconds = audio.info.length
        elif ext == '.ogg':
            audio = OggVorbis(file_path)
            duration_seconds = audio.info.length
        elif ext == '.flac':
            audio = FLAC(file_path)
            duration_seconds = audio.info.length

        if duration_seconds > 0:
            return timedelta(seconds=int(duration_seconds))
    except Exception:
        pass

    return None


def generate_clean_title(filename):
    """
    Génère un titre propre à partir du nom d'origine du fichier téléversé.
    Ex: 'journal_parle_kara_12_08.mp3' -> 'Journal Parle Kara 12 08'
    """
    name_without_ext = os.path.splitext(filename)[0]
    clean_name = name_without_ext.replace('_', ' ').replace('-', ' ').strip()
    return clean_name.capitalize()


def get_client_ip(request):
    """Extrait l'adresse IP du client à partir des en-têtes de la requête HTTP."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip