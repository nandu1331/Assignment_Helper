# admin.py
from django.contrib import admin
from .models import Document, APIResponse, Quiz, QuizAttempt

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'uploaded_at', 'user')
    search_fields = ('name', 'user__username')
    list_filter = ('uploaded_at', 'user')

@admin.register(APIResponse)
class APIResponseAdmin(admin.ModelAdmin):
    list_display = ('question', 'answer', 'document', 'created_at', 'user')
    search_fields = ('question', 'document__name', 'user__username')
    list_filter = ('created_at', 'document', 'user')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'created_at', 'id')
    search_fields = ('title', 'topic')
    list_filter = ('created_at',)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'user', 'score', 'started_at', 'completed_at')
    search_fields = ('quiz__title', 'user__username')
    list_filter = ('started_at', 'completed_at', 'quiz')
