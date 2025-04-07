# Generated by Django 5.1.7 on 2025-04-07 08:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0010_alter_tutorapplications_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('plan_type', models.CharField(choices=[('MONTHLY', 'Monthly'), ('YEARLY', 'Yearly')], max_length=10)),
                ('plan_category', models.CharField(choices=[('BASIC', 'Basic'), ('PRO', 'Pro'), ('PREMIUM', 'Premium')], max_length=10)),
                ('price', models.DecimalField(decimal_places=2, max_digits=8)),
                ('description', models.TextField()),
                ('stripe_price_id', models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
        migrations.AlterField(
            model_name='tutorapplications',
            name='email',
            field=models.EmailField(max_length=254, unique=True),
        ),
    ]
