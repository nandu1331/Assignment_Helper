from django.contrib import admin
from .models import APIResponse, Document

# Customizing the APIResponse admin interface
class APIResponseAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'question', 'answer', 'document', 'created_at')  # Include question_id
    search_fields = ('question', 'answer', 'question_id')  # Enable search on question, answer, and question_id
    list_filter = ('document',)  # Filter by document in the admin interface

# Customizing the Document admin interface
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'file', 'uploaded_at')  # Display fields in the list view
    search_fields = ('name',)  # Enable search on the document name

# Registering the models with their respective admin classes
admin.site.register(APIResponse, APIResponseAdmin)
admin.site.register(Document, DocumentAdmin)