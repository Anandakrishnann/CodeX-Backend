# Generated by Django 5.1.7 on 2025-03-24 12:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0004_remove_tutorapplications_verification_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tutorapplications',
            name='verification_file_url',
        ),
        migrations.RemoveField(
            model_name='tutorapplications',
            name='verification_video_url',
        ),
        migrations.AddField(
            model_name='tutorapplications',
            name='verification_file',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tutorapplications',
            name='verification_video',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='tutorapplications',
            name='email',
            field=models.EmailField(max_length=254),
        ),
    ]
