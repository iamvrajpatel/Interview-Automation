from PyPDF2 import PdfReader
from docx import Document
import time 
import hashlib

# Define boards, grades, and subjects
boards = [
    'Central Board of Secondary Education (CBSE)',
    'Council for the Indian School Certificate Examinations (CISCE)', 
    # ...existing boards...
]

grades = ['Primary', 'Secondary', 'Higher Secondary']

countries = [
    'India', 'Afghanistan', 'Albania', 'Algeria', # ...rest of countries...
]

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def parse_file(filepath):
    extension = filepath.rsplit('.', 1)[1].lower()
    if extension == 'txt':
        with open(filepath, 'r') as file:
            return file.read()
    elif extension in ['doc', 'docx']:
        doc = Document(filepath)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    elif extension == 'pdf':
        pdf_reader = PdfReader(filepath)
        return "\n".join([page.extract_text() for page in pdf_reader.pages])
    else:
        return "Unsupported file format."

def generate_hashed_id():
    data = str(time.time()).encode('utf-8')
    return hashlib.sha256(data).hexdigest()
