"""
Application Core - Modèles de Données Transversaux.
Projet : Radio Kara Archive Project
Rôle : Gestion des profils utilisateurs, rôles métiers et traçabilité (AuditLog).
"""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extension du modèle utilisateur natif de Django (contrib.auth.models.User).
    
    Le modèle User fournit déjà nativement :
    - id, username, password, email, first_name, last_name,
    - is_staff, is_superuser, is_active, date_joined.
    
    UserProfile ajoute uniquement le rôle métier et le contact téléphone.
    """
    ROLE_CHOICES = [
        ('ADMIN', 'Administrateur'),
        ('ARCHIVISTE', 'Archiviste'),
        ('JOURNALISTE', 'Journaliste / Agent'),
        ('LECTEUR', ''), # ajouter une description pour le rôle LECTEUR si nécessaire
    ]

    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile',
        verbose_name="Utilisateur"
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='LECTEUR',
        verbose_name="Rôle applicatif"
    )
    telephone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Téléphone"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Profil Utilisateur"
        verbose_name_plural = "Profils Utilisateurs"
        ordering = ['user__username']

    def __str__(self):
        full_name = self.user.get_full_name()
        display_name = full_name if full_name else self.user.username
        return f"{display_name} ({self.get_role_display()})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Signal pour créer ou mettre à jour automatiquement le profil lors de la gestion d'un User."""
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Garantit la création du profil si l'utilisateur existait déjà sans profil
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            UserProfile.objects.create(user=instance)


class AuditLog(models.Model):
    """
    Journal d'audit pour enregistrer la traçabilité des opérations dans l'application.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Création'),
        ('UPDATE', 'Modification'),
        ('DELETE', 'Suppression'),
        ('CONSULT', 'Consultation / Téléchargement'),
        ('LOGIN', 'Connexion'),
        ('LOGOUT', 'Déconnexion'),
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs',
        verbose_name="Utilisateur"
    )
    action = models.CharField(
        max_length=20, 
        choices=ACTION_CHOICES, 
        verbose_name="Action effectuée"
    )
    module = models.CharField(
        max_length=50, 
        verbose_name="Module concerné"
    )
    description = models.TextField(
        verbose_name="Description détaillée"
    )
    ip_address = models.GenericIPAddressField(
        null=True, 
        blank=True, 
        verbose_name="Adresse IP"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, 
        db_index=True, 
        verbose_name="Date et Heure"
    )

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.username if self.user else "Système/Anonyme"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {user_str} - {self.get_action_display()} ({self.module})"