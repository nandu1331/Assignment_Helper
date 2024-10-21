from django.shortcuts import render
from .forms import PDFUploadForm
import google.generativeai as genai
import os
from fpdf import FPDF
import PyPDF2
import re
from .models import APIResponse

# Configure the Gemini API
genai.configure(api_key=os.environ['API_KEY'])

# Question Bank PDF class

class QuestionBankPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_fonts()

    def add_fonts(self):
        # Add Open Sans font (normal, bold, italic)
        font_path = os.path.join(settings.BASE_DIR, 'core/fonts')  # Update this path
        self.add_font('OpenSans', '', os.path.join(font_path, 'OpenSans-Regular.ttf'), uni=True)
        self.add_font('OpenSans', 'B', os.path.join(font_path, 'OpenSans-Bold.ttf'), uni=True)
        self.add_font('OpenSans', 'I', os.path.join(font_path, 'OpenSans-Italic.ttf'), uni=True)

    def header(self):
        # Logo (optional)
        logo_path = os.path.join(settings.BASE_DIR, 'logo.png') 
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)  # Adjust the path and size as necessary
        self.set_font("OpenSans", 'B', 16)  # Use Open Sans for header
        self.cell(0, 10, 'Question Bank', 0, 1, 'C')
        self.ln(5)  # Space after header

    def footer(self):
        self.set_y(-15)
        self.set_font("OpenSans", '', 10)  # Use Open Sans for footer
        self.set_text_color(100, 100, 100)  # Grey color for footer
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, num, title):
        self.set_font('OpenSans', 'B', 14)  # Bold for question titles
        self.set_text_color(20, 20, 20)  # Dark blue color
        self.cell(0, 10, f'Question {num}:', 0, 1, 'L')
        self.set_font('OpenSans', 'B', 12)  # Italic for question text
        self.multi_cell(0, 10, title)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('OpenSans', '', 12)  # Regular font for body text
        self.multi_cell(0, 10, body)
        self.ln()

    def add_question(self, num, question, answer=None):
        self.chapter_title(num, question)
        if answer:
            self.set_font('OpenSans', '', 12)  # Italic for answers
            self.set_text_color(30, 30, 30)  # Dark green color for answers
            self.multi_cell(0, 10, f'Answer: {answer}')
            self.ln(5)

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            extracted_text = extract_text_from_pdf(pdf_file)
            questions = extract_questions(extracted_text)

            # Check if the questions are cached, if yes, return the cached answers
            cached_answers = get_cached_answers(questions)
            if cached_answers:
                answers = cached_answers
            else:
                answers = get_answers_from_gemini(questions)
                store_api_responses(questions, answers)  # Store responses in the database

            formatted_data = clean_and_format_data(answers)
            pdf_file_path = generate_question_bank_pdf(questions, formatted_data)  # Generate PDF
            
            return render(request, 'core/upload_success.html', {
                'questions': questions,
                'answers': answers,
                'extracted_text': extracted_text,
                'pdf_file': pdf_file_path,
            })
    else:
        form = PDFUploadForm()

    return render(request, 'core/upload_pdf.html', {'form': form})

from django.conf import settings
# Function to generate question bank-style PDF
def generate_question_bank_pdf(questions, answers):
    media_dir = settings.MEDIA_ROOT
    if not os.path.exists(media_dir):
        os.makedirs(media_dir)

    pdf = QuestionBankPDF()
    pdf.add_page()

    # Title Page
    pdf.set_font("OpenSans", '', 20)  # Use Open Sans for title
    pdf.set_text_color(0, 51, 102)  # Dark blue for title
    pdf.cell(0, 20, 'University Question Bank', 0, 1, 'C')
    pdf.ln(10)

    # Subtitle or description
    pdf.set_font("OpenSans", 'I', 14)  # Italic Open Sans
    pdf.set_text_color(100, 100, 100)  # Light grey
    pdf.cell(0, 10, 'A compilation of important questions for review', 0, 1, 'C')
    pdf.ln(20)

    # Adding questions
    pdf.set_fill_color(220, 220, 220)  # Light grey for background
    pdf.set_font("OpenSans", '', 12)  # Regular font for questions

    for i, (question, answer) in enumerate(zip(questions, answers), start=1):
        pdf.add_question(i, question, answer)

    # Save the PDF
    pdf_output = os.path.join(media_dir, "question_bank.pdf")
    pdf.output(pdf_output)

    return os.path.join(settings.MEDIA_URL, "question_bank.pdf")


# Other helper functions (extract_text_from_pdf, extract_questions, etc.) remain unchanged

def store_api_responses(questions, answers):
    for question, answer in zip(questions, answers):
        APIResponse.objects.create(question=question, answer=answer)

def get_cached_answers(questions):
    answers = []
    for question in questions:
        try:
            cache_entry = APIResponse.objects.get(question=question)
            answers.append(cache_entry.answer)
        except APIResponse.DoesNotExist:
            return None
    return answers


def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    extracted_text = ""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        extracted_text += page.extract_text()
    return extracted_text

def extract_questions(text):
    lines = text.splitlines()
    questions = []

    for line in lines:
        line = line.strip()
        
        # Using regex to match patterns that are likely to represent questions
        if re.match(r'^\d+\s+.*$', line):
            question_match = re.search(r'^\d+\s+(.*?)(?=\s*RBT|\s*COs|$)', line)
            if question_match:
                question_text = question_match.group(1).strip()
                if question_text:
                    questions.append(question_text)
        
        if any(phrase in line for phrase in ['how', 'what', 'why', 'describe', 'explain']):
            if line.endswith('?') or line.endswith('.'):
                question_text = re.sub(r'^(Q\.?No\.?\s*\d*\s*)?', '', line)
                question_text = question_text.strip()
                if question_text:
                    questions.append(question_text)

    # Remove duplicates while maintaining order
    questions = list(dict.fromkeys(questions))
    
    return questions

def get_answers_from_gemini(questions):
    answers = []
    model = genai.GenerativeModel("gemini-1.5-flash")
    for question in questions:
        response = model.generate_content(question)
        answers.append(response.text.strip())
    return answers

def clean_and_format_data(raw_data):
    cleaned_data = [answer.strip() for answer in raw_data if answer.strip()]  # Clean whitespace
    return cleaned_data
