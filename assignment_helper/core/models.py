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
    

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=100)
    context = models.TextField(null=True, blank=True)
    time_limit = models.IntegerField(
        default=600,  # 10 minutes in seconds
        validators=[
            MinValueValidator(60),    # Minimum 1 minute
            MaxValueValidator(3600)   # Maximum 1 hour
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_quizzes'
    )
    is_active = models.BooleanField(default=True)  # To soft-delete/deactivate quizzes
    difficulty = models.CharField(
        max_length=20,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return f"{self.title} - {self.topic}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    options = models.JSONField()  # Ensure a list of strings
    correct_option = models.IntegerField()  # Store the index of the correct option
    explanation = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.text


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        null=True,
        default=None
    )
    score = models.FloatField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    answers = models.JSONField()  # Stores the user's answers
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-completed_at']
        unique_together = ['quiz', 'user']

    def __str__(self):
        return f"{self.user.username}'s attempt at {self.quiz.title} - {self.score}%"
    
    @staticmethod
    def get_user_statistics(user):
        """Returns statistics for a user, including total attempts, average score, and highest score."""
        attempts = QuizAttempt.objects.filter(user=user)
        total_attempts = attempts.count()
        if total_attempts == 0:
            return {
                'total_attempts': 0,
                'average_score': 0,
                'highest_score': 0,
            }

        total_score = sum([attempt.score for attempt in attempts])
        average_score = total_score / total_attempts
        highest_score = max([attempt.score for attempt in attempts])

        return {
            'total_attempts': total_attempts,
            'average_score': average_score,
            'highest_score': highest_score,
        }

class PDFChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    pdf_document = models.ForeignKey(Document, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return f"Chat Session: {self.pdf_document.name} - {self.user.username}"

class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('USER', 'User'),
        ('AI', 'AI Assistant')
    ]
    
    session = models.ForeignKey(PDFChatSession, on_delete=models.CASCADE)
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_context_relevant = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.message[:50]}..."




