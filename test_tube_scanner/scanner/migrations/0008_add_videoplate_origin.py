from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scanner', '0007_add_videoplate_px_per_mm'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoplate',
            name='x_origin_mm',
            field=models.FloatField(
                default=0.0,
                verbose_name='Origine X (mm)',
                help_text='Position CNC X correspondant au pixel 0 de la vidéo plaque (mm). Défaut 0.',
            ),
        ),
        migrations.AddField(
            model_name='videoplate',
            name='y_origin_mm',
            field=models.FloatField(
                default=0.0,
                verbose_name='Origine Y (mm)',
                help_text='Position CNC Y correspondant au pixel 0 de la vidéo plaque (mm). Défaut 0.',
            ),
        ),
    ]
