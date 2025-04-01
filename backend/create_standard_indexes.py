import os
import shutil
from pathlib import Path
import sys
import argparse

# Add app directory to sys path to import embeddings from indexing module if needed
# This might be fragile, consider defining embeddings directly here
APP_DIR = Path(__file__).parent / "app"
# sys.path.insert(0, str(APP_DIR.parent))

# Or define embeddings directly to avoid path issues:
from langchain_community.embeddings import SentenceTransformerEmbeddings
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# Langchain components (ensure these are installed locally)
try:
    from langchain_community.vectorstores import FAISS
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError as e:
    print(f"ImportError: {e}. Please install required libraries: pip install langchain-openai faiss-cpu pypdf sentence-transformers")
    sys.exit(1)

def get_base_dir():
    """Get base directory based on whether script is running in Docker or locally."""
    parser = argparse.ArgumentParser(description='Create standard indexes')
    parser.add_argument('--docker', action='store_true', help='Running in Docker container')
    args, _ = parser.parse_known_args()
    
    if args.docker:
        print("Running in Docker container mode")
        return Path("/app")
    else:
        print("Running in local mode")
        return Path(__file__).parent
    
# --- Configuration ---
BASE_DIR = get_base_dir() # backend directory
DATA_DIR = BASE_DIR / "data"
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR / "app" / "data"
    if not DATA_DIR.exists():
        print(f"Error: Data directory not found at {DATA_DIR}. Please check the path.")
        sys.exit(1)

print(f"Using data directory: {DATA_DIR}")

STANDARDS_TO_INDEX = [
    {"name": "ifrs", "pdf_filename": "ifrs.pdf"},
    {"name": "asc805", "pdf_filename": "blueprint.pdf"}, # Using blueprint.pdf for asc805 index
]

def create_and_save_index(standard_name: str, pdf_filename: str, embeddings_func):
    """Loads a PDF, creates a FAISS index, and saves it locally."""
    pdf_path = DATA_DIR / pdf_filename
    index_path = DATA_DIR / standard_name

    if not pdf_path.exists():
        print(f"Error: PDF file {pdf_path} not found for standard '{standard_name}'. Skipping.")
        return False

    if index_path.exists():
        print(f"Index directory '{index_path}' already exists. Deleting existing index...")
        try:
            shutil.rmtree(index_path)
        except OSError as e:
            print(f"Error deleting existing index {index_path}: {e}. Skipping creation.")
            return False

    print(f"Creating index for '{standard_name}' from {pdf_path}...")
    try:
        loader = PyPDFLoader(str(pdf_path))
        documents = loader.load()
        if not documents:
             print(f"Warning: No documents loaded from {pdf_path}. Skipping index creation.")
             return False

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)

        if not docs:
            print(f"Warning: No text chunks generated after splitting {pdf_path}. Skipping index creation.")
            return False

        print(f"Embedding {len(docs)} chunks for '{standard_name}' using '{EMBEDDING_MODEL_NAME}'...")
        index = FAISS.from_documents(docs, embeddings_func)

        index_path.mkdir(parents=True, exist_ok=True)
        index.save_local(str(index_path))
        print(f"Index for '{standard_name}' saved successfully to {index_path}.")
        return True

    except Exception as e:
        print(f"Error creating index for '{standard_name}': {e}")
        # Clean up potentially partially created index directory
        if index_path.exists():
            try:
                shutil.rmtree(index_path)
            except OSError as rm_err:
                 print(f"Error cleaning up partially created index {index_path}: {rm_err}")
        return False

if __name__ == "__main__":
    print("Starting manual pre-indexing of standard documents...")
    
    # Initialize embeddings function directly in the script
    print(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
    try:
        embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    except Exception as e:
        print(f"Failed to initialize SentenceTransformerEmbeddings: {e}")
        print("Ensure the model is available or network connection is working.")
        sys.exit(1)

    success = True
    for standard_info in STANDARDS_TO_INDEX:
        if not create_and_save_index(standard_info["name"], standard_info["pdf_filename"], embeddings):
            success = False
            print(f"Failed to create index for {standard_info['name']}")
    
    if success:
        print("All indexes created successfully.")
    else:
        print("One or more indexes failed to create. See logs above for details.")
    
    print("Manual pre-indexing finished.") 