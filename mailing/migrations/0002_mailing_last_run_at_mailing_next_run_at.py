# Generated by Django 4.2.8 on 2023-12-22 14:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('mailing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mailing',
            name='last_run_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mailing',
            name='next_run_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
