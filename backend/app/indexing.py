import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from fastapi import UploadFile
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --- Configuration ---
APP_DIR = Path("/app") # Base directory inside container
DATA_DIR = APP_DIR / "data" # Path should match Docker mount
USER_DATA_DIR = APP_DIR / "user_data" # Path should match Docker volume

# Print current working directory for debugging
print(f"Current working directory: {os.getcwd()}")
print(f"DATA_DIR set to: {DATA_DIR}")
print(f"USER_DATA_DIR set to: {USER_DATA_DIR}")

# Ensure directories exist
if not DATA_DIR.exists():
    print(f"Warning: Data directory not found at {DATA_DIR}")
    alt_paths = [Path("/app/app/data"), Path("data"), Path("app/data")]
    for alt_path in alt_paths:
        if alt_path.exists():
            DATA_DIR = alt_path
            print(f"Using alternative data directory: {DATA_DIR}")
            break

if not USER_DATA_DIR.exists():
    print(f"Creating user data directory: {USER_DATA_DIR}")
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True) # Ensure parent dirs exist

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# --- Global Variables ---
embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
# Initialize with expected keys, will be populated by load_standard_index
standard_indexes: Dict[str, Optional[FAISS]] = {"ifrs": None, "asc805": None} 

# --- Index Loading ---
def load_standard_index(standard: str) -> Optional[FAISS]:
    """Loads a pre-built standard FAISS index. Caches the loaded index."""
    standard_lower = standard.lower()
    if standard_lower not in standard_indexes:
        print(f"Error: Unknown standard '{standard}'. Expected one of: {list(standard_indexes.keys())}")
        return None

    # Check cache first
    if standard_indexes[standard_lower] is not None:
        print(f"Using cached index for '{standard}'.")
        return standard_indexes[standard_lower]

    # Define potential paths in priority order
    potential_paths = [
        DATA_DIR / standard_lower,              # /app/data/ifrs (primary Docker volume path)
        APP_DIR / "app" / "data" / standard_lower,  # /app/app/data/ifrs (mounted code path)
        Path(f"app/data/{standard_lower}"),     # Relative path
        Path(f"/app/data/{standard_lower}")     # Absolute Docker path
    ]
    
    print(f"Searching for {standard_lower} index in these locations: {[str(p) for p in potential_paths]}")
    
    # Create new embeddings instance for loading
    load_embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    
    # Try loading from each path
    for idx, index_path in enumerate(potential_paths):
        faiss_file = index_path / "index.faiss"
        pkl_file = index_path / "index.pkl"
        
        print(f"Checking path {idx+1}/{len(potential_paths)}: {index_path}")
        print(f"  - FAISS file exists: {faiss_file.exists()}")
        print(f"  - PKL file exists: {pkl_file.exists()}")
        
        if not index_path.exists() or not faiss_file.exists() or not pkl_file.exists():
            continue
            
        # Always use allow_dangerous_deserialization=True for consistent behavior
        try:
            print(f"Attempting to load from {index_path} with allow_dangerous_deserialization=True")
            index = FAISS.load_local(str(index_path), load_embeddings, allow_dangerous_deserialization=True)
            print(f"Successfully loaded index for '{standard}' from {index_path}")
            standard_indexes[standard_lower] = index  # Cache the loaded index
            return index
        except Exception as e:
            print(f"Failed to load from {index_path} with error: {str(e)}")
            
            # If this is the last path, try one more approach
            if idx == len(potential_paths) - 1:
                print("Trying last-resort loading approach...")
                try:
                    # Try without the flag for backward compatibility
                    index = FAISS.load_local(str(index_path), load_embeddings)
                    print(f"Successfully loaded index without using allow_dangerous_deserialization")
                    standard_indexes[standard_lower] = index
                    return index
                except Exception as e2:
                    print(f"Last-resort approach failed: {str(e2)}")
    
    print(f"ERROR: Failed to load index for '{standard}' from any location.")
    print("Please ensure the index exists and is accessible.")
    return None

def load_agreement_index(session_id: str) -> Optional[FAISS]:
    """Loads the user-specific agreement index."""
    # Try different potential paths
    potential_paths = [
        USER_DATA_DIR / session_id,  # /app/user_data/{session_id}
        Path(f"/app/app/user_data/{session_id}"),  # Default Docker path
        Path(f"app/user_data/{session_id}"),  # Relative path
        Path(f"/app/user_data/{session_id}")   # Docker path
    ]
    
    index = None
    for user_dir in potential_paths:
        index_file = user_dir / "index.faiss"
        
        if not user_dir.exists() or not index_file.exists():
            print(f"Agreement index not found at {user_dir}, trying next location...")
            continue
            
        try:
            print(f"Attempting to load agreement index for session {session_id} from {user_dir}...")
            
            # Make a new embeddings instance each time to avoid issues
            embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
            
            # First try with dangerous deserialization allowed
            try:
                index = FAISS.load_local(str(user_dir), embeddings, allow_dangerous_deserialization=True)
                print(f"Successfully loaded agreement index for session {session_id} using allow_dangerous_deserialization=True")
                break
            except Exception as e1:
                print(f"First attempt failed with: {e1}")
                
                # Second try without the flag
                try:
                    index = FAISS.load_local(str(user_dir), embeddings)
                    print(f"Successfully loaded agreement index for session {session_id} without deserialization flag")
                    break
                except Exception as e2:
                    print(f"Second attempt failed with: {e2}")
                    
                    # If both attempts fail, continue to the next path
                    print(f"Failed to load agreement index from {user_dir}, trying next location...")
        
        except Exception as e:
            print(f"Error accessing agreement index files at {user_dir}: {e}")
    
    if not index:
        print(f"Failed to load agreement index for session {session_id} from any location.")
    
    return index

def create_agreement_index(pdf_file: UploadFile, session_id: str) -> Tuple[bool, Optional[str]]:
    """Saves uploaded PDF, creates FAISS index, and saves it to user's session dir."""
    user_dir = USER_DATA_DIR / session_id
    user_dir.mkdir(parents=True, exist_ok=True)
    agreement_pdf_path = user_dir / "agreement.pdf"

    # Save the uploaded file
    try:
        with open(agreement_pdf_path, "wb") as buffer:
            shutil.copyfileobj(pdf_file.file, buffer)
        print(f"Agreement PDF saved to {agreement_pdf_path}")
    except IOError as e:
        print(f"Error saving agreement PDF for session {session_id}: {e}")
        return False, "Failed to save agreement file."
    finally:
        pdf_file.file.close() # Ensure file handle is closed

    # Create the index
    try:
        print(f"Creating agreement index for session {session_id}...")
        loader = PyPDFLoader(str(agreement_pdf_path))
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.split_documents(documents)

        if not docs:
             print(f"Warning: No text extracted from agreement PDF for session {session_id}.")
             return True, "Agreement processed, but no text content found to index."

        print(f"Embedding {len(docs)} chunks for agreement in session {session_id}...")
        index = FAISS.from_documents(docs, embeddings)
        index.save_local(str(user_dir))
        print(f"Agreement index for session {session_id} saved successfully.")
        return True, None # Success

    except Exception as e:
        print(f"Error creating agreement index for session {session_id}: {e}")
        if agreement_pdf_path.exists():
            os.remove(agreement_pdf_path)
        if (user_dir / "index.faiss").exists():
             shutil.rmtree(user_dir)
        return False, f"Failed to process and index agreement file: {e}" 