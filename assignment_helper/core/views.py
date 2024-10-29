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

# Configure the Gemini API
genai.configure(api_key=os.environ['API_KEY'])

# Load the English NLP model
nlp = spacy.load("en_core_web_sm")
# Load English words list
english_words = set(words.words())

# views.py
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import CustomLoginForm

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('upload_pdf')  # Redirect to the upload PDF page or any other page
            else:
                form.add_error(None, "Invalid username or password.")
    else:
        form = CustomLoginForm()
    return render(request, 'core/login.html', {'form': form})

# Question Bank PDF class (remains unchanged)
class QuestionBankPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_fonts()

    def add_fonts(self):
        font_path = os.path.join(settings.BASE_DIR, 'core/fonts')
        self.add_font('OpenSans', '', os.path.join(font_path, 'OpenSans-Regular.ttf'), uni=True)
        self.add_font('OpenSans', 'B', os.path.join(font_path, 'OpenSans-Bold.ttf'), uni=True)
        self.add_font('OpenSans', 'I', os.path.join(font_path, 'OpenSans-Italic.ttf'), uni=True)

    def header(self):
        logo_path = os.path.join(settings.BASE_DIR, 'logo.png') 
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)
        self.set_font("OpenSans", 'B', 12)
        self.cell(0, 10, 'RNS INSTITUTE OF TECHNOLOGY', 0, 1, 'C')
        self.cell(0, 10, 'Autonomous Institution Affiliated to VTU', 0, 1, 'C')
        self.cell(0, 10, 'Assignment 2: CLOUD COMPUTING', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("OpenSans", '', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, num, title):
        self.set_font('OpenSans', 'B', 14)
        self.set_text_color(20, 20, 20)
        self.cell(0, 10, f'Question {num}:', 0, 1, 'L')
        self.set_font('OpenSans', 'B', 12)
        self.multi_cell(0, 10, title)
        self.ln(4)

    def add_question(self, num, question, answer=None):
        self.chapter_title(num, question + '?')
        if answer:
            self.set_font('OpenSans', '', 12)
            self.set_text_color(30, 30, 30)
            self.multi_cell(0, 10, f'Answer: {answer}')
            self.ln(5)

def index(request):
    print("Rendering index page.")
    return render(request, 'core/index.html')

from django.db import IntegrityError

@login_required
def upload_pdf(request):
    print("Upload PDF view accessed.")
    uploaded_files = Document.objects.filter(user=request.user)
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
            questions = extract_questions(pdf_file)
            print(f"Extracted questions: {questions}")

            # Store the new questions in the database
            for i, question_text in enumerate(questions):
                try:
                    # Create a new APIResponse entry for each question
                    APIResponse.objects.create(
                        document=document,
                        question=question_text,
                        question_id=i + 1  # Assign a new unique question ID
                    )
                    print(f"Stored question: {question_text}")
                except IntegrityError:
                    print(f"IntegrityError for question: {question_text} with document ID: {document.id}")
                    continue  # Skip to the next question if an integrity error occurs

            # Store questions in the session
            request.session['questions'] = list(questions)
            request.session['document_id'] = document.id
            print(f"Questions stored in session for document ID {document.id}.")

            # Render the success page with questions
            return render(request, 'core/upload_success.html', {
                'questions': questions,
                'extracted_text': None,
            })
    else:
        form = PDFUploadForm()

    return render(request, 'core/upload_pdf.html', {'form': form, 'uploaded_files': uploaded_files})

def saved_files(request):
    print("Accessing saved files.")
    uploaded_files = Document.objects.exclude(name='Default Document')
    context = {'uploaded_files': uploaded_files}
    return render(request, 'core/saved_files.html', context)

def get_uploaded_files(request):
    print("Fetching uploaded files.")
    files = Document.objects.all().order_by('-uploaded_at')
    file_list = [{
        'id': file.id,
        'name': file.name,
        'upload_time': file.uploaded_at,
        'delete_url': reverse('delete_file', args=[file.id]),
        'view_answers_url': reverse('view_answers', args=[file.id]),
        'download_url': reverse('download_file', args=[file.id]),
    } for file in files]
    return JsonResponse(file_list, safe=False)

def delete_file(request, file_id):
    print(f"Deleting file with ID: {file_id}.")
    document = get_object_or_404(Document, id=file_id)
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
    return redirect('upload_pdf')

def download_file(request, file_id):
    print(f"Downloading file with ID: {file_id}.")
    document = get_object_or_404(Document, id=file_id)

    if document.answers:
        file_path = document.answers.path
        if os.path.isfile(file_path):
            response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="answers_{document.id}.pdf"'
            return response
        else:
            return JsonResponse({'error': 'Answer file not found.'}, status=404)

    questions_and_answers = APIResponse.objects.filter(document=document)
    if not questions_and_answers.exists():
        return JsonResponse({'error': 'No questions and answers found for this document.'}, status=404)

    questions = [q.question for q in questions_and_answers]
    answers = [a.answer for a in questions_and_answers]

    return generate_question_bank_pdf(questions, answers, document.id)

def view_answers(request, file_id):
    print(f"Viewing answers for file with ID: {file_id}.")
    document = get_object_or_404(Document, id=file_id)
    answers = document.api_responses.all()

    questions = [response.question for response in answers]
    for question in questions:
        if question[0].isdigit():
            question = question[1:]
    
    formatted_answers = [response.answer for response in answers]

    question_answer_map = dict(zip(questions, formatted_answers))

    pdf_file_path = os.path.join(settings.MEDIA_ROOT, f"answers/answers_{document.id}.pdf")
    if not os.path.exists(pdf_file_path):
        pdf_file_path = generate_question_bank_pdf(questions, formatted_answers, document.id)

    return render(request, 'core/generate_answers.html', {
        'document': document,
        'question_answer_map': question_answer_map,
        'pdf_file_path': pdf_file_path,
        'viewing_answers': True,
        'formatted_answers': formatted_answers,
    })

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
                api_response = APIResponse.objects.get(document_id=document_id, question_id=question_id)
                api_response.question = question_text
                api_response.save()
                print(f"Question {question_id} updated to: {question_text}")
            except APIResponse.DoesNotExist:
                print(f"Question with ID {question_id} does not exist.")
                continue

        return JsonResponse({'success': True, 'message': "Questions updated successfully."})

    return JsonResponse({'error': "Invalid request method."}, status=400)

@login_required
def generate_answer(request):
    print("Generating answer for specific question.")
    if request.method == 'POST':
        try:
            question_data = json.loads(request.body)
            question = question_data.get('question')

            if not question:
                return JsonResponse({'error': 'No question provided.'}, status=400)

            # Fetch answer from the Gemini API
            answer = get_answers_from_gemini([question])
            answer = clean_and_format_data(answer)
            

            if answer and isinstance(answer, list) and len(answer) > 0:
                api_response = APIResponse.objects.get(question=question)
                api_response.answer = answer[0]
                api_response.save()
                return JsonResponse({'answer': answer[0]})  # Return the first answer
            else:
                return JsonResponse({'error': 'No answer generated.'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)

@login_required
def generate_answers(request):
    print("Generating answers.")
    if request.method == 'POST':
        document_id = request.session.get('document_id')
        if not document_id:
            return JsonResponse({'error': 'Document ID not found in session.'}, status=400)

        document = get_object_or_404(Document, id=document_id)

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
        questions = APIResponse.objects.filter(document_id=document_id, question_id__in=question_ids).values_list('question', flat=True)
        questions_list = list(questions)  # Convert to a list for easy processing

        print(f"Questions to process: {questions_list}")

        # Directly fetch new answers from the Gemini API using the actual questions
        answers = get_answers_from_gemini(questions_list) 
        print("RAW API RESPONSE:\n", answers, "\n\n")
         # Pass the actual questions
        answers = clean_and_format_data(answers)
        print("CLEANED API RESPONSE: \n", answers, "\n\n")

        question_id_answer_map = {}

        if answers:
            for question_id, answer in zip(question_ids, answers):
                question_id_answer_map[question_id] = str(answer)
            store_api_responses(question_ids, answers, document_id)  # Store the new answers
        else:
            # If all new answers are empty strings
            return render(request, 'core/generate_answers.html', {
                'error': "No valid answers generated for the provided questions.",
                'question_answer_map': {}
            })

        question_answer_map = {}
        for question, answer in zip(questions, answers):
            if question[0].isdigit():
                question = question[1:]
            question_answer_map[question] = answer

        return render(request, 'core/generate_answers.html', {
            'question_answer_map': question_answer_map,
            'viewing_answers': True,
        })

    return render(request, 'core/generate_answers.html', {
        'error': "Invalid request method.",
        'question_answer_map': {}
    })
def generate_question_bank_pdf(questions, answers, document_id):
    print("Generating question bank PDF.")
    media_dir = settings.MEDIA_ROOT
    answers_dir = os.path.join(media_dir, "answers")

    if not os.path.exists(answers_dir):
        os.makedirs(answers_dir)

    pdf = QuestionBankPDF()
    pdf.add_page()

    pdf.set_font("OpenSans", 'B', 20)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 20, 'University Question Bank', 0, 1, 'C')
    pdf.ln(10)

    pdf.set_font("OpenSans", 'I', 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, 'A compilation of important questions for review', 0, 1, 'C')
    pdf.ln(20)

    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("OpenSans", '', 12)

    for i, (question, answer) in enumerate(zip(questions, answers), start=1):
        pdf.add_question(i, question, answer)

    pdf_output = os.path.join(answers_dir, f"answers_{document_id}.pdf")
    pdf.output(pdf_output)

    document = Document.objects.get(id=document_id)
    document.answers = f"answers/answers_{document_id}.pdf"
    document.save()

    return FileResponse(open(pdf_output, 'rb'), content_type='application/pdf')

def store_api_responses(questions_ids, answers, document_id):
    print("Storing API responses.")
    print(questions_ids)
    print(answers)
    for question_id, answer in zip(questions_ids, answers):
        APIResponse.objects.update_or_create(
            document_id=document_id,
            question_id=question_id,
            defaults={'answer': answer}
        )

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

def get_answers_from_gemini(questions):
    print("Fetching answers from Gemini.")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            'Generate brief answers for these questions in exam answer format: ' + ', '.join(questions)
        )
        return response.text.strip()
        
    except google.api_core.exceptions.InvalidArgument as api_error:
        print(f"API Key Invalid: {api_error}")
        return ['API Key Invalid. Please check your credentials.']
    except Exception as e:
        print(f"An error occurred: {e}")
        return ['An error occurred. Please try again.']

import re

def clean_and_format_data(raw_data):
    print("Cleaning and formatting data.")
    answer_sections = re.split(r'\*\*\d+\.\s', raw_data)  # Split by numbered headers
    cleaned_answers = []
    
    for section in answer_sections:
        # Clean and format each section individually
        
        # Step 1: Remove unnecessary headers or markers like '## Exam Answers:' and asterisks
        section = re.sub(r'^\s*##\s+Exam\s+Answers:|[*#]+', '', section).strip()
        
        # Step 2: Clean unnecessary spaces or symbols from the beginning and end
        section = re.sub(r'^[^a-zA-Z0-9]*|[^a-zA-Z0-9]*$', '', section)
        
        # Step 3: Remove excess spaces between words and punctuation
        section = re.sub(r'\s+', ' ', section)
        
        # Step 4: Ensure items within answers (like points in bullet lists) are cleaned:
        section = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', section)  # Ensure proper sentence spacing
        
        # Step 5: Add the cleaned section to list if it's not empty
        if section:
            cleaned_answers.append(section)
    
    return cleaned_answers

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
    questions = [line for line in merged_lines if question_pattern.match(line) and len(line.split()) > 3]
    
    return questions


def detect_questions_spacy(text):
    """Use spaCy to identify sentences ending in question marks."""
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if sent.text.strip().endswith("?")]

def extract_questions(pdf_path):
    """Main function to extract questions from PDF with robust filtering."""
    raw_text = extract_text_from_pdf(pdf_path)
    clean_text = filter_noise(raw_text)
    # Extract numbered and non-numbered questions
    numbered_questions = extract_numbered_questions(clean_text)
    nlp_detected_questions = detect_questions_spacy(clean_text)


    # Combine and deduplicate questions
    all_questions = list(set(numbered_questions + nlp_detected_questions))
    return all_questions

