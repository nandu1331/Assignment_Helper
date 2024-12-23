from django.shortcuts import render, redirect, get_object_or_404
from .forms import PDFUploadForm
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
import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .forms import CustomLoginForm

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

import math
import datetime
class QuestionBankPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_fonts()
        # Enhanced color palette
        self.primary_color = (0, 51, 102)     # Navy Blue
        self.secondary_color = (70, 70, 70)    # Dark Gray
        self.accent_color = (0, 102, 204)      # Blue
        self.light_gray = (220, 220, 220)      # Light Gray
        self.success_color = (46, 125, 50)     # Green
        self.warning_color = (255, 153, 0)     # Orange
        self.highlight_color = (247, 247, 247) # Off-white
        
        # Set default margins
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=25)

    def add_fonts(self):
        font_path = os.path.join(settings.BASE_DIR, 'core/fonts')
        fonts = {
            'OpenSans': ['', 'B', 'I', 'BI'],
            'Roboto': ['', 'B'],
            'Lato': ['', 'B', 'I']
        }
        
        for font_name, styles in fonts.items():
            for style in styles:
                filename = f'{font_name}-{style if style else "Regular"}.ttf'
                self.add_font(font_name, style, os.path.join(font_path, filename), uni=True)

    def header(self):
        # Gradient header background
        self.set_fill_color(*self.light_gray)
        self.rect(0, 0, 210, 45, 'F')
        
        # Add decorative line
        self.set_draw_color(*self.accent_color)
        self.set_line_width(0.5)
        self.line(10, 44, 200, 44)
        
        # Logo with shadow effect
        logo_path = os.path.join(settings.BASE_DIR, 'logo.png')
        if os.path.exists(logo_path):
            self.image(logo_path, 12, 8, 30)
            # Add shadow effect
            self.set_fill_color(200, 200, 200)
            self.rect(13, 9, 30, 30, 'F')
            self.image(logo_path, 12, 8, 30)

        # Header Text with enhanced typography
        self.set_font("OpenSans", 'B', 18)
        self.set_text_color(*self.primary_color)
        self.cell(40)  # Space for logo
        self.cell(0, 12, 'RNS INSTITUTE OF TECHNOLOGY', 0, 1, 'C')
        
        self.set_font("Lato", 'I', 12)
        self.set_text_color(*self.secondary_color)
        self.cell(40)
        self.cell(0, 8, 'Autonomous Institution Affiliated to VTU', 0, 1, 'C')
        
        self.set_font("Roboto", 'B', 14)
        self.set_text_color(*self.accent_color)
        self.cell(40)
        self.cell(0, 8, 'Assignment 2: CLOUD COMPUTING', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-30)
        
        # Footer background
        self.set_fill_color(*self.highlight_color)
        self.rect(0, self.get_y(), 210, 30, 'F')
        
        # Add decorative elements
        self.set_draw_color(*self.accent_color)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        
        # Footer content
        self.set_font("OpenSans", '', 8)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 10, f'Generated using Assignment Mate - Page {self.page_no()}', 0, 1, 'C')

    def add_section_header(self, text, include_line=True):
        # Add subtle background
        self.set_fill_color(*self.highlight_color)
        self.rect(10, self.get_y(), 190, 12, 'F')
        
        # Section header text
        self.set_font('Roboto', 'B', 14)
        self.set_text_color(*self.primary_color)
        self.cell(0, 10, text, 0, 1, 'L')
        
        if include_line:
            self.set_draw_color(*self.accent_color)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
        
        self.ln(5)

    def chapter_title(self, num, title):
        # Question number with gradient background
        self.set_fill_color(*self.primary_color)
        self.set_font('OpenSans', 'B', 14)
        self.set_text_color(255, 255, 255)
        
        # Add rounded rectangle for question number
        self.rounded_rect(10, self.get_y(), 45, 10, 2, 'F')
        self.cell(45, 10, f'Question {num}', 0, 0, 'C')
        
        # Question text with subtle background
        self.ln(12)
        self.set_fill_color(*self.highlight_color)
        self.set_font('OpenSans', 'B', 12)
        self.set_text_color(*self.secondary_color)
        self.multi_cell(0, 10, title, border='B', fill=True)
        self.ln(4)

    def write_html(self, html_text):
        """
            Enhanced HTML parser and writer with recursion protection
        """
        soup = BeautifulSoup(html_text, 'html.parser')
                    
        def write_paragraph(text, indent=0, style=''):
            """Helper function to write paragraphs with proper formatting"""
            self.set_x(20 + indent)
            self.set_font('OpenSans', style, 11)
            self.multi_cell(170 - indent, 8, text.strip(), align='J')
            self.ln(4)

        def process_element(element, list_level=0):
            """Process individual elements with recursion protection"""
            if not element or (not element.name and not element.string):
                return
                            
                        # Handle headings
            if element.name in ['h1', 'h2', 'h3', 'h4']:
                self.ln(5)
                size = 16 - (int(element.name[1]) * 2)
                self.set_font('Roboto', 'B', size)
                self.set_text_color(*self.primary_color)
                write_paragraph(element.text, indent=0)
                self.set_text_color(*self.secondary_color)
                self.ln(5)
                        
                        # Handle bold text
            elif element.name in ['strong', 'b']:
                self.set_font('OpenSans', 'B', 11)
                self.write(8, element.get_text(strip=True) + ' ')
                self.set_font('OpenSans', '', 11)
                        
                        # Handle italic text
            elif element.name in ['em', 'i']:
                self.set_font('OpenSans', 'I', 11)
                self.write(8, element.get_text(strip=True) + ' ')
                self.set_font('OpenSans', '', 11)
                        
                        # Handle unordered lists
            elif element.name == 'ul':
                self.ln(5)
                for li in element.find_all('li', recursive=False):
                    bullet = '•' if list_level == 0 else '◦' if list_level == 1 else '‣'
                    self.set_x(20 + ((list_level + 1) * 10))
                    self.set_font('OpenSans', '', 11)
                    self.write(8, f'{bullet} {li.get_text(strip=True)}')
                    self.ln(8)
                self.ln(5)
                        
                        # Handle ordered lists
            elif element.name == 'ol':
                self.ln(5)
                for i, li in enumerate(element.find_all('li', recursive=False), 1):
                    self.set_x(20 + ((list_level + 1) * 10))
                    self.set_font('OpenSans', '', 11)
                    self.write(8, f'{i}. {li.get_text(strip=True)}')
                    self.ln(8)
                self.ln(5)
                        
                        # Handle paragraphs
            elif element.name == 'p':
                self.ln(2)
                write_paragraph(element.get_text(strip=True))
                self.ln(4)
                        
                        # Handle plain text
            elif element.string and element.string.strip():
                text = element.string.strip()
                if text:
                    current_x = self.get_x()
                    if current_x == self.l_margin:
                        self.set_x(20)
                    self.write(8, text + ' ')

                    # Process top-level elements only
        for element in soup.children:
            process_element(element)
                                
                    # Ensure proper spacing after all content
        self.ln(4)



    def rounded_rect(self, x, y, w, h, r, style=''):
        # Helper method to draw rounded rectangles
        k = 0.4477
        self.set_line_width(0.5)
        
        self.line(x+r, y, x+w-r, y)
        self.line(x+r, y+h, x+w-r, y+h)
        self.line(x, y+r, x, y+h-r)
        self.line(x+w, y+r, x+w, y+h-r)
        

    def add_question(self, num, question, answer=None):
        if self.get_y() > 250:
            self.add_page()

        self.chapter_title(num, question + '?')
        
        if answer:
            # Answer section with enhanced formatting
            self.set_font('Roboto', 'B', 12)
            self.set_text_color(*self.success_color)
            self.cell(0, 10, 'Answer:', 0, 1, 'L')
            
            # Add subtle background for answer
            answer_height = self.get_string_height(answer, 170)
            self.set_fill_color(*self.highlight_color)
            self.rect(20, self.get_y(), 170, answer_height + 10, 'F')
            
            # Answer content with HTML support
            self.set_font('OpenSans', '', 11)
            self.set_text_color(*self.secondary_color)
            self.set_x(25)
            
            # Handle HTML content
            self.write_html(answer)
            
            # Spacing and separator
            self.ln(10)
            self.draw_separator()
            self.ln(10)

    import math
    def get_string_height(self, text, width):
        """Calculate height needed for HTML text"""
        soup = BeautifulSoup(text, 'html.parser')
        plain_text = soup.get_text('\n')
        lines = 0
        
        # Count lines in paragraphs
        paragraphs = plain_text.split('\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                lines += math.ceil(self.get_string_width(paragraph) / width)
        
        # Add extra space for lists
        lines += len(soup.find_all(['li'])) * 1.2
        
        return lines * 8

    def draw_separator(self):
        # Draw decorative separator
        self.set_draw_color(*self.light_gray)
        self.set_line_width(0.5)
        
        # Dotted line effect
        x = 10
        while x < 200:
            self.line(x, self.get_y(), x + 3, self.get_y())
            x += 6



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
            <h1>University Question Bank</h1>
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


from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import IntegrityError
from .models import Quiz, QuizAttempt, Question
from django.views.decorators.csrf import csrf_exempt
import json

# Quiz Home
def quiz_home(request):
    """Render the quiz generator template."""
    recent_quizzes = Quiz.objects.order_by('-created_at')[:5]
    return render(request, 'core/quiz_generator.html', {'recent_quizzes': recent_quizzes})


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Quiz, QuizAttempt

@login_required
def attempt_quiz(request, quiz_id):
    """Handle quiz attempts."""
    # Get the quiz object, return 404 if not found
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Check if the quiz is active
    if not quiz.is_active:
        messages.error(request, "This quiz is no longer available.")
        return redirect('quiz_home')

    # Check if the user has already attempted the quiz
    if QuizAttempt.objects.filter(quiz=quiz, user=request.user).exists():
        return redirect('quiz_results', quiz_id=quiz_id)

    # Get the questions for the quiz
    questions = quiz.questions.all()

    # Ensure there are questions for the quiz
    if not questions:
        messages.error(request, "This quiz has no questions. Please contact support.")
        return redirect('quiz_home')

    # Pass the quiz and questions to the template
    context = {
        'quiz': quiz,
        'questions': questions,
    }
    
    return render(request, 'core/quiz_attempt.html', context)


@login_required
def submit_quiz(request, quiz_id):
    """Handle quiz submission and scoring, updating an existing attempt if one exists."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        answers = data.get('answers', [])

        if not quiz_id:
            return JsonResponse({'error': 'Quiz ID is required'}, status=400)

        # Retrieve the quiz and questions
        quiz = get_object_or_404(Quiz, id=quiz_id)
        questions = quiz.questions.all()

        # Ensure there are questions in the quiz
        if not questions:
            return JsonResponse({'error': 'This quiz has no questions'}, status=400)

        # Calculate score
        correct_answers = 0
        incorrect_answers = []
        for answer in answers:
            question_index = answer.get('questionIndex')  # Frontend sends `questionIndex`
            selected_option = answer.get('selectedOption')

            # Validate the presence of questionIndex and selectedOption
            if question_index is None or selected_option is None:
                continue

            try:
                question = questions[question_index]  # Use index to get the question directly
                # Compare selected option with correct option
                if question.correct_option == selected_option:
                    correct_answers += 1
                else:
                    incorrect_answers.append({
                        'question': question.text,
                        'selectedOption': question.options[selected_option],
                        'correctOption': question.options[question.correct_option],
                        'explanation': question.explanation
                    })
            except IndexError:
                continue  # If the index is out of range, skip this answer

        total_questions = questions.count()
        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0

        # Check if the user has already attempted this quiz
        existing_attempt = QuizAttempt.objects.filter(quiz=quiz, user=request.user).first()
        if existing_attempt:
            # Update the existing attempt
            existing_attempt.score = score
            existing_attempt.answers = answers  # Update the answers field
            existing_attempt.save()
            attempt = existing_attempt  # Use the updated attempt
        else:
            # Create a new attempt
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                user=request.user,
                score=score,
                answers=answers,
            )

        # Return the response with quizId, score, and other details
        return JsonResponse({
            'quizId': quiz.id,
            'score': score,
            'correctAnswers': correct_answers,
            'totalQuestions': total_questions,
            'incorrectAnswers': incorrect_answers,
            'explanations': [
                {
                    'question': question.text,
                    'explanation': question.explanation
                } for question in questions
            ]
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in submit_quiz: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def quiz_results(request, quiz_id):
    """Display quiz results."""
    attempt = get_object_or_404(QuizAttempt, quiz_id=quiz_id, user=request.user)
    incorrect_questions = []

    # Identify incorrect questions
    for answer in attempt.answers:
        try:
            question_index = answer.get('questionIndex')  # Use `questionIndex` from answers
            selected_option = answer.get('selectedOption')

            # Ensure question_index exists and is valid
            if question_index is None:
                continue

            # Retrieve the question based on the index
            question = attempt.quiz.questions.all()[question_index]

            # Compare selected option with correct option
            if question.correct_option != selected_option:
                incorrect_questions.append({
                    'question': question.text,
                    'selectedOption': question.options[selected_option],
                    'correctOption': question.options[question.correct_option],
                    'explanation': question.explanation,
                })
        except Exception as e:
            continue

    context = {
        'attempt': attempt,
        'incorrect_questions': incorrect_questions,
        'time_taken': attempt.completed_at - attempt.started_at,
    }
    return render(request, 'core/quiz_results.html', context)

@login_required
def quiz_history(request):
    """Display user's quiz history with pagination."""
    attempts = QuizAttempt.objects.filter(user=request.user).select_related('quiz').order_by('-completed_at')
    paginator = Paginator(attempts, 10)  # 10 attempts per page
    page = request.GET.get('page')
    attempts_page = paginator.get_page(page)

    # Cache user statistics
    cache_key = f'user_stats_{request.user.id}'
    user_stats = cache.get(cache_key)
    if not user_stats:
        user_stats = QuizAttempt.get_user_statistics(request.user)
        cache.set(cache_key, user_stats, 3600)  # Cache for 1 hour

    context = {
        'attempts': attempts_page,
        'statistics': user_stats,
    }
    return render(request, 'core/quiz_history.html', context)


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from .models import Quiz, Question
import json # Assuming the generator is imported from a separate module

@csrf_protect
def generate_quiz(request):
    """Generate a new quiz."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        # Parse JSON request body
        data = json.loads(request.body)
        topic = data.get('topic')
        context = data.get('context', '')

        # Validate input
        if not topic:
            return JsonResponse({'error': 'Topic is required'}, status=400)

        # Use the existing QuizGenerator class to generate the quiz
        quiz_generator = QuizGenerator()
        quiz_data = quiz_generator.generate_quiz(topic, context)

        # Validate quiz data
        if not quiz_data or 'questions' not in quiz_data:
            return JsonResponse({'error': 'Failed to generate quiz, please try again.'}, status=500)

        # Create a Quiz object
        quiz = Quiz.objects.create(
            title=quiz_data['title'],
            topic=topic,
            context=context,
            created_by=request.user,
        )

        # Create Question objects
        for question in quiz_data['questions']:
            Question.objects.create(
                quiz=quiz,
                text=question['text'],
                options=question['options'],
                correct_option=question['correctOption'],
                explanation=question.get('explanation', ''),
            )

        # Return the generated quiz details
        return JsonResponse({
            'quizId': quiz.id,
            'title': quiz.title,
            'context': quiz.context,
            'quizUrl': f"/quiz/attempt/{quiz.id}/",  # Return a URL to redirect to attempt page
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        # Catch any other exceptions
        print(f"Error in generate_quiz: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred. Please try again later.'}, status=500)

class QuizGenerator:
    def __init__(self):
        self.client = Groq()
    
    def generate_quiz(self, topic, context=None):
        print("Fetching quiz from Groq.")
        prompt = f"""Generate a quiz about {topic}. 
        {f'Additional context: {context}' if context else ''}
        
        Create a JSON response with the following structure:
        {{
            "title": "Quiz title",
            "timeLimit": 600,
            "questions": [
                {{
                    "text": "Question text",
                    "options": ["option1", "option2", "option3", "option4"],
                    "correctOption": 0,
                    "explanation": "Explanation for the correct answer"
                }}
            ]
        }}
        
        Generate 10 questions with 4 options each. Ensure questions are challenging but fair.
        Important: Return only the JSON object, no additional text before or after.
        """
    
        try:
            completion = self.client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_tokens=4000,
                top_p=1,
                stream=False,
                stop=None,
            )
            
            # Extract content and clean it
            raw_response = completion.choices[0].message.content.strip()
            print("Raw response from Groq:", raw_response)
            
            def extract_json(text):
                # Helper function to extract and validate JSON
                def find_json_boundaries(s):
                    # Find all potential JSON start positions
                    starts = [i for i, char in enumerate(s) if char == '{']
                    # Find all potential JSON end positions
                    ends = [i + 1 for i, char in enumerate(s) if char == '}']
                    
                    valid_jsons = []
                    
                    # Try all possible combinations of starts and ends
                    for start in starts:
                        for end in ends:
                            if end > start:
                                try:
                                    potential_json = s[start:end]
                                    # Quick check for balanced braces
                                    if potential_json.count('{') != potential_json.count('}'):
                                        continue
                                        
                                    parsed = json.loads(potential_json)
                                    
                                    # Validate required structure
                                    if all(key in parsed for key in ['title', 'timeLimit', 'questions']):
                                        if isinstance(parsed['questions'], list):
                                            # Validate question structure
                                            valid_questions = all(
                                                isinstance(q, dict) and
                                                all(key in q for key in ['text', 'options', 'correctOption', 'explanation'])
                                                for q in parsed['questions']
                                            )
                                            if valid_questions:
                                                valid_jsons.append((parsed, len(potential_json)))
                                                
                                except json.JSONDecodeError:
                                    continue
                                
                    # Return the longest valid JSON if found (assuming it's the most complete)
                    return max(valid_jsons, key=lambda x: x[1])[0] if valid_jsons else None
    
                # Clean common formatting issues
                text = text.replace('\n', ' ').replace('\r', ' ')
                text = re.sub(r'```json\s*|\s*```', '', text)  # Remove markdown code blocks
                text = re.sub(r'`', '', text)  # Remove backticks
                
                # Try to parse the entire text first
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
                
                # If that fails, try to find valid JSON within the text
                extracted_json = find_json_boundaries(text)
                if extracted_json:
                    return extracted_json
                
                # If still no valid JSON, try more aggressive cleaning
                text = re.sub(r'[^\x20-\x7E]', '', text)  # Remove non-printable characters
                text = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', '', text)  # Fix invalid escapes
                
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None
    
            # Try to extract and parse JSON
            quiz_data = extract_json(raw_response)
            
            if quiz_data:
                # Validate and sanitize the extracted data
                sanitized_data = {
                    "title": str(quiz_data.get("title", "Quiz"))[:200],  # Limit title length
                    "timeLimit": min(max(int(quiz_data.get("timeLimit", 600)), 60), 3600),  # Limit between 1-60 minutes
                    "questions": []
                }
                
                # Process questions
                for q in quiz_data.get("questions", [])[:10]:  # Limit to 5 questions
                    if isinstance(q, dict):
                        sanitized_question = {
                            "text": str(q.get("text", ""))[:500],  # Limit question length
                            "options": [str(opt)[:200] for opt in q.get("options", [])[:4]],  # Limit option length and count
                            "correctOption": min(max(int(q.get("correctOption", 0)), 0), 3),  # Ensure valid option index
                            "explanation": str(q.get("explanation", ""))[:500]  # Limit explanation length
                        }
                        sanitized_data["questions"].append(sanitized_question)
                
                return sanitized_data if sanitized_data["questions"] else None
                
            print("Failed to extract valid JSON from response")
            return None
            
        except Exception as e:
            print(f"Error in Groq API call: {str(e)}")
            return None
        
from .models import PDFChatSession, ChatMessage
from django.urls import reverse

@login_required
def pdf_chat_home(request):
    """Display user's PDF chat sessions and option to start new ones."""
    active_sessions = PDFChatSession.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('pdf_document')
    
    documents = Document.objects.filter(user=request.user)
    
    return render(request, 'core/home.html', {
        'active_sessions': active_sessions,
        'documents': documents
    })

@login_required
def create_chat_session(request):
    """Create a new PDF chat session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        
        if not document_id:
            return JsonResponse({'error': 'Document ID is required'}, status=400)
        
        # Get the document and verify ownership
        document = get_object_or_404(Document, id=document_id, user=request.user)
        
        # Create new chat session
        session = PDFChatSession.objects.create(
            user=request.user,
            pdf_document=document,
            is_active=True
        )
        
        # Return the redirect URL using the URL pattern name
        return JsonResponse({
            'session_id': session.id,
            'redirect_url': request.build_absolute_uri(
                reverse('chat_session', kwargs={'session_id': session.id})
            )
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def chat_session(request, session_id):
    """Handle individual chat sessions."""
    session = get_object_or_404(PDFChatSession, id=session_id, user=request.user)
    messages = ChatMessage.objects.filter(session=session)
    
    return render(request, 'core/session.html', {
        'session': session,
        'messages': messages,
        'document': session.pdf_document
    })

@login_required
def send_message(request, session_id):
    """Handle sending and receiving chat messages."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        session = get_object_or_404(PDFChatSession, id=session_id, user=request.user)
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Store user message
        ChatMessage.objects.create(
            session=session,
            sender='USER',
            message=user_message
        )
        
        # Process message with LLaMa
        try:
            ai_response, is_relevant = process_with_llama(user_message, session)
            # Convert bool to int for JSON serialization
            is_relevant_int = 1 if is_relevant else 0
        except Exception as llama_error:
            print(f"LLaMA processing error: {str(llama_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            ai_response = "I apologize, but I encountered an error processing your message. Please try again."
            is_relevant_int = 0
        
        # Store AI response
        ai_message = ChatMessage.objects.create(
            session=session,
            sender='AI',
            message=ai_response,
            is_context_relevant=bool(is_relevant_int)  # Convert back to bool for database
        )
        
        return JsonResponse({
            'response': ai_response,
            'is_relevant': is_relevant_int,  # Send as int
            'timestamp': ai_message.timestamp.isoformat()
        })
        
    except Exception as e:
        print(f"Detailed error in send_message: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

from .llama_integration import process_with_llama

@login_required
def send_message(request, session_id):
    """Handle sending and receiving chat messages."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        session = get_object_or_404(PDFChatSession, id=session_id, user=request.user)
        print(f"PDF document path: {session.pdf_document.file.path}")
        print(f"PDF document exists: {os.path.exists(session.pdf_document.file.path)}")
        
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Store user message
        ChatMessage.objects.create(
            session=session,
            sender='USER',
            message=user_message
        )
        
        try:
            # Process message with LLaMa
            ai_response, is_relevant = process_with_llama(user_message, session)
            # Convert bool to int for JSON serialization
            is_relevant_int = 1 if is_relevant else 0
        except Exception as llama_error:
            print(f"LLaMA processing error: {str(llama_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            ai_response = "I apologize, but I encountered an error processing your message. Please try again."
            is_relevant_int = 0
        
        # Store AI response
        ai_message = ChatMessage.objects.create(
            session=session,
            sender='AI',
            message=ai_response,
            is_context_relevant=bool(is_relevant_int)
        )
        
        # Ensure all values are JSON serializable
        response_data = {
            'response': str(ai_response),  # Convert to string to ensure serializable
            'is_relevant': int(is_relevant_int),  # Use integer instead of boolean
            'timestamp': ai_message.timestamp.isoformat()  # Convert datetime to ISO format string
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Detailed error in send_message: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def end_chat_session(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(PDFChatSession, id=session_id, user=request.user)
        session.is_active = False
        session.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)