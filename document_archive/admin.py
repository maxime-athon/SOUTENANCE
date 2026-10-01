from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Document, DocumentView, Favorite
from .views import run_ocr_on_document


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_document_count')
    search_fields = ('name', 'description')
    
    def get_document_count(self, obj):
        return obj.documents.count()
    get_document_count.short_description = "Nombre de Documents"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'preview_thumbnail', 
        'title', 
        'category', 
        'author', 
        'uploaded_by', 
        'uploaded_at', 
        'compressed', 
        'has_ocr'
    )
    list_filter = ('category', 'compressed', 'uploaded_at')
    search_fields = ('title', 'author', 'tags', 'ocr_text', 'description')
    readonly_fields = ('uploaded_at', 'ocr_text_preview')
    fieldsets = (
        ('Informations Générales', {
            'fields': ('title', 'author', 'description', 'category', 'tags')
        }),
        ('Fichiers & Médias', {
            'fields': ('file', 'thumbnail')
        }),
        ('Traitements Automatiques & Indexation', {
            'fields': ('compressed', 'uploaded_by', 'uploaded_at', 'ocr_text_preview')
        }),
    )
    actions = ['trigger_ocr_processing']

    def preview_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="width: 45px; height: auto; border-radius: 4px;" />', obj.thumbnail.url)
        return "Pas d'image"
    preview_thumbnail.short_description = "Aperçu"

    def has_ocr(self, obj):
        return bool(obj.ocr_text and obj.ocr_text.strip())
    has_ocr.boolean = True
    has_ocr.short_description = "OCR Extrait"

    def ocr_text_preview(self, obj):
        if obj.ocr_text:
            return obj.ocr_text[:300] + "..." if len(obj.ocr_text) > 300 else obj.ocr_text
        return "Aucun texte OCR disponible."
    ocr_text_preview.short_description = "Aperçu du texte OCR"

    @admin.action(description="Exécuter/Relancer l'OCR sur les documents sélectionnés")
    def trigger_ocr_processing(self, request, queryset):
        success_count = 0
        for doc in queryset:
            run_ocr_on_document(doc)
            success_count += 1
        self.message_user(request, f"L'OCR a été réexécuté avec succès sur {success_count} document(s).")


@admin.register(DocumentView)
class DocumentViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'document', 'viewed_at')
    list_filter = ('viewed_at', 'user')
    search_fields = ('user__username', 'document__title')
    readonly_fields = ('user', 'document', 'viewed_at')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'document', 'added_at')
    list_filter = ('added_at', 'user')
    search_fields = ('user__username', 'document__title')
    readonly_fields = ('user', 'document', 'added_at')