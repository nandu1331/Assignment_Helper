from django.db import models
from django.contrib.auth.models import User  # Import the User model

class Document(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    answers = models.FileField(upload_to='answers/', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    preview = models.ImageField(upload_to='previews/', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents', default=1)  # Associate with User

    def __str__(self):
        return self.name

class APIResponse(models.Model):
    question = models.TextField()
    answer = models.TextField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='api_responses', default=75)
    question_id = models.PositiveIntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1)

    class Meta:
        unique_together = ('document', 'question_id')

    def __str__(self):
        return f"Question: {self.question[:50]} - Answer: {self.answer[:50]}"