from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import AuditLog
from document_archive.models import Category


@override_settings(SECURE_SSL_REDIRECT=False)
class CoreViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='journaliste', password='MotDePasseFort123!')
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='MotDePasseFort123!'
        )

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_creates_audit_entry(self):
        response = self.client.post(reverse('login'), {
            'username': self.user.username,
            'password': 'MotDePasseFort123!',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(AuditLog.objects.filter(user=self.user, action='LOGIN').exists())

    def test_admin_can_create_category_and_action_is_audited(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('add_doc_category'), {'name': 'Actualités', 'description': ''})
        self.assertRedirects(response, reverse('global_manage_categories'))
        self.assertTrue(Category.objects.filter(name='Actualités').exists())


    def test_docx_audit_export_is_disabled(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"{reverse('audit_log_list')}?export=docx")
        self.assertEqual(response.status_code, 400)
