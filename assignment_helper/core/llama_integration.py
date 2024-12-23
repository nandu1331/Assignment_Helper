# core/llama_integration.py

from groq import Groq
import pdfplumber
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import traceback
import os

class LLaMAHandler:
    def __init__(self):
        self.client = Groq()
        self.vectorizer = TfidfVectorizer(stop_words='english')  # Added stop words
        self.context_threshold = 0.1  # Lowered threshold significantly
        
    def extract_pdf_context(self, pdf_path):
        """Extract text from PDF to use as context."""
        try:
            if not os.path.exists(pdf_path):
                print(f"PDF file not found at path: {pdf_path}")
                return ""

            print(f"Processing PDF at path: {pdf_path}")
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    # Enhanced text extraction with better formatting
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"  # Add double newline between pages
                
                print(f"Extracted text from PDF:\n{text[:500]}...")  # Print first 500 chars for debugging
                return text.strip()
                
        except Exception as e:
            print(f"Error extracting PDF context: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return ""

    def check_context_relevance(self, query, context):
        """Check if the query is relevant to the PDF context."""
        try:
            if not context or not query:
                print("Empty context or query")
                return False, 0.0

            # Clean and normalize texts
            query = query.lower().strip()
            context = context.lower().strip()

            print(f"Query length: {len(query)}")
            print(f"Context length: {len(context)}")

            # Combine query and context into a list
            texts = [query, context]

            # Create TF-IDF matrix
            tfidf_matrix = self.vectorizer.fit_transform(texts)

            # Calculate cosine similarity
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            print(f"Similarity score: {similarity}")
            return similarity > self.context_threshold, similarity

        except Exception as e:
            print(f"Error checking context relevance: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return False, 0.0
        
    def generate_response(self, query, context, include_context=True):
        """Generate a response using LLaMA model with context awareness."""
        try:
            # Create the prompt with or without context
            if include_context:
                prompt = f"""Based on the following context from a PDF document:

                {context[:1000]}...

                Please answer this question: {query}

                If the question is not related to the context, indicate that it's out of context.
                """
            else:
                prompt = f"Please answer this question: {query}"

            print(f"Sending request to Groq API with prompt length: {len(prompt)}")

            # Generate completion using Groq with the correct model name
            completion = self.client.chat.completions.create(
                model="llama3-8b-8192",  # Changed from llama2-70b-4096 to llama2-70b
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful AI assistant specializing in answering questions about PDF documents."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000,
                top_p=1,
                stream=False
            )

            response = completion.choices[0].message.content.strip()
            print(f"Successfully generated response of length: {len(response)}")
            return response

        except Exception as e:
            print(f"Error generating response: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return "I encountered an error generating the response. Please try again."


def process_with_llama(message, session):
    """Process a message with LLaMA integration."""
    try:
        handler = LLaMAHandler()
        
        # Extract context from the PDF
        pdf_path = session.pdf_document.file.path
        print(f"Processing PDF at path: {pdf_path}")
        
        context = handler.extract_pdf_context(pdf_path)
        if not context:
            print("Warning: No context extracted from PDF")
            return "I apologize, but I couldn't extract text from the PDF document.", False
            
        # Check context relevance
        is_relevant, similarity_score = handler.check_context_relevance(message, context)
        print(f"Context relevance check - Is relevant: {is_relevant}, Score: {similarity_score}")
        
        # Generate response based on relevance
        if is_relevant:
            try:
                response = handler.generate_response(message, context, include_context=True)
            except Exception as e:
                print(f"Error generating response: {str(e)}")
                response = "I encountered an error generating the response. Please try again."
                is_relevant = False
        else:
            response = "I apologize, but your question appears to be outside the context of the PDF document. Please ask a question related to the document's content."
        
        return response, is_relevant
        
    except Exception as e:
        print(f"Error in process_with_llama: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return "I encountered an error processing your request. Please try again.", False