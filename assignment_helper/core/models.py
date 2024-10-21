# models.py
from django.db import models

class APIResponse(models.Model):
    question = models.TextField()
    answer = models.TextField()
    document_hash = models.CharField(max_length=255)  # To identify different documents
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question: {self.question[:50]} - Answer: {self.answer[:50]}"
