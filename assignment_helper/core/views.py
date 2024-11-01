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
    if not os.path.exists(pdf_file_path):
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
            ans_detailing = data.get('ans_detailing')  # Assuming you send document_id in the request
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
        answers = get_answers_from_gemini(questions_list) 
         # Pass the actual questions
        answers = clean_and_format_data(answers)
        print("SPI RESPONSE:\n\n", answers)

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
                question_answer_map[questions_list[question_id - 1]] = ans_map[question_id]

        return render(request, 'core/generate_answers.html', {
            'question_answer_map': question_answer_map,
            'viewing_answers': True,
            'document' : document,
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
    prompt = f"Generate medium form answers for these questions and Generate each answer for each question in HTML format. Include the necessary tags to make it display-ready for web templates." + ', '.join(questions)

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
from bs4 import BeautifulSoup

def clean_single_answer_response(response_text):
    """Clean and format the response treating the entire content as a single answer."""
    response_patterns = [
        r'Here is the answer to the question.*',  # General introductory phrases
        r'I hope this helps!',  # Closing phrases
        r'Let me know if you have any further questions or need any modifications.',  # Closing suggestion
        r'In summary,.*',  # Summary or conclusion starters
        r'Here are some insights.*',  # Introductory insight phrases
        r'The following are key points.*',  # Key points starters
        r'Additionally,.*',  # Additional info starters
        r'Please note that.*',  # Notes or disclaimers
        # Add additional patterns as needed for other chatbot response phrases
    ]
    
    combined_pattern = re.compile('|'.join(response_patterns), re.IGNORECASE)
    cleaned_response = combined_pattern.sub('', response_text)
    soup = BeautifulSoup(cleaned_response, "html.parser")
    
    # Remove specific unwanted tags while preserving their content
    for tag in soup.find_all(['code', 'q']):
        tag.unwrap()  # Remove <code> and <q> tags but keep the content
    
    # Convert the cleaned HTML back to a string
    cleaned_answer = str(soup)
    
    # Return the cleaned answer wrapped in a list
    return [cleaned_answer]

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

def clean_and_format_data(raw_response):
    """Directly use HTML content to structure data with HTML formatting."""
    normalized_text = normalize_text(raw_response)
    qa_pairs = extract_questions_and_answers(normalized_text)
    
    structured_data = []
    for question, answer in qa_pairs:
        structured_data.append({'title': question, 'content': answer})
    
    return convert_to_html(structured_data)

def convert_to_html(cleaned_data):
    """Format structured data into the final HTML format."""
    html_data = []
    for entry in cleaned_data:
        title_html = f"<strong>{entry['title']}</strong>"
        content_html = f"<p>{entry['content']}</p>"
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