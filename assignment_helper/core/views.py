from django.shortcuts import render, redirect, get_object_or_404
from .forms import PDFUploadForm
import google.generativeai as genai
import os
from fpdf import FPDF
import re
from .models import APIResponse, Document
from pdf2image import convert_from_path
from django.core.files.base import ContentFile
from io import BytesIO
from django.http import JsonResponse, FileResponse
from django.urls import reverse
from django.conf import settings
import pdfplumber
import spacy
from nltk.corpus import words
import google
import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .forms import CustomLoginForm
# Configure the Gemini API
genai.configure(api_key=os.environ['API_KEY'])

# Load the English NLP model
nlp = spacy.load("en_core_web_sm")
# Load English words list
english_words = set(words.words())

def index(request):
    print("Rendering index page.")
    return render(request, 'core/index.html')

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('saved_files')  # Redirect to the upload PDF page or any other page
            else:
                form.add_error(None, "Invalid username or password.")
    else:
        form = CustomLoginForm()
    return render(request, 'core/login.html', {'form': form})

from .forms import SignUpForm
def sign_up(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, "Registration Successful.")
            return redirect('login')  # Redirect to the login page
    else:
        form = SignUpForm()
    return render(request, 'core/sign_up.html', {'form': form})

from django.contrib.auth import logout
@login_required
def log_out(request):
    logout(request)
    return redirect('login')


from django.db import IntegrityError
@login_required
def upload_pdf(request):
    print("Upload PDF view accessed.")
    uploaded_files = Document.objects.filter(user=request.user)  # Filter by logged-in user
    if request.method == 'POST':
        print("POST request received for PDF upload.")
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            pdf_name = pdf_file.name
            print(f"PDF file received: {pdf_name}")

            # Check if the document already exists
            existing_document = Document.objects.filter(name=pdf_name, user=request.user).first()
            if existing_document:
                document = existing_document
                print(f"Document already exists: {document.name} with ID {document.id}")
                
                # Optionally delete existing APIResponse entries for this document
                APIResponse.objects.filter(document=document).delete()
                print(f"Existing questions for document ID {document.id} have been deleted.")
            else:
                document = Document(name=pdf_name, file=pdf_file, user=request.user)
                document.save()
                print(f"Document saved: {document.name} with ID {document.id}")

            # Check if a preview image already exists
            if not document.preview:
                images = convert_from_path(document.file.path, first_page=1, last_page=1)
                if images:
                    img_byte_arr = BytesIO()
                    images[0].save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)

                    preview_image_path = f'previews/preview_{document.id}.png'
                    image_file = ContentFile(img_byte_arr.read(), name=preview_image_path)
                    document.preview.save(preview_image_path, image_file, save=True)
                    print(f"Preview image created for document ID {document.id}.")

            # Extract questions from the PDF
            questions_with_ids = extract_questions(pdf_file)
            print(f"Extracted questions: {questions_with_ids}")

            # Store the new questions in the database
            for question_id, question_text in questions_with_ids:
                try:
                    # Create a new APIResponse entry for each question
                    APIResponse.objects.create(
                        document=document,
                        question=question_text,
                        question_id=question_id  # Assign a new unique question ID
                    )
                    print(f"Stored question: {question_text}")
                except IntegrityError:
                    print(f" IntegrityError for question: {question_text} with document ID: {document.id}")
                    continue  # Skip to the next question if an integrity error occurs

            # Store questions in the session
            request.session['questions'] = [q[1] for q in questions_with_ids]
            request.session['document_id'] = document.id
            print(f"Questions stored in session for document ID {document.id}.")

            # Render the success page with questions
            return render(request, 'core/upload_success.html', {
                'questions': [q[1] for q in questions_with_ids],
                'extracted_text': None,
            })
    else:
        form = PDFUploadForm()

    return render(request, 'core/upload_pdf.html', {'form': form, 'uploaded_files': uploaded_files})

@login_required
def saved_files(request):
    print("Accessing saved files.")
    uploaded_files = Document.objects.filter(user=request.user)  # Filter by logged-in user
    context = {'uploaded_files': uploaded_files}
    return render(request, 'core/saved_files.html', context)

@login_required
def get_uploaded_files(request):
    print("Fetching uploaded files.")
    files = Document.objects.filter(user=request.user).order_by('-uploaded_at')  # Filter by logged-in user
    file_list = [{
        'id': file.id,
        'name': file.name,
        'upload_time': file.uploaded_at,
        'delete_url': reverse('delete_file', args=[file.id]),
        'view_answers_url': reverse('view_answers', args=[file.id]),
        'download_url': reverse('download_file', args=[file.id]),
    } for file in files]
    return JsonResponse(file_list, safe=False)

@login_required
def delete_file(request, file_id):
    print(f"Deleting file with ID: {file_id}.")
    document = get_object_or_404(Document, id=file_id, user=request.user)  # Filter by logged-in user
    file_path = document.file.path
    if os.path.isfile(file_path):
        os.remove(file_path)
        print(f"File {file_path} deleted.")

    answers_dir = os.path.join(settings.MEDIA_ROOT, 'answers')
    answers_pdf_path = os.path.join(answers_dir, f" answers_{document.id}.pdf")
    preview_dir = os.path.join(settings.MEDIA_ROOT, 'previews')
    preview_path = os.path.join(preview_dir, f"preview_{document.id}.png")
    
    if os.path.isfile(answers_pdf_path):
        os.remove(answers_pdf_path)
        print(f"Answer PDF {answers_pdf_path} deleted.")

    if os.path.isfile(preview_path):
        os.remove(preview_path)
        print(f"Preview image {preview_path} deleted.")

    document.delete()
    print(f"Document with ID {file_id} deleted.")
    return redirect('saved_files')

@login_required
def download_file(request, file_id):
    print(f"Downloading file with ID: {file_id}.")
    document = get_object_or_404(Document, id=file_id, user=request.user)  # Filter by logged-in user

    if document.answers:
        file_path = document.answers.path
        if os.path.isfile(file_path):
            response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="answers_{document.id}.pdf"'
            return response
        else:
            return JsonResponse({'error': 'Answer file not found.'}, status=404)

    questions_and_answers = APIResponse.objects.filter(document=document, user=request.user)  # Filter by logged-in user
    if not questions_and_answers.exists():
        return JsonResponse({'error': 'No questions and answers found for this document.'}, status=404)

    questions = [q.question for q in questions_and_answers]
    answers = [a.answer for a in questions_and_answers]

    return generate_question_bank_pdf(questions, answers, document.id)

@login_required
def view_answers(request, file_id):
    print(f"Viewing answers for file with ID: {file_id}.")
    
    # Get the document for the logged-in user
    document = get_object_or_404(Document, id=file_id, user=request.user)  # Filter by logged-in user

    # Filter answers specific to the document and user
    answers = document.api_responses.filter(user=request.user)  # Ensure to filter by user
    question_answer_map = {}

    # Create a question_answer_map using question IDs as keys and formatted answers as values
    for response in answers:
        question_id = response.question_id  # Get the question ID
        question_text = response.question  # Get the question text
        formatted_answer = response.answer  # Get the formatted answer

        # Map question ID to its corresponding answer
        question_answer_map[question_id] = {
            'question': question_text,
            'answer': formatted_answer
        }

    pdf_file_path = os.path.join(settings.MEDIA_ROOT, f"answers/answers_{document.id}.pdf")
    pdf_file_path = generate_question_bank_pdf(
        [item['question'] for item in question_answer_map.values()],
        [item['answer'] for item in question_answer_map.values()],
        document.id
    )

    return render(request, 'core/generate_answers.html', {
        'document': document,
        'question_answer_map': question_answer_map,
        'pdf_file_path': pdf_file_path,
        'viewing_answers': True,
        'document_id' : document.id,
    })

@login_required
def update_questions(request):
    print("Updating questions.")
    if request.method == 'POST':
        document_id = request.session.get('document_id')
        if not document_id:
            return JsonResponse({'error': 'Document ID not found in session.'}, status=400)

        modified_questions_json = request.body.decode('utf-8')
        try:
            modified_questions = json.loads(modified_questions_json)
        except json.JSONDecodeError:
            return JsonResponse({'error': "Failed to decode JSON. Please check the format."}, status=400)
        
        print("Modified questions:\n", modified_questions)
        # Update questions in the database
        for question_data in modified_questions['questions']:
            question_id = int(question_data['id'])
            question_text = question_data['text']
            try:
                api_response = APIResponse.objects.get(document_id=document_id, question_id=question_id, user=request.user)  # Filter by logged-in user
                api_response.question = question_text
                api_response.save()
                print(f"Question {question_id} updated to: {question_text}")
            except APIResponse.DoesNotExist:
                print(f"Question with ID {question_id} does not exist.")
                continue

        return JsonResponse({'success': True, 'message': "Questions updated successfully."})

    return JsonResponse({'error': "Invalid request method."}, status=400)

from django.http import HttpResponseBadRequest

@login_required
def generate_answer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question_id = data.get('question_id')
            document_id = data.get('document_id')
            ans_detailing = data.get('detailing')  # Assuming you send document_id in the request
            print(document_id)

            print("QUESTION ID:\n\n", question_id, document_id)

            if not question_id or not document_id:
                return HttpResponseBadRequest('No question ID or document ID provided.')

            # Fetch the Document based on the document_id
            document = get_object_or_404(Document, id=document_id)

            # Now fetch the APIResponse for the specific document and question_id
            api_response = get_object_or_404(APIResponse, document=document, question_id=question_id)

            question_text = api_response.question  # Get the question text

            # Fetch answer from the Gemini API
            answer = get_answers_from_gemini([question_text], ans_detailing)
            
            answer = clean_single_answer_response(answer)
            print(answer)
            
            if answer and isinstance(answer, list) and len(answer) > 0:
                api_response.answer = answer[0]
                api_response.save()
                
                return render(request, 'core/answer_snippet.html', {'answer': answer[0]})
            else:
                return HttpResponseBadRequest('No answer generated.')

        except json.JSONDecodeError:
            return HttpResponseBadRequest('Invalid JSON format.')
    return HttpResponseBadRequest('Invalid request method.')

@login_required
def generate_answers(request):
    print("Generating answers.")
    if request.method == 'POST':
        document_id = request.session.get('document_id')
        if not document_id:
            return JsonResponse({'error': 'Document ID not found in session.'}, status=400)

        document = get_object_or_404(Document, id=document_id, user=request.user)  # Filter by logged-in user

        # Fetch the latest responses from the database
        questions_to_process = document.api_responses.values_list('question', flat=True)
        questions = list(questions_to_process)
        print("Questions to process:", questions)

        if not questions_to_process:
            return render(request, 'core/generate_answers.html', {
                'error': "No questions found for this document.",
                'question_answer_map': {}
            })

        # Extract question IDs from the APIResponse objects
        question_ids = document.api_responses.values_list('question_id', flat=True)
        question_ids = list(question_ids)
        print(f"Question IDs to process: {question_ids}")

        # Fetch the actual questions from the APIResponse model using the question IDs
        questions_to_process = document.api_responses.values_list('question', flat=True)
        questions_list = list(questions)
        print(f"Questions to process: {questions_list}")

        # Directly fetch new answers from the Gemini API using the actual questions
        answers = get_answers_from_gemini(questions_list, 'medium')
        print("RAW API RESPONSE\n\n", answers) 
         # Pass the actual questions
        answers = clean_and_format_data(answers)
        print("CLEANED API RESPONSE:\n\n", answers)

        question_id_answer_map = {}
        ans_map = {idx + 1: answer for idx, answer in enumerate(answers)}
        if answers:
            for question_id in question_ids:
                if question_id in ans_map:
                    question_id_answer_map[question_id] = ans_map[question_id]
            store_api_responses(question_ids, ans_map, document_id)  # Store the new answers
        else:
            # If all new answers are empty strings
            return render(request, 'core/generate_answers.html', {
                'error': "No valid answers generated for the provided questions.",
                'question_answer_map': {}
            })

        question_answer_map = {}
        for question_id in question_ids:
            if question_id in ans_map and question_id <= len(ans_map.keys()):
                question_answer_map[question_id] = {'question': questions_list[question_id - 1], 'answer': ans_map[question_id], }
        
        pdf_file_path = os.path.join(settings.MEDIA_ROOT, f"answers/answers_{document.id}.pdf")
        pdf_file_path = generate_question_bank_pdf(
            [item['question'] for item in question_answer_map.values()],
            [item['answer'] for item in question_answer_map.values()],
            document.id
        )

        return render(request, 'core/generate_answers.html', {
            'question_answer_map': question_answer_map,
            'viewing_answers': True,
            'document' : document,
            'document_id': document_id,
            'pdf_file_path': pdf_file_path,
        })

    return render(request, 'core/generate_answers.html', {
        'error': "Invalid request method.",
        'question_answer_map': {}
    })

def edit_file_details(request, file_id):
    
    return render(request, 'core/edit_file_details.html')

from weasyprint import HTML, CSS

def generate_question_bank_pdf(questions, answers, document_id, metadata=None):
    print("Generating enhanced question bank PDF...")
    media_dir = settings.MEDIA_ROOT
    answers_dir = os.path.join(media_dir, "answers")
    
    # Ensure directory exists
    os.makedirs(answers_dir, exist_ok=True)

    # Create HTML content for the PDF
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>University Question Bank</title>
        <style>
            body {{
                font-family: 'Open Sans', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f7f8;
                color: #333;
    line-height: 1.6;
            }}

.header {{
    background-color: #007bff;
    color: white;
    padding: 20px;
    text-align: center;
}}

.header h1 {{
    font-size: 2.5em;
    margin: 0;
}}

.container {{
    width: 80%;
    margin: 0 auto;
    padding: 20px;
    background: white;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
}}

h2 {{
    color: #007bff;
    border-bottom: 2px solid #007bff;
    padding-bottom: 10px;
}}

.table-of-contents {{
    margin: 20px 0;
}}

.table-of-contents ul {{
    list-style-type: none;
    padding: 0;
}}

.table-of-contents li {{
    margin: 5px 0;
}}

.table-of-contents li a {{
    text-decoration: none;
    color: #007bff;
}}

.table-of-contents li a:hover {{
    text-decoration: underline;
}}

.question-answer-section {{
    margin: 30px 0;
}}

.question {{
    background-color: #e9ecef;
    border-left: 5px solid #007bff;
    padding: 15px;
    margin: 15px 0;
    border-radius: 5px;
}}

.answer {{
    background-color: #f8f9fa;
    padding: 15px;
    margin: 10px 0 20px;
    border-radius: 5px;
    border: 1px solid #dee2e6;
}}

.footer {{
    margin-top: 20px;
    text-align: center;
    padding: 20px;
    font-size: 0.9em;
    background-color: #007bff;
    color: white;
    position: relative;
}}

.footer p {{
    margin: 0;
}}

@media (max-width: 768px) {{
    .container {{
        width: 90%;
    }}

    .header h1 {{
        font-size: 2em;
    }}
}}

        </style>
    </head>
    <body>
        <div class="cover">
            <h1>Assignment Mate</h1>
            <h2>A comprehensive compilation of important questions</h2>
            {generate_metadata_section(metadata)}
        </div>
        <div class="toc">
            <h3 class="toc-header">Table of Contents</h3>
            {generate_toc(questions)}
        </div>
        <div class="content">
            <h3>Questions and Answers</h3>
            {generate_questions_answers(questions, answers)}
        </div>
        <div class="footer">
            <p>Generated by Your Application</p>
        </div>
    </body>
    </html>
    """

    # Create PDF
    pdf_filename = f"answers_{document_id}.pdf"
    pdf_output = os.path.join(answers_dir, pdf_filename)
    
    HTML(string=html_content).write_pdf(pdf_output, stylesheets=[CSS(string='body { font-family: "Open Sans"; }')])
    print(f"PDF generated successfully: {pdf_filename}")
        
    # Update document record
    document = Document.objects.get(id=document_id)
    document.answers = f"answers/{pdf_filename}"
    document.save()
    
def generate_metadata_section(metadata):
    if metadata:
        section = "<div>"
        for key, value in metadata.items():
            section += f"<p>{key}: {value}</p>"
        section += "</div>"
        return section
    return ""

def generate_toc(questions):
    toc = "<ul>"
    for i, question in enumerate(questions, start=1):
        truncated_question = (question[:60] + '...') if len(question) > 60 else question
        toc += f"<li>{i}. {truncated_question}</li>"
    toc += "</ul>"
    return toc

def generate_questions_answers(questions, answers):
    content = ""
    for i, (question, answer) in enumerate(zip(questions, answers), start=1):
        content += f"<div class='question-answer'><div class='question'>{i}. {question}</div><div class='answer'>{answer}</div></div>"
    return content




def store_api_responses(questions_ids, answer_map, document_id):
    print("Storing API responses.")
    print(questions_ids)
    for question_id in questions_ids:
        if question_id in answer_map:
            APIResponse.objects.update_or_create(
                document_id=document_id,
                question_id=question_id,
                defaults={'answer': str(answer_map[question_id])}
            )

@login_required
def get_cached_answers(question_ids):
    print("Fetching cached answers.")
    answers = []
    for question_id in question_ids:
        try:
            cache_entry = APIResponse.objects.get(question_id=question_id)
            answers.append(cache_entry.answer)
        except APIResponse.DoesNotExist:
            answers.append(None)
    return [answer for answer in answers if answer is not None]

from groq import Groq

def get_answers_from_gemini(questions, ans_detailing):
    print("Fetching answers from Groq.")
    client = Groq()
    prompt = f"Generate {ans_detailing} form answers for these questions and Generate each answer for each question in HTML format. Include the necessary tags to make it display-ready for web templates." + ', '.join(questions)

    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=1,
            max_tokens=4000,
            top_p=1,
            stream=False,  # Set to False to get the full response at once
            stop=None,
        )

        # Correctly extract the content from the response
        answers = completion.choices[0].message.content.strip()  # Use dot notation
        return answers # Assuming each answer is on a new line

    except Exception as e:
        print("An error occurred:", e)
        return ['An error occurred. Please try again.']

'''CLEANING PIPELINE'''
import re
from bs4 import BeautifulSoup

def clean_single_answer_response(response_text):
    """Extract and clean relevant HTML formatted text from the response."""
    # Define patterns to remove common noise phrases from model responses
    response_patterns = [
        r'Here is the answer to the question.*',  # General introductory phrases
        r'I hope this helps!',  # Closing phrases
        r'Let me know if you have any further questions or need any modifications.',  # Closing suggestion
        r'In summary,.*',  # Summary or conclusion starters
        r'Here are some insights.*',  # Introductory insight phrases
        r'The following are key points.*',  # Key points starters
        r'Additionally,.*',  # Additional info starters
        r'Please note that.*',  # Disclaimers
        r'Here is the answer in HTML format:*',  # Format indicators
        r'Note*',  # General notes
        r'Here are the*',  # List starters
        r'Let me know if you need any further assistance*',  # Offers for further help
        r'know if you need any changes or further assistance!*',  # Further assistance offers
        r': The HTML code generated is a simple comparison container that includes headings, lists, and spans to format the text. You can customize the design and style to fit your web template.*',
        r'Answer in HTML format:',  # Format indicators
        r'know if you have any further requests.',  # Further requests
        # Add additional patterns as needed for other model-specific phrases
    ]
    
    # Compile the patterns into a single regex pattern
    combined_pattern = re.compile('|'.join(response_patterns), re.IGNORECASE)
    
    # Remove unwanted phrases
    cleaned_response = combined_pattern.sub('', response_text)
    
    # Parse the cleaned response with BeautifulSoup
    soup = BeautifulSoup(cleaned_response, "html.parser")
    
    # Remove specific unwanted tags while preserving their content
    for tag in soup.find_all(['code', 'q']):
        tag.unwrap()  # Remove <code> and <q> tags but keep the content
    
    # Additional cleaning: remove empty tags and unnecessary whitespace
    for tag in soup.find_all():
        if not tag.get_text(strip=True):
            tag.decompose()  # Remove empty tags
        else:
            tag.attrs = {}  # Remove all attributes from tags to clean up the HTML

    # Convert the cleaned HTML back to a string
    cleaned_html = str(soup)
    
    # Return the cleaned HTML wrapped in a list
    return [cleaned_html]

# Note: Ensure that you have BeautifulSoup installed:
# pip install beautifulsoup4

import re
from bs4 import BeautifulSoup

def normalize_text(raw_text):
    """Minimal normalization for HTML-formatted content."""
    # Remove unnecessary whitespace
    return re.sub(r'\s+', ' ', raw_text).strip()

def extract_questions_and_answers(normalized_text):
    """Extract questions and answers from HTML content."""
    soup = BeautifulSoup(normalized_text, "html.parser")
    questions = soup.find_all(['h2', 'h3'])
    
    qa_pairs = []
    for question in questions:
        answer_content = ""
        sibling = question.find_next_sibling()
        
        while sibling and sibling.name not in ['h2', 'h3']:
            answer_content += str(sibling)
            sibling = sibling.find_next_sibling()
        
        qa_pairs.append((question.get_text(strip=True), answer_content.strip()))
    
    return qa_pairs

def clean_single_answer_response_in_pipeline(response_text):
    """Extract and clean relevant HTML formatted text from the response."""
    # Define patterns to remove common noise phrases from model responses
    response_patterns = [
        r'Here is the answer to the question.*',  # General introductory phrases
        r'I hope this helps!',  # Closing phrases
        r'Let me know if you have any further questions or need any modifications.',  # Closing suggestion
        r'In summary,.*',  # Summary or conclusion starters
        r'Here are some insights.*',  # Introductory insight phrases
        r'The following are key points.*',  # Key points starters
        r'Additionally,.*',  # Additional info starters
        r'Please note that.*',  # Disclaimers
        r'Here is the answer in HTML format:*',  # Format indicators
        r'Note*',  # General notes
        r'Here are the*',  # List starters
        r'Let me*',  # Offers for further help
        r'know if you need any changes or further assistance!*',  # Further assistance offers
        r': The HTML code generated is a simple comparison container that includes headings, lists, and spans to format the text. You can customize the design and style to fit your web template.*',
        r'Answer in HTML format:',  # Format indicators
        r'know if you have any further requests.',  # Further requests
        # Add additional patterns as needed for other model-specific phrases
    ]
    
    # Compile the patterns into a single regex pattern
    combined_pattern = re.compile('|'.join(response_patterns), re.IGNORECASE)
    
    # Remove unwanted phrases
    cleaned_response = combined_pattern.sub('', response_text)
    
    # Parse the cleaned response with Beaut
    soup = BeautifulSoup(cleaned_response, "html.parser")
    
    # Remove specific unwanted tags while preserving their content
    for tag in soup.find_all(['code', 'q']):
        tag.unwrap()  # Remove <code> and <q> tags but keep the content
    
    # Additional cleaning: remove empty tags and unnecessary whitespace
    for tag in soup.find_all():
        if not tag.get_text(strip=True):
            tag.decompose()  # Remove empty tags
        else:
            tag.attrs = {}  # Remove all attributes from tags to clean up the HTML

    # Convert the cleaned HTML back to a string
    cleaned_html = str(soup)
    
    # Return the cleaned HTML wrapped in a list
    return [cleaned_html]

import re
from bs4 import BeautifulSoup

def clean_and_format_data(raw_response):
    # Remove any leading or trailing whitespace
    raw_response = raw_response.strip()

    # Remove any unnecessary text before the actual HTML content
    html_start_index = raw_response.find('<')
    if html_start_index != -1:
        raw_response = raw_response[html_start_index:]

    # Parse the HTML response
    soup = BeautifulSoup(raw_response, 'html.parser')

    # Find all the answer sections
    answer_sections = soup.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'div'])

    cleaned_answers = []
    current_answer = ''

    for section in answer_sections:
        if section.name.startswith('h') or section.name == 'div':
            if current_answer.strip():
                cleaned_answers.append(current_answer.strip())
            current_answer = ''
        else:
            current_answer += str(section)

    if current_answer.strip():
        cleaned_answers.append(current_answer.strip())

    # Additional cleaning and formatting
    cleaned_answers = [re.sub(r'\n+', '\n', answer) for answer in cleaned_answers]  # Remove excessive newline characters
    cleaned_answers = [re.sub(r'\s+', ' ', answer) for answer in cleaned_answers]  # Remove excessive whitespace
    cleaned_answers = [answer.replace('**', '').strip() for answer in cleaned_answers]  # Remove any remaining Markdown formatting
    cleaned_answers = [re.sub(r'</?strongda>', '', answer) for answer in cleaned_answers]  # Remove invalid closing tags
    cleaned_answers = [re.sub(r'</?strong_.*?>', '', answer) for answer in cleaned_answers]  # Remove invalid opening tags

    return cleaned_answers



def convert_to_html(cleaned_data):
    """Format structured data into the final HTML format."""
    html_data = []
    for entry in cleaned_data:
        title_html = f"<strong>{entry['title']}</strong>"
        content_html = entry['content']
        html_data.append(f"{title_html}\n{content_html}")
    
    return html_data



'''QUESTION EXTRACTION PIPELINE'''
def extract_text_from_pdf(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    return text

def merge_multiline_questions(lines):
    """Merge lines that appear to be continuations of previous questions."""
    merged_lines = []
    current_question = ""
    
    for line in lines:
        if re.match(r'^\d+(\.|:|)\s', line) or re.match(r'^\s*(Q\d+\.?)', line):
            # Start of a new question, save current and reset
            if current_question:
                merged_lines.append(current_question.strip())
            current_question = line
        else:
            # Continuation of the current question
            current_question += " " + line.strip()
    
    # Append any remaining question
    if current_question:
        merged_lines.append(current_question.strip())
    
    return merged_lines

def filter_noise(text):
    """Remove headers, footers, and module sections."""
    noise_patterns = [
        r"Module\s+\d+",                # Module headers like "Module 5"
        r"SL\.NO",                      # Table headers like "SL.NO"
        r"Page\s+\d+",                  # Page numbers
        r"^.*?\b(footer|header)\b.*?$", # General footer/header lines
        r"\b(L[1-9]|L10|CO[1-9]|CO10)\b",
        r"(Course Coordinator|Module Coordinator|Program Coordinator\/ HOD)",

    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text.strip()

def extract_numbered_questions(text):
    """Extract numbered questions, handling multi-line text."""
    # Split text into lines for line-based merging
    lines = text.splitlines()
    merged_lines = merge_multiline_questions(lines)

    # Regex to capture questions starting with numbers or "Qx"
    question_pattern = re.compile(r'^\d+(\.|:|)\s+|^Q\d+\.?', re.IGNORECASE)
    questions = [
        re.sub(r'^\d+(\.|:|)\s*', '', line).strip()  # Remove the leading number and punctuation
        for line in merged_lines
        if question_pattern.match(line) and len(line.split()) > 3
    ]
    
    return questions


def detect_questions_spacy(text):
    """Use spaCy to identify sentences ending in question marks."""
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip().endswith("?")]

from collections import OrderedDict
def extract_questions(pdf_path):
    """Main function to extract questions from PDF with robust filtering."""
    raw_text = extract_text_from_pdf(pdf_path)
    clean_text = filter_noise(raw_text)
    # Extract numbered and non-numbered questions
    numbered_questions = extract_numbered_questions(clean_text)
    nlp_detected_questions = detect_questions_spacy(clean_text)


    # Combine and deduplicate questions
    all_questions = list(set(numbered_questions + nlp_detected_questions))
    all_questions = list(OrderedDict.fromkeys(all_questions))
    
    question_id_mapping = []
    for index, question in enumerate(all_questions, start=1):
        question_id_mapping.append((index, question))
    return question_id_mapping