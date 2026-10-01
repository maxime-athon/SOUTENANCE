from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .api import (
    CategoryViewSet,
    DocumentViewSet,
    DocumentViewHistoryViewSet,
    FavoriteViewSet,
)

# Configuration du routeur API REST
router = DefaultRouter()
router.register(r'documents', DocumentViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'favorites', FavoriteViewSet)
router.register(r'history', DocumentViewHistoryViewSet)

urlpatterns = [
    # --------------------------------------------------------------------------
    # 1. GESTION DES DOCUMENTS (CRUD, OCR & Upload)
    # --------------------------------------------------------------------------
    path('', views.document_list, name='document_list'),
    path('upload/', views.upload_document, name='upload_document'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/edit/', views.edit_document, name='edit_document'),
    path('<int:pk>/delete/', views.delete_document, name='delete_document'),
    path('<int:pk>/ocr/', views.extract_ocr, name='extract_ocr'),
    path('<int:doc_id>/ocr/view/', views.document_ocr_detail, name='document_ocr_detail'),
    path('<int:doc_id>/ocr/save/', views.save_ocr,name='save_ocr'),
     
    # --------------------------------------------------------------------------
    # 2. FAVORIS & HISTORIQUE
    # --------------------------------------------------------------------------
    path('<int:pk>/favorite/', views.toggle_document_favorite, name='toggle_favorite'),
    path('favorites/', views.favorites, name='favorites'),
    path('recent/', views.recent_views, name='recent_views'),

    # --------------------------------------------------------------------------
    # 3. GESTION DES CATÉGORIES (Document & Audio)
    # --------------------------------------------------------------------------
    path('categories/manage/', views.global_manage_categories, name='global_manage_categories'),
    path('categories/doc/add/', views.add_doc_category, name='add_doc_category'),
    path('categories/audio/add/', views.add_audio_category, name='add_audio_category'),
    path('categories/doc/edit/<int:pk>/', views.doc_edit_category, name='doc_edit_category'),
    path('categories/audio/edit/<int:pk>/', views.audio_edit_category, name='audio_edit_category'),
    path('categories/doc/delete/<int:pk>/', views.doc_delete_category, name='doc_delete_category'),
    path('categories/audio/delete/<int:pk>/', views.audio_delete_category, name='audio_delete_category'),

    # --------------------------------------------------------------------------
    # 4. RECHERCHE, STATISTIQUES & EXPORT
    # --------------------------------------------------------------------------
    path('search/', views.search_document, name='search_document'),
    path('statistics/', views.statistics, name='statistics'),
    path('export/', views.export_data, name='export_data'),
    path('api-docs/', views.api_documentation, name='api_docs'),

    # --------------------------------------------------------------------------
    # 5. ENDPOINTS API REST
    # --------------------------------------------------------------------------
    path('api/', include(router.urls)),
]