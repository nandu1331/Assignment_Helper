from django.shortcuts import render
from .forms import PDFUploadForm

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            # For now, we'll just print the file name for testing
            print(pdf_file.name)
            return render(request, 'core/upload_success.html')
    else:
        form = PDFUploadForm()
    return render(request, 'core/upload_pdf.html', {'form': form})

