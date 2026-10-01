from django.test import TestCase

# Create your tests here.
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import AuditLog
from document_archive.models import Document, DocumentView, Favorite


@override_settings(SECURE_SSL_REDIRECT=False)
class DocumentArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='lecteur', password='MotDePasseFort123!')
        self.document = Document.objects.create(
            title='Compte rendu',
            file=SimpleUploadedFile('compte-rendu.txt', b'contenu de test', content_type='text/plain'),
            uploaded_by=self.user,
        )
        self.client.force_login(self.user)

    def test_document_detail_registers_view_and_audit_log(self):
        response = self.client.get(reverse('document_detail', args=[self.document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(DocumentView.objects.filter(user=self.user, document=self.document).exists())
        self.assertTrue(AuditLog.objects.filter(
            user=self.user, action='CONSULT', module='DOCUMENT'
        ).exists())

    def test_toggle_document_favorite_adds_then_removes_favorite(self):
        url = reverse('toggle_favorite', args=[self.document.pk])
        response = self.client.post(url)
        self.assertJSONEqual(response.content, {'is_favorite': True})
        self.assertTrue(Favorite.objects.filter(user=self.user, document=self.document).exists())

        response = self.client.post(url)
        self.assertJSONEqual(response.content, {'is_favorite': False})
        self.assertFalse(Favorite.objects.filter(user=self.user, document=self.document).exists())
        self.assertEqual(AuditLog.objects.filter(user=self.user, module='FAVORIS_DOCUMENT').count(), 2)

    def test_anonymous_user_is_redirected_from_document_detail(self):
        self.client.logout()
        response = self.client.get(reverse('document_detail', args=[self.document.pk]))
        self.assertEqual(response.status_code, 302)
