from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.api import router as api_router
from app.indexing import load_standard_index
from app.startup import run_startup_indexing

app = FastAPI(title="Business Combination Memo Generator API")

# --- CORS Configuration --- 
# Adjust origins based on your frontend setup
origins = [
    "http://localhost:3000", # Default Next.js dev port
    "http://127.0.0.1:3000",
    # Add other origins if needed (e.g., deployed frontend URL)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"] # Allows all headers
)

# --- Include API Routes --- 
app.include_router(api_router, prefix="/api")

# --- Startup Event --- 
@app.on_event("startup")
async def startup_event():
    print("Application startup...")
    
    try:
        # Run the startup indexing process to check/create indices as needed
        print("Checking and creating standard indices if needed...")
        indexing_success = run_startup_indexing()
        
        if indexing_success:
            print("Standard indices are ready for use.")
        else:
            print("Warning: Some standard indices may not be available.")
    except Exception as e:
        print(f"Error during startup indexing: {e}")
        print("Warning: Application may not function correctly without indices.")
    
    print("Startup complete.")

# --- Root Endpoint (Optional) --- 
@app.get("/")
async def root():
    return {"message": "Welcome to the Business Combination Memo Generator API"}

# --- Run with Uvicorn (handled by Dockerfile CMD) --- 
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000) 