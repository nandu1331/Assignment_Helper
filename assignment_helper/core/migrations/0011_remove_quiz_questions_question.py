# Generated by Django 5.1.2 on 2024-12-06 17:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_quiz_difficulty_quiz_is_active'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quiz',
            name='questions',
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=500)),
                ('options', models.JSONField()),
                ('correct_option', models.IntegerField()),
                ('explanation', models.TextField(blank=True, null=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='core.quiz')),
            ],
        ),
    ]