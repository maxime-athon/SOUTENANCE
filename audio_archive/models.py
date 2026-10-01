"""
Application Audio Archive - Modèles de Données Métier (Version Flexible & Automatisée).
Projet : Radio Kara Archive Project
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.utils import timezone


class Category(models.Model):
    """Catégories des archives audio (ex: Journaux, Émissions culturelles, Musique)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Catégorie Audio"
        verbose_name_plural = "Catégories Audio"
        ordering = ['name']

    def __str__(self):
        return self.name


class Language(models.Model):
    """
    Langues de diffusion de Radio Kara (Français, Kabiye, Tem, Ewe, etc.).
    Gérable dynamiquement par les administrateurs (ajout/suppression).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Langue de diffusion")
    code = models.CharField(max_length=10, blank=True, null=True, verbose_name="Code ISO/Interne")
    is_active = models.BooleanField(default=True, verbose_name="Langue active sur l'antenne")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")

    class Meta:
        verbose_name = "Langue"
        verbose_name_plural = "Langues"
        ordering = ['name']

    def __str__(self):
        return self.name


class AudioFile(models.Model):
    """Modèle central représentant une archive sonore et ses métadonnées radio."""
    
    # --- Classification & Relations ---
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT, 
        related_name='audio_files',
        verbose_name="Catégorie"
    )
    language = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audio_files',
        verbose_name="Langue"
    )

    # --- Identification & Métadonnées Radio ---
    band_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        db_index=True,
        verbose_name="Numéro de Bande / Support",
        help_text="Identifiant de la bande, disquette, cassette ou disque physique d'origine"
    )
    recording_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Numéro d'enregistrement"
    )
    title = models.CharField(
        max_length=200, 
        db_index=True, 
        verbose_name="Titre",
        help_text="Pré-rempli automatiquement avec le nom du fichier si non renseigné"
    )
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="Sous-titre")
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Résumé / Description / Transcription",
        help_text="Contenu de l'émission ou texte transcrit (automatiquement ou manuellement)"
    )
    producer = models.CharField(max_length=100, blank=True, null=True, verbose_name="Producteur / Présentateur")

    # --- Données Temporelles & Techniques (Texte Libre pour la Vitesse) ---
    recording_date = models.DateField(default=timezone.now, blank=True, null=True, verbose_name="Date d'enregistrement")
    broadcast_date = models.DateField(default=timezone.now, blank=True, null=True, db_index=True, verbose_name="Date de diffusion")
    duration = models.DurationField(
        blank=True, 
        null=True, 
        verbose_name="Durée (HH:MM:SS)",
        help_text="Calculée automatiquement lors de l'upload si laissée vide"
    )
    speed = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Vitesse / Format du support",
        help_text="Ex: 19 cm/s, 38 cm/s, 4.75 cm/s, Vinyle 33 RPM, CD, etc."
    )

    # --- Fichier Physiques & Audit ---
    file = models.FileField(
        upload_to='audio/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['mp3', 'wav', 'ogg', 'flac', 'm4a', 'webm', 'zip'])],
        verbose_name="Fichier Audio"
    )
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='audio_uploads',
        verbose_name="Téléversé par"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de téléversement")
    
    # --- Statistiques & Ergonomie ---
    play_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de lectures")
    is_featured = models.BooleanField(default=False, verbose_name="Mettre à la une")

    class Meta:
        verbose_name = "Archives Audio"
        verbose_name_plural = "Archives Audios"
        ordering = ['-broadcast_date', '-uploaded_at']

    def __str__(self):
        band_info = f"[{self.band_number}] " if self.band_number else ""
        return f"{band_info}{self.title}"


class AudioView(models.Model):
    """Historique des écoutes des archives audio par les utilisateurs."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audio_views', verbose_name="Utilisateur")
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='views', verbose_name="Archive audio")
    listened_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'écoute")

    class Meta:
        ordering = ['-listened_at']
        verbose_name = "Historique d'écoute audio"
        verbose_name_plural = "Historiques d'écoute audio"

    def __str__(self):
        return f"{self.user.username} a écouté '{self.audio_file.title}'"


class Favorite(models.Model):
    """Favoris utilisateurs."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audio_favorites', verbose_name="Utilisateur")
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Archive Audio")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"
        unique_together = ('user', 'audio_file')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.audio_file.title}"


class Playlist(models.Model):
    """Playlists utilisateurs."""
    name = models.CharField(max_length=100, verbose_name="Nom de la playlist")
    description = models.TextField(blank=True, verbose_name="Description")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audio_playlists', verbose_name="Créateur")
    is_public = models.BooleanField(default=False, verbose_name="Playlist Publique")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")

    class Meta:
        verbose_name = "Playlist"
        verbose_name_plural = "Playlists"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class PlaylistItem(models.Model):
    """Éléments d'une playlist."""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='items', verbose_name="Playlist")
    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE, verbose_name="Archive Audio")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre de lecture")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        verbose_name = "Élément de Playlist"
        verbose_name_plural = "Éléments de Playlist"
        ordering = ['order', 'added_at']
        unique_together = ('playlist', 'audio_file')

    def __str__(self):
        return f"{self.playlist.name} - #{self.order} {self.audio_file.title}"
