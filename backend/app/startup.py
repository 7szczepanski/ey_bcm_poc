import os
import sys
import shutil
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Configuration ---
APP_DIR = Path("/app")
DATA_DIR = APP_DIR / "data"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

STANDARDS_TO_INDEX = [
    {"name": "ifrs", "pdf_filename": "ifrs.pdf"},
    {"name": "asc805", "pdf_filename": "blueprint.pdf"},
]

def create_and_save_index(standard_name: str, pdf_filename: str, embeddings_func):
    """Loads a PDF, creates a FAISS index, and saves it locally."""
    print(f"Checking index for standard: {standard_name}")
    
    pdf_path = DATA_DIR / pdf_filename
    index_path = DATA_DIR / standard_name
    
    # If index already exists, test loading it first
    if index_path.exists() and (index_path / "index.faiss").exists() and (index_path / "index.pkl").exists():
        print(f"Index for '{standard_name}' exists at {index_path}. Testing it can be loaded...")
        
        try:
            # Test loading the existing index with the same parameters we'll use later
            test_index = FAISS.load_local(str(index_path), embeddings_func, allow_dangerous_deserialization=True)
            print(f"Successfully loaded existing index for '{standard_name}'. Keeping it.")
            return True
        except Exception as e:
            print(f"Existing index for '{standard_name}' failed to load: {e}")
            print(f"Will recreate the index for '{standard_name}'")
            # We'll attempt to recreate the index since it's not loadable
    
    # Check if PDF file exists
    if not pdf_path.exists():
        print(f"Error: PDF file {pdf_path} not found for standard '{standard_name}'. Skipping.")
        return False
    
    # Clean up any partial/corrupted index directory
    if index_path.exists():
        print(f"Removing existing index directory: {index_path}")
        try:
            shutil.rmtree(index_path)
        except OSError as e:
            print(f"Error removing directory {index_path}: {e}")
            # Continue anyway, we'll try to create the directory again
    
    print(f"Creating index for '{standard_name}' from {pdf_path}...")
    try:
        # Load and process the PDF
        loader = PyPDFLoader(str(pdf_path))
        documents = loader.load()
        if not documents:
            print(f"Warning: No documents loaded from {pdf_path}. Skipping.")
            return False
        
        # Split the documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)
        
        if not docs:
            print(f"Warning: No text chunks generated after splitting {pdf_path}. Skipping.")
            return False
        
        # Create the embeddings and index
        print(f"Embedding {len(docs)} chunks for '{standard_name}' using '{EMBEDDING_MODEL_NAME}'...")
        index = FAISS.from_documents(docs, embeddings_func)
        
        # Create the directory and save the index
        index_path.mkdir(parents=True, exist_ok=True)
        print(f"Saving index to {index_path}...")
        index.save_local(str(index_path))
        
        # Verify the index files were created and can be loaded
        if (index_path / "index.faiss").exists() and (index_path / "index.pkl").exists():
            print(f"Index files for '{standard_name}' created at {index_path}. Verifying they can be loaded...")
            
            try:
                # Verify the index can be loaded with the same parameters we'll use later
                test_index = FAISS.load_local(str(index_path), embeddings_func, allow_dangerous_deserialization=True)
                print(f"Index for '{standard_name}' saved and verified successfully.")
                return True
            except Exception as e:
                print(f"Error verifying index for '{standard_name}': {e}")
                return False
        else:
            print(f"Warning: Index files not found after save operation for '{standard_name}'.")
            return False
    
    except Exception as e:
        print(f"Error creating index for '{standard_name}': {e}")
        # Clean up any partial index directory
        if index_path.exists():
            try:
                shutil.rmtree(index_path)
            except OSError as rm_err:
                print(f"Error cleaning up index directory {index_path}: {rm_err}")
        return False

def run_startup_indexing():
    """Check for required indices and create them if they don't exist."""
    print("=== Running startup indexing check ===")
    
    # Ensure the data directory exists and is writable
    if not DATA_DIR.exists():
        print(f"Data directory {DATA_DIR} does not exist. Creating it.")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Check if data directory is writable
    try:
        test_file = DATA_DIR / "test_write.tmp"
        with open(test_file, 'w') as f:
            f.write("Testing write permissions")
        os.remove(test_file)
        print(f"Confirmed {DATA_DIR} is writable")
    except Exception as e:
        print(f"WARNING: {DATA_DIR} is not writable! Error: {e}")
        print("Index creation may fail. Check volume permissions.")
    
    # Initialize the embeddings function
    print(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
    try:
        embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    except Exception as e:
        print(f"Failed to initialize SentenceTransformerEmbeddings: {e}")
        return False
    
    # Process each standard
    success = True
    for standard_info in STANDARDS_TO_INDEX:
        standard_success = create_and_save_index(
            standard_info["name"], 
            standard_info["pdf_filename"], 
            embeddings
        )
        if not standard_success:
            success = False
            print(f"Failed to create/verify index for {standard_info['name']}")
    
    if success:
        print("All necessary indices checked/created successfully.")
    else:
        print("Warning: One or more indices could not be created or verified.")
    
    print("=== Startup indexing check complete ===")
    return success

if __name__ == "__main__":
    run_startup_indexing() 