from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('delete_file/<int:file_id>/', views.delete_file, name='delete_file'),
    path('generate_answers/', views.generate_answers, name='generate_answers'),
    path('view_answers/<int:file_id>/', views.view_answers, name='view_answers'),  # New URL pattern for viewing answers
    path('download/<int:file_id>/', views.download_file, name='download_file'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)