# Generated by Django 5.1.7 on 2025-05-21 10:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0014_coursecategory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tutorapplications',
            name='profile_picture',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='tutorapplications',
            name='verification_file',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='tutorapplications',
            name='verification_video',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
