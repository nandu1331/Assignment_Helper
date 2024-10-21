from django.shortcuts import render
from .forms import PDFUploadForm

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            # Call the separate function to extract text
            extracted_text = extract_text_from_pdf(pdf_file)
            questions = extract_questions(extracted_text)
            return render(request, 'core/upload_success.html', {'questions': questions, 'extracted_text' : extracted_text})

    else:
        form = PDFUploadForm()

    return render(request, 'core/upload_pdf.html', {'form': form})


import PyPDF2

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    extracted_text = ""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        extracted_text += page.extract_text()
    return extracted_text

import re

def extract_questions(text):
    # Split the text into lines
    lines = text.splitlines()
    questions = []

    for line in lines:
        line = line.strip()
        
        # Check if the line contains a question
        # Using regex to match patterns that are likely to represent questions
        # We consider lines that start with a number followed by text
        if re.match(r'^\d+\s+.*$', line):
            question_match = re.search(r'^\d+\s+(.*?)(?=\s*RBT|\s*COs|$)', line)
            if question_match:
                question_text = question_match.group(1).strip()
                if question_text:  # Ensure it's not empty
                    questions.append(question_text)
        
        # More general cases: look for lines ending with a question mark or common question phrases
        if any(phrase in line for phrase in ['how', 'what', 'why', 'describe', 'explain']):
            # Check if it looks like a question
            if line.endswith('?') or line.endswith('.'):
                # Clean the line by removing extraneous parts
                question_text = re.sub(r'^(Q\.?No\.?\s*\d*\s*)?', '', line)  # Remove 'Q.No. ' and number
                question_text = question_text.strip()  # Clean up whitespace
                if question_text:  # Ensure it's not empty
                    questions.append(question_text)

    # Remove duplicates while maintaining order
    questions = list(dict.fromkeys(questions))
    
    return questions
