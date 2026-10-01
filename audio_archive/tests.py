from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audio_archive.models import AudioFile, AudioView, Category, Favorite
from core.models import AuditLog


@override_settings(SECURE_SSL_REDIRECT=False)
class AudioArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='auditeur', password='MotDePasseFort123!')
        self.audio = AudioFile.objects.create(
            category=Category.objects.create(name='Journal'),
            title='Édition de midi',
            file=SimpleUploadedFile('journal.mp3', b'fake-audio-content', content_type='audio/mpeg'),
            uploaded_by=self.user,
        )
        self.client.force_login(self.user)

    def test_stream_registers_audio_view_and_audit_log(self):
        response = self.client.get(reverse('stream_audio', args=[self.audio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AudioView.objects.filter(user=self.user, audio_file=self.audio).count(), 1)
        self.assertTrue(AuditLog.objects.filter(
            user=self.user, action='CONSULT', module='AUDIO'
        ).exists())
        self.audio.refresh_from_db()
        self.assertEqual(self.audio.play_count, 1)

    def test_toggle_favorite_adds_then_removes_favorite(self):
        url = f'/audio/toggle-favorite/{self.audio.pk}/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Favorite.objects.filter(user=self.user, audio_file=self.audio).exists())

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Favorite.objects.filter(user=self.user, audio_file=self.audio).exists())
        self.assertEqual(AuditLog.objects.filter(user=self.user, module='AUDIO').count(), 2)

    def test_anonymous_user_cannot_stream_audio(self):
        self.client.logout()
        response = self.client.get(reverse('stream_audio', args=[self.audio.pk]))
        self.assertEqual(response.status_code, 302)
