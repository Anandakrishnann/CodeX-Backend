# Generated by Django 5.1.7 on 2025-04-10 07:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0006_alter_tutorsubscription_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accounts',
            name='password',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
