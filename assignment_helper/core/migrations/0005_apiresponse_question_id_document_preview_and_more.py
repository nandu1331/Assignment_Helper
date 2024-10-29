# Generated by Django 5.1.2 on 2024-10-27 10:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_document_preview'),
    ]

    operations = [
        migrations.AddField(
            model_name='apiresponse',
            name='question_id',
            field=models.PositiveIntegerField(default=-1),
        ),
        # Remove or comment out the duplicate addition of the preview field
        # migrations.AddField(
        #     model_name='document',
        #     name='preview',
        #     field=models.ImageField(blank=True, null=True, upload_to='previews/'),
        # ),
        migrations.AlterUniqueTogether(
            name='apiresponse',
            unique_together={('document', 'question_id')},
        ),
    ]