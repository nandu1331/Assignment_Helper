from django.shortcuts import render, redirect, get_object_or_404
from .forms import PDFUploadForm
import google.generativeai as genai
import os
from fpdf import FPDF
import PyPDF2
import re
from .models import APIResponse, Document
import google

# Configure the Gemini API
genai.configure(api_key=os.environ['API_KEY'])

# Question Bank PDF class

class QuestionBankPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_fonts()

    def add_fonts(self):
        # Add Open Sans font (normal, bold, italic)
        font_path = os.path.join(settings.BASE_DIR, 'core/fonts')  # Path to your fonts folder
        self.add_font('OpenSans', '', os.path.join(font_path, 'OpenSans-Regular.ttf'), uni=True)
        self.add_font('OpenSans', 'B', os.path.join(font_path, 'OpenSans-Bold.ttf'), uni=True)
        self.add_font('OpenSans', 'I', os.path.join(font_path, 'OpenSans-Italic.ttf'), uni=True)

    def header(self):
        # Header with institutional details and logo
        logo_path = os.path.join(settings.BASE_DIR, 'logo.png') 
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)  # Logo size and position
        self.set_font("OpenSans", 'B', 12)  # Header font style
        self.cell(0, 10, 'RNS INSTITUTE OF TECHNOLOGY', 0, 1, 'C')
        self.cell(0, 10, 'Autonomous Institution Affiliated to VTU', 0, 1, 'C')
        self.cell(0, 10, 'Assignment 2: CLOUD COMPUTING', 0, 1, 'C')
        self.ln(5)  # Space after header

    def footer(self):
        self.set_y(-15)
        self.set_font("OpenSans", '', 10)  # Footer font style
        self.set_text_color(100, 100, 100)  # Grey color for footer

        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, num, title):
        self.set_font('OpenSans', 'B', 14)  # Bold for question titles
        self.set_text_color(20, 20, 20)  # Dark color for questions
        self.cell(0, 10, f'Question {num}:', 0, 1, 'L')
        self.set_font('OpenSans', 'B', 12)  # Regular for question text
        self.multi_cell(0, 10, title)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('OpenSans', '', 12)  # Regular font for body text
        self.multi_cell(0, 10, body)
        self.ln()

    def add_question(self, num, question, answer=None):
        self.chapter_title(num, question + '?')
        if answer:
            self.set_font('OpenSans', '', 12)  # Regular for answers
            self.set_text_color(30, 30, 30)  # Dark grey for answers
            self.multi_cell(0, 10, f'Answer: {answer}')
            self.ln(5)

def index(request):
    return render(request, 'core/index.html')

def upload_pdf(request):
    uploaded_files = Document.objects.all()
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            pdf_name = pdf_file.name
            existing_document = Document.objects.filter(name=pdf_name).first()
            if existing_document:
                document = existing_document
            else:
                document = Document(name=pdf_file.name, file=pdf_file)
                document.save()

            extracted_text = extract_text_from_pdf(pdf_file)
            questions = extract_questions(extracted_text)

            # Store questions in the session
            request.session['questions'] = questions
            request.session['document_id'] = document.id

            # Render the success page with questions
            return render(request, 'core/upload_success.html', {
                'questions': questions,
                'extracted_text': extracted_text,
            })
    else:
        form = PDFUploadForm()

    return render(request, 'core/upload_pdf.html', {'form': form, 'uploaded_files': uploaded_files, })

def delete_file(request, file_id):
    document = get_object_or_404(Document, id=file_id)
    file_path = document.file.path
    if os.path.isfile(file_path):
        os.remove(file_path)

    answers_dir = os.path.join(settings.MEDIA_ROOT, 'answers')  # Path to the answers directory
    answers_pdf_path = os.path.join(answers_dir, f"answers_{document.id}.pdf")  # Assuming the answers PDF is named in this format

    # Check if the answers PDF exists and delete it
    if os.path.isfile(answers_pdf_path):
        os.remove(answers_pdf_path)


    document.delete()
    return redirect('upload_pdf')  # Redirect back to the upload page

from django.http import FileResponse

def download_file(request, file_id):
    document = get_object_or_404(Document, id=file_id)
    
    # Check if the answers file exists
    if document.answers:
        file_path = document.answers.path
        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="answers_{document.id}.pdf"'
        return response
    else:
        # Check if there are questions and answers in the database
        questions_and_answers = APIResponse.objects.filter(document=document)
        
        if not questions_and_answers.exists():
            return redirect('upload_pdf')  # Or handle the error appropriately
        
        # Extract questions and answers
        questions = [q.question for q in questions_and_answers]
        answers = [a.answer for a in questions_and_answers]
        
        return generate_question_bank_pdf(questions, answers, document.id)

def view_answers(request, file_id):
    document = get_object_or_404(Document, id=file_id)
    answers = document.api_responses.all()  # Assuming you have an answers model

    # Prepare the questions and answers for rendering
    questions = [response.question for response in answers]  # Extract questions from answers
    formatted_answers = [response.answer for response in answers]  # Extract answers

    pdf_file_path = os.path.join(settings.MEDIA_ROOT, f"answers/answers_{document.id}.pdf")
    if not os.path.exists(pdf_file_path):
        # Generate the PDF if it does not exist
        pdf_file_path = generate_question_bank_pdf(questions, formatted_answers, document.id)
    
    return render(request, 'core/generate_answers.html', {
        'document': document,  # Pass the document object to the template
        'questions': questions,
        'answers': formatted_answers,
        'pdf_file_path': pdf_file_path,  # No PDF generated for viewing answers
        'viewing_answers': True,  # Flag to indicate that this is a view answers page
    })

def generate_answers(request):
    if request.method == 'POST':
        # Retrieve the document ID from the session
        document_id = request.session.get('document_id')
        document = get_object_or_404(Document, id=document_id)

        # Check if there are edited questions
        edited_questions = request.POST.getlist('edited_questions')  # Get the list of edited questions from the form
        if edited_questions:
            # Generate answers only for the edited questions
            answers = []
            for question in edited_questions:
                # Fetch answers for each edited question
                cached_answer = get_cached_answers([question])
                if cached_answer:
                    answers.append(cached_answer)  # Assuming cached_answer returns a list
                else:
                    answer = get_answers_from_gemini([question])
                    answers.append(answer)
                    # Store the new answer in the database
                    store_api_responses([question], [answer], document_id)

            # Clean and format the answers
            formatted_data = clean_and_format_data(answers)
            # Pass the document_id to the PDF generation function
            pdf_file_path = generate_question_bank_pdf(edited_questions, formatted_data, document_id)

            return render(request, 'core/generate_answers.html', {
                'questions': edited_questions,
                'answers': formatted_data,
                'pdf_file_path': pdf_file_path,
                'viewing_answers': True,
                'document': document,
            })
        else:
            # Handle the case for generating answers for new questions
            questions = request.POST.getlist('questions')  # Get the list of questions from the form

            # Split the questions string back into a list if needed
            questions = questions[0].split(',') if questions else []

            cached_answers = get_cached_answers(questions)

            if cached_answers:
                answers = cached_answers
            else:
                answers = get_answers_from_gemini(questions)
                answers = clean_and_format_data(answers)
                store_api_responses(questions, answers, document_id)  # Store responses in the database

            formatted_data = clean_and_format_data(answers)
            # Pass the document_id to the PDF generation function
            pdf_file_path = generate_question_bank_pdf(questions, formatted_data, document_id)

            return render(request, 'core/generate_answers.html', {
                'questions': questions,
                'answers': formatted_data,
                'pdf_file_path': pdf_file_path,
                'viewing_answers': True,
                'document': document,
            })

    return redirect('upload_pdf')  # Redirect to upload_pdf if not POST

from django.conf import settings
# Function to generate question bank-style PDF
def generate_question_bank_pdf(questions, answers, document_id):
    # Define the media directory and answers directory
    media_dir = settings.MEDIA_ROOT
    answers_dir = os.path.join(media_dir, "answers")

    # Create the answers directory if it does not exist
    if not os.path.exists(answers_dir):
        os.makedirs(answers_dir)

    # Create the PDF instance
    pdf = QuestionBankPDF()
    pdf.add_page()

    # Adding title and description to match the institutional style
    pdf.set_font("OpenSans", 'B', 20)
    pdf.set_text_color(0, 51, 102)  # Dark blue for title
    pdf.cell(0, 20, 'University Question Bank', 0, 1, 'C')
    pdf.ln(10)

    # Subtitle or description
    pdf.set_font("OpenSans", 'I', 14)
    pdf.set_text_color(100, 100, 100)  # Light grey
    pdf.cell(0, 10, 'A compilation of important questions for review', 0, 1, 'C')
    pdf.ln(20)

    # Adding questions and answers in a structured format
    pdf.set_fill_color(220, 220, 220)  # Light grey for question background
    pdf.set_font("OpenSans", '', 12)

    for i, (question, answer) in enumerate(zip(questions, answers), start=1):
        pdf.add_question(i, question, answer)

    # Save the PDF in the answers directory
    pdf_output = os.path.join(answers_dir, f"answers_{document_id}.pdf")
    pdf.output(pdf_output)

    # Update the document's answers field
    document = Document.objects.get(id=document_id)
    document.answers = f"answers/answers_{document_id}.pdf"
    document.save()

    # Return the file response for the generated PDF
    return FileResponse(open(pdf_output, 'rb'), content_type='application/pdf')


# Other helper functions (extract_text_from_pdf, extract_questions, etc.) remain unchanged

def store_api_responses(questions, answers, document_id):
    for question, answer in zip(questions, answers):
        APIResponse.objects.create(question=question, answer=answer, document_id=document_id)

def get_cached_answers(questions):
    answers = []
    for question in questions:
        try:
            cache_entry = APIResponse.objects.get(question=question)
            answers.append(cache_entry.answer)
        except APIResponse.DoesNotExist:
            return None
    return answers

import pdfplumber
import re
import spacy
from spacy.matcher import Matcher
from spacy.tokens import Span

# Load the English NLP model
nlp = spacy.load("en_core_web_sm")

def extract_text_from_pdf(pdf_file):
    extracted_text = ""
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"  # Add a newline for separation

    return extracted_text

def clean_extracted_text(text):
    # Remove excessive whitespace and newlines
    text = re.sub(r'\n+', ' ', text)  # Replace multiple newlines with a single space
    text = re.sub(r'\s+', ' ', text)   # Normalize whitespace
    text = text.strip()  # Remove leading/trailing whitespace
    return text

import re
from nltk.corpus import words

# Load English words list
english_words = set(words.words())

def is_valid_english_sentence(sentence):
    # Tokenize the sentence into words
    words_in_sentence = sentence.split()
    
    # Count how many valid English words are in the sentence
    valid_words = [word for word in words_in_sentence if word.lower() in english_words]
    
    # Return True if the majority of the words in the sentence are valid English words
    return len(valid_words) >= len(words_in_sentence) * 0.5  # At least 50% must be valid English words

def extract_questions(text):
    # Preprocess the text to reduce noise
    text = re.sub(r'\n+', '\n', text)  # Normalize new lines to single breaks
    text = re.sub(r'\s+', ' ', text)  # Normalize excessive whitespace
    text = re.sub(r'[^\w\s\.\?\!\-]', '', text)  # Remove unnecessary special characters
    text = re.sub(r'\b[L2]\d+\s[Cc][Oo]\d+\b', '', text)

    # Split text into sentences based on common question delimiters (periods, question marks, etc.)
    sentences = re.split(r'(?<!\w\.\w.)(?<=\.|\?|\!)\s+', text)

    # Define enhanced question patterns for flexibility
    question_patterns = [
        re.compile(r'^\d+\.\s'),  # Matches "1. ", "2. " (Numbered questions)
        re.compile(r'^[A-Za-z]\.\s+'),  # Matches "A. ", "B. " (Lettered questions)
        re.compile(r'^[A-Za-z]\)\s+'),  # Matches "A) ", "B) " (Lettered with parenthesis)
        re.compile(r'\?\s*$'),  # Sentences ending in a question mark
        re.compile(r'^(What|How|Why|When|Where|Who|Is|Are|Do|Does|Did|Can|Could|May|Might|Shall|Should|Explain|Describe|Identify|Compare|Discuss)\s+', re.IGNORECASE)  # Common question starters
    ]

    questions = []

    # Check each sentence for matching question patterns and valid English content
    for sentence in sentences:
        sentence = sentence.strip()  # Ensure clean sentences
        
        # Skip sentences that don't have enough valid English words
        if not is_valid_english_sentence(sentence):
            continue
        
        # Check if the sentence matches any of the patterns
        if any(pattern.match(sentence) for pattern in question_patterns):
            questions.append(sentence)
        else:
            # Fallback for multiline questions: Look for blocks that might be part of longer questions
            if re.match(r'^\d+[\.\)]\s+|^[A-Z][a-z]*[\.\)]\s+', sentence):
                questions.append(sentence)

            # Also, consider multi-line question markers
            elif len(sentence.split()) > 5 and sentence[0].isupper():
                # Sentences longer than 5 words that start with a capital letter can be considered questions
                questions.append(sentence)
    
    return questions

def get_answers_from_gemini(questions):
    try:
        answers = []
        model = genai.GenerativeModel("gemini-1.5-flash")
        for question in questions:
            response = model.generate_content(question)
            answers.append(response.text.strip())
        return answers
    except google.api_core.exceptions.InvalidArgument as api_error:
        # Handle invalid API key error
        print(f"API Key Invalid: {api_error}")
        return 'API Key Invalid. Please check your credentials.'
    except Exception as e:
        # Catch other general exceptions
        print(f"An error occurred: {e}")
        return ''


import re

def clean_and_format_data(raw_data):
    cleaned_data = []
    
    for answer in raw_data:
        # Strip leading/trailing whitespace
        answer = answer.strip()
        
        # Remove HTML tags (if any)
        answer = re.sub(r'<.*?>', '', answer)
        
        # Replace multiple spaces with a single space
        answer = re.sub(r'\s+', ' ', answer)
        
        # Remove any unwanted characters (optional: modify regex as needed)
        answer = re.sub(r'[^a-zA-Z0-9,.!?\'" ]', '', answer)
        
        # Ensure the answer is not empty after cleaning
        if answer:
            cleaned_data.append(answer)
    
    return cleaned_data

