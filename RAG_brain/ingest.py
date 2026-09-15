import os
import pdfplumber
import ollama
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("avatar-brain")

# Ensure this matches your local PDF resume filename
PDF_PATH = "/home/mrcaro/Projects/3D Avatar RAG/RAG_brain/my_cv.pdf" 

def extract_and_embed():
    print("Safely clearing old vector index...")
    try:
        # Pass default namespace explicitly to avoid Pinecone 404
        index.delete(delete_all=True, namespace="")
    except Exception as e:
        print(f"Notice during index clear (safe to proceed): {e}")

    print(f"Parsing PDF layout from '{PDF_PATH}'...")
    chunks = []
    
    if not os.path.exists(PDF_PATH):
        print(f"Error: Could not find '{PDF_PATH}' in {os.getcwd()}")
        return

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                # Split text into logical section blocks
                sections = text.split("\n\n")
                for section in sections:
                    cleaned = section.strip()
                    if len(cleaned) > 20:  # Skip tiny fragments
                        chunks.append(cleaned)

    print(f"Generated {len(chunks)} structured context chunks. Embedding to Pinecone...")

    for idx, chunk in enumerate(chunks):
        # 1. Generate embeddings using local Ollama model
        embed_resp = ollama.embeddings(
            model="nomic-embed-text",
            prompt=chunk
        )
        vector = embed_resp["embedding"]
        
        # 2. Upsert chunk with plain-text metadata to Pinecone
        index.upsert(vectors=[{
            "id": f"chunk_{idx}",
            "values": vector,
            "metadata": {"text": chunk}
        }])

    print("Data ingestion completed successfully!")

if __name__ == "__main__":
    extract_and_embed()