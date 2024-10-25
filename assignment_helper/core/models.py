# models.py
from django.db import models

class Document(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    answers = models.FileField(upload_to='answers/', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    preview = models.ImageField(upload_to='previews/', null=True, blank=True)

    def __str__(self):
        return self.name
    
class APIResponse(models.Model):
    question = models.TextField()
    answer = models.TextField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='api_responses', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question: {self.question[:50]} - Answer: {self.answer[:50]}"

