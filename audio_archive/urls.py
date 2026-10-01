from django.urls import path
from . import views



urlpatterns = [
    # -------------------------------------------------------------------
    #  Navigation Publique & Consultation
    # -------------------------------------------------------------------
    path('', views.audio_list, name='audio_list'),
    path('search/', views.search_audio, name='search_audio'),
    path('<int:audio_id>/', views.audio_detail, name='audio_detail'),

    # -------------------------------------------------------------------
    #  Streaming & Téléchargement
    # -------------------------------------------------------------------
    path('stream/<int:audio_id>/', views.stream_audio, name='stream_audio'),
    path('download/<int:audio_id>/', views.download_audio, name='download_audio'),

    # -------------------------------------------------------------------
    #  Favoris (AJAX)
    # -------------------------------------------------------------------
    path('toggle-favorite/<int:audio_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('check-favorite/<int:audio_id>/', views.check_favorite, name='check_favorite'),


    # -------------------------------------------------------------------
    #  Gestion des Fichiers Audio (Espace Staff / Admin)
    # -------------------------------------------------------------------
    path('management/', views.audio_management, name='audio_management'),
    path('add/', views.add_audio, name='add_audio'),
    path('edit/<int:audio_id>/', views.edit_audio, name='edit_audio'),
    path('delete/<int:audio_id>/', views.delete_audio, name='delete_audio'),
    path('delete-bulk/', views.delete_bulk_audio, name='delete_bulk_audio'),
    path('normalize-bulk/', views.normalize_bulk_audio, name='normalize_bulk_audio'),

    
    path('audit/', views.audit_logs, name='audit_logs'),
]