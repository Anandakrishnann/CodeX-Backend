# Generated by Django 5.1.7 on 2025-03-22 13:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tutorapplications',
            name='verification',
        ),
        migrations.RemoveField(
            model_name='tutorapplications',
            name='verification_video',
        ),
    ]
