# Generated by Django 5.1.7 on 2025-05-15 04:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0021_lessonprogress_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='lessonprogress',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
