from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la catégorie")
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Document(models.Model):
    title = models.CharField(max_length=200, db_index=True, verbose_name="Titre")
    author = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="Auteur")
    description = models.TextField(blank=True, verbose_name="Description")
    
    # Rangement dynamique par Année / Mois
    file = models.FileField(upload_to='documents/%Y/%m/', verbose_name="Fichier document")
    thumbnail = models.ImageField(upload_to='thumbnails/%Y/%m/', blank=True, null=True, verbose_name="Miniature")
    
    # Protections et index
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='documents',
        verbose_name="Catégorie"
    )
    tags = models.CharField(max_length=500, blank=True, help_text="Mots-clés séparés par des virgules", verbose_name="Mots-clés (Tags)")
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='doc_uploads',
        verbose_name="Téléversé par"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Date d'upload")
    compressed = models.BooleanField(default=False, verbose_name="Fichier compressé")
    ocr_text = models.TextField(blank=True, verbose_name="Texte OCR extrait")

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


class DocumentView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doc_views', verbose_name="Utilisateur")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name="Document")
    viewed_at = models.DateTimeField(auto_now_add=True, verbose_name="Dernière vue")

    class Meta:
        ordering = ['-viewed_at']
        verbose_name = "Historique de consultation"
        verbose_name_plural = "Historiques de consultation"

    def __str__(self):
        return f"{self.user.username} a vu '{self.document.title}'"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doc_favorites', verbose_name="Utilisateur")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name="Document")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        unique_together = ('user', 'document')
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"

    def __str__(self):
        return f"{self.user.username} - {self.document.title}"