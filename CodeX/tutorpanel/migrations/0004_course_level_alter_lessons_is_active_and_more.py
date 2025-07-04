# Generated by Django 5.1.7 on 2025-04-15 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tutorpanel', '0003_alter_course_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='level',
            field=models.CharField(choices=[('beginer', 'Beginer'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], default='beginer', max_length=50),
        ),
        migrations.AlterField(
            model_name='lessons',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='modules',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
    ]
