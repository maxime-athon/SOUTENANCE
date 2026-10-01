"""
Configuration de l'administration pour l'application Audio Archive.
Projet : Radio Kara Archive Project
"""

from django.contrib import admin
from .models import Category, Language, AudioFile, AudioView, Favorite, Playlist, PlaylistItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_editable = ('is_active',)


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = (
        'title', 
        'band_number', 
        'category', 
        'language', 
        'broadcast_date', 
        'speed', 
        'play_count', 
        'is_featured'
    )
    list_filter = ('category', 'language', 'is_featured', 'broadcast_date')
    search_fields = ('title', 'band_number', 'recording_number', 'description', 'producer')
    date_hierarchy = 'broadcast_date'
    list_editable = ('is_featured',)
    readonly_fields = ('play_count', 'uploaded_at', 'uploaded_by')

    fieldsets = (
        ('Classification', {
            'fields': ('category', 'language', 'is_featured')
        }),
        ('Identification & Métadonnées Radio', {
            'fields': ('band_number', 'recording_number', 'title', 'subtitle', 'description', 'producer')
        }),
        ('Spécifications Techniques & Dates', {
            'fields': ('recording_date', 'broadcast_date', 'duration', 'speed')
        }),
        ('Fichier & Audit', {
            'fields': ('file', 'uploaded_by', 'uploaded_at', 'play_count')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change or not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AudioView)
class AudioViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'audio_file', 'listened_at')
    list_filter = ('listened_at', 'user')
    search_fields = ('user__username', 'audio_file__title')
    readonly_fields = ('user', 'audio_file', 'listened_at')


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 1


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_public', 'created_at')
    list_filter = ('is_public',)
    search_fields = ('name', 'user__username')
    inlines = [PlaylistItemInline]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'audio_file', 'added_at')
    search_fields = ('user__username', 'audio_file__title')
