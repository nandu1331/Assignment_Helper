from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.sign_up, name='sign_up'),
    path('log_out/', views.log_out, name='log_out'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('saved_files/', views.saved_files, name='saved_files'),
    path('edit_file_details/', views.edit_file_details, name='edit_file_details'),
    path('update_questions/', views.update_questions, name='update_questions'),
    path('api/uploaded-files/', views.get_uploaded_files, name='get_uploaded_files'),
    path('delete_file/<int:file_id>/', views.delete_file, name='delete_file'),
    path('generate_answer/', views.generate_answer, name='generate_answer'),
    path('generate_answers/', views.generate_answers, name='generate_answers'),
    path('view_answers/<int:file_id>/', views.view_answers, name='view_answers'),  # New URL pattern for viewing answers
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    # path('quiz/', views.quiz_home, name='quiz_home'),
    path('generate-quiz/', views.generate_quiz, name='generate_quiz'),
    path('submit-quiz/<int:quiz_id>/', views.submit_quiz, name='submit_quiz'),
    path('quiz/', views.quiz_home, name='quiz_home'),
    path('quiz/attempt/<int:quiz_id>/', views.attempt_quiz, name='attempt_quiz'),
    path('quiz/results/<int:quiz_id>/', views.quiz_results, name='quiz_results'),
    path('quiz/history/', views.quiz_history, name='quiz_history'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)