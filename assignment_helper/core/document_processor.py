# core/document_processor.py
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings

class DocumentProcessor:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
    
    def process_pdf(self, pdf_path):
        """Process PDF and create vector store"""
        try:
            # Load PDF
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            
            # Split into chunks
            chunks = self.text_splitter.split_documents(pages)
            
            # Create vector store
            vectorstore = FAISS.from_documents(chunks, self.embeddings)
            
            return vectorstore
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return None
