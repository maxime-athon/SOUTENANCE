from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('audio_archive', '0006_remove_userprofile_preferred_categories_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='audiofile',
            name='file',
            field=models.FileField(
                upload_to='audio/%Y/%m/',
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['mp3', 'wav', 'ogg', 'flac', 'm4a', 'webm']
                )],
                verbose_name='Fichier Audio',
            ),
        ),
    ]