# Generated by Django 5.1.7 on 2025-04-08 14:17

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0003_tutorsubscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tutorsubscription',
            name='tutor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Accounts.tutordetails'),
        ),
    ]
