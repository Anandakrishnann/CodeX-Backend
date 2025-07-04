# Generated by Django 5.1.7 on 2025-05-14 13:59

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Accounts', '0018_alter_usercourseenrollment_status_lessonprogress'),
        ('tutorpanel', '0013_remove_course_rating_remove_course_review_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuleProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('progress', 'In Progress'), ('completed', 'Completed')], default='pending', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('module', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tutorpanel.modules')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'module')},
            },
        ),
    ]
