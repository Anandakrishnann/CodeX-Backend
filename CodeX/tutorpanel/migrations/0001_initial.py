# Generated by Django 5.1.7 on 2025-04-09 13:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('Accounts', '0006_alter_tutorsubscription_is_active'),
        ('adminpanel', '0014_coursecategory'),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('title', models.CharField(max_length=200)),
                ('description', models.CharField(max_length=600)),
                ('requirements', models.CharField(max_length=600)),
                ('benefits', models.CharField(max_length=600)),
                ('price', models.DecimalField(decimal_places=2, max_digits=8)),
                ('created_at', models.DateField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('category_id', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='adminpanel.coursecategory')),
                ('tutor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='Accounts.tutordetails')),
            ],
        ),
    ]
