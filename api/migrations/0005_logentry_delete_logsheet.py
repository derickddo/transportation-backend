# Generated by Django 5.1.7 on 2025-03-21 17:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_routeinstruction_current_location_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('driver_name', models.CharField(max_length=255)),
                ('load_number', models.CharField(blank=True, max_length=255, null=True)),
                ('carrier_name', models.CharField(blank=True, max_length=255, null=True)),
                ('truck_number', models.CharField(blank=True, max_length=255, null=True)),
                ('trailer_number', models.CharField(blank=True, max_length=255, null=True)),
                ('co_driver_name', models.CharField(blank=True, max_length=255, null=True)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('trip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='log_entries', to='api.trip')),
            ],
        ),
        migrations.DeleteModel(
            name='LogSheet',
        ),
    ]
