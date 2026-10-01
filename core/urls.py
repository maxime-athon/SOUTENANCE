# core/urls.py
from django.urls import path
from . import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Traçabilité & Audit
    path('audit/', views.audit_log_list, name='audit_log_list'),

    # Gestion des Utilisateurs (Administrateur)
    path('users/', views.manage_users, name='manage_users'),
    path('users/<int:pk>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:pk>/delete/', views.delete_user, name='delete_user'),
    
    #vues pour les favoris
    path('favoris/', views.favoris_view, name='favoris'),
    path('historique/', views.historique_view, name='historique'),
]