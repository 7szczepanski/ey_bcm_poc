import uuid
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Request, Response, Depends, HTTPException, status, UploadFile, File, Cookie, Body, Query
from fastapi.security import OAuth2PasswordBearer # Not used directly, but common
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# Add the ChatMessage class definition here before it's used
class ChatMessage(BaseModel):
    message: str

class MessageEvaluation(BaseModel):
    message: str

from app.models.auth import LoginRequest, StandardSelectionRequest
from app.models.chat import ChatRequest, ChatResponse
from app.models.memo import MemoResponse
from app.models.structured_output import StructuredMergerData
from app.auth import get_users_from_file, verify_password
from app.services.session_manager import (
    create_session, 
    save_session_data, 
    load_session_data, 
    SESSION_DIR,
    create_session_cookie,
    verify_session_cookie
)
from app.indexing import create_agreement_index, load_standard_index, load_agreement_index, USER_DATA_DIR
from app.chatbot import get_chatbot_response, process_chat_message, llm
from app.memo_generation import generate_memo

router = APIRouter()

# --- Constants ---
COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 3600  # 1 hour in seconds

# --- Helper Functions ---
def get_current_session(session_cookie: Optional[str] = Cookie(None, alias=COOKIE_NAME)) -> Dict[str, Any]:
    """FastAPI dependency to get current session data."""
    print(f"Debug - Received cookie: {session_cookie}")
    session_id = verify_session_cookie(session_cookie)
    print(f"Debug - Verified session_id: {session_id}")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing session cookie")
    
    session_data = load_session_data(session_id)
    print(f"Debug - Loaded session data: {session_data}")
    
    # Initialize session data if it doesn't exist
    if not session_data:
        session_data = {}
        save_session_data(session_id, session_data)
        print(f"Debug - Created new session data for session_id: {session_id}")
    
    return {"session_id": session_id, "data": session_data}

# --- API Endpoints --- 

@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """Login endpoint that sets an HttpOnly cookie."""
    users = get_users_from_file()
    if request.username not in users or not verify_password(request.password, users[request.username]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Generate a unique session_id
    session_id = uuid.uuid4().hex
    
    # Create session with the generated ID
    create_session(session_id)
    
    cookie_value = create_session_cookie(session_id)
    
    response = JSONResponse(content={"message": "Login successful", "session_id": session_id})
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax"
    )
    return response

@router.post("/logout")
async def logout(session_info: Dict[str, Any] = Depends(get_current_session)):
    """Logout endpoint that invalidates the session."""
    session_file = SESSION_DIR / f"{session_info['session_id']}.json"
    if session_file.exists():
        session_file.unlink()
    return {"message": "Logout successful"}

@router.get("/session")
async def get_session(session_info: Dict[str, Any] = Depends(get_current_session)):
    """Get current session data."""
    return session_info["data"]

@router.post("/set-standard")
async def set_standard(
    request: StandardSelectionRequest,
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """Set the accounting standard for the current session."""
    standard_lower = request.standard.lower()
    if standard_lower not in ["ifrs", "asc805"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid standard. Must be 'ifrs' or 'asc805'")
    
    # Try to load standard index
    index = load_standard_index(standard_lower)
    if not index:
        # This is a real error - we need standard indexes for the app to work properly
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load standard index: {standard_lower}")
    
    session_info["data"]["selected_standard"] = standard_lower
    save_session_data(session_info["session_id"], session_info["data"])
    return {"message": f"Standard set to {standard_lower}"}

@router.post("/upload-agreement")
async def upload_agreement(
    file: UploadFile = File(...),
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """Upload and index a merger agreement PDF."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a PDF")
    
    success, error_msg = create_agreement_index(file, session_info["session_id"])
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
    
    session_info["data"]["agreement_uploaded"] = True
    save_session_data(session_info["session_id"], session_info["data"])
    return {"message": f"Agreement '{file.filename}' uploaded and indexed successfully. "}

@router.post("/chatbot")
async def chatbot_endpoint(
    message: ChatMessage,
    session_info: dict = Depends(get_current_session)
):
    """Chat with the assistant about the standard and agreement."""
    session_id = session_info["session_id"]
    session_data = session_info["data"]
    
    # Process the chat message
    result = process_chat_message(session_id, session_data, message.message)
    
    # Check for errors
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Get structured output from result
    structured_output = result.get("structured_output", {})
    
    # Update chat history
    chat_history = session_data.get("chat_history", [])
    chat_history.append({"role": "user", "content": message.message})
    chat_history.append({"role": "assistant", "content": result["response"]})
    session_data["chat_history"] = chat_history
    
    # Update session's structured output with new data if found
    session_structured_output = session_data.get("structured_output", {})
    
    # Merge any new structured data with existing data
    # Note: This simple merge will overwrite existing keys if they appear in the new data
    if structured_output:
        for key, value in structured_output.items():
            session_structured_output[key] = value
        session_data["structured_output"] = session_structured_output
    
    # Determine if we should regenerate the memo based on structured data
    should_regenerate = False
    detected_fields = []
    
    key_fields = [
        "acquisition_date", "acquirer", "acquiree", 
        "consideration", "goodwill", "fair_value",
        "identifiable_assets", "liabilities"
    ]
    
    if structured_output:
        for field in key_fields:
            if field in structured_output:
                should_regenerate = True
                detected_fields.append(field)
    
    # Regenerate memo if significant new information is found
    memo_data = None
    if should_regenerate and session_data.get("agreement_uploaded") and session_data.get("selected_standard"):
        try:
            print(f"Regenerating memo based on new structured data: {detected_fields}")
            
            # Increment memo iteration in session data
            memo_iteration = session_data.get("memo_iteration", 1)
            session_data["memo_iteration"] = memo_iteration + 1
            
            # Load relevant indexes
            standard_index = load_standard_index(session_data["selected_standard"])
            agreement_index = load_agreement_index(session_id)
            
            # Generate memo
            memo, evidence, follow_up_questions = generate_memo(
                standard_index,
                agreement_index,
                session_structured_output
            )
            
            # Create MemoResponse for client
            memo_response = MemoResponse(
                memo=memo,
                evidence=evidence,
                follow_up_questions=follow_up_questions
            )
            
            # Store in session as dictionary for JSON serializability
            session_data["cached_memo_dict"] = memo_response.model_dump()
            memo_data = session_data["cached_memo_dict"]
            
            print(f"Memo regenerated successfully with iteration {memo_iteration + 1}")
        except Exception as e:
            print(f"Error regenerating memo: {e}")
            # Continue even if memo generation fails
    
    # Save updated session data
    save_session_data(session_id, session_data)
    
    # Return the response along with structured data info and regeneration status
    return {
        "response": result["response"],
        "structured_output": structured_output,
        "should_regenerate": should_regenerate,
        "detected_fields": detected_fields,
        "memo": memo_data
    }

@router.post("/generate-memo", response_model=MemoResponse)
async def generate_memo_endpoint(
    force_regenerate: bool = Query(False, description="Whether to force regeneration of the memo"),
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """Generate a memo using the selected standard and uploaded agreement.
    
    If force_regenerate is True, regenerate the memo even if it hasn't been updated.
    Otherwise, return the cached memo if it exists and no updates are needed.
    """
    if not session_info["data"].get("selected_standard"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No standard selected")
    if not session_info["data"].get("agreement_uploaded"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No agreement uploaded")
    
    # Check if we have a cached memo dict and don't need regeneration
    if (not force_regenerate and 
        not session_info["data"].get("memo_needs_update", True) and
        session_info["data"].get("cached_memo_dict")):
        print("Using cached memo as no updates needed")
        # Reconstruct MemoResponse from dict
        return MemoResponse(**session_info["data"]["cached_memo_dict"])
    
    standard = session_info["data"]["selected_standard"]
    standard_index = load_standard_index(standard)
    if not standard_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load standard index: {standard}")
    
    agreement_index = load_agreement_index(session_info["session_id"])
    if not agreement_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load agreement index")
    
    try:
        # Get current memo iteration
        current_iteration = session_info["data"].get("memo_iteration", 1)
        
        # Add memo_iteration to structured output for tracking in the memo
        structured_output = session_info["data"].get("structured_output", {})
        structured_output["memo_iteration"] = current_iteration
        
        # Generate the memo with the latest information
        memo, evidence, follow_up_questions = generate_memo(
            standard_index,
            agreement_index,
            structured_output
        )
        
        # Create the response
        memo_response = MemoResponse(
            memo=memo, 
            evidence=evidence,
            follow_up_questions=follow_up_questions
        )
        
        # Update session data - store as dict to ensure it's JSON serializable
        memo_response_dict = memo_response.model_dump()
        session_info["data"]["memo_iteration"] = current_iteration + 1
        session_info["data"]["cached_memo_dict"] = memo_response_dict
        session_info["data"]["memo_needs_update"] = False
        session_info["data"]["follow_up_questions"] = follow_up_questions
        save_session_data(session_info["session_id"], session_info["data"])
        
        return memo_response
    except Exception as e:
        print(f"Error generating memo: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate memo. Check server logs.")

@router.post("/seed-questions")
async def seed_questions(session_info: Dict[str, Any] = Depends(get_current_session)):
    """Seed the chat with follow-up questions from memo generation.
    
    This endpoint adds the follow-up questions from memo generation
    to the chat history as assistant messages. This creates a conversational
    flow where the system proactively asks for missing information.
    """
    follow_up_questions = session_info["data"].get("follow_up_questions", [])
    
    if not follow_up_questions:
        return {"message": "No follow-up questions to seed"}
    
    # Create a prompt for the questions
    if len(follow_up_questions) == 1:
        prompt = f"To improve the memo, I need additional information: {follow_up_questions[0]}"
    else:
        questions_text = "\n".join([f"- {q}" for q in follow_up_questions])
        prompt = f"To improve the memo, I need information about the following:\n{questions_text}"
    
    # Add the prompt to chat history
    chat_history = session_info["data"].get("chat_history", [])
    chat_history.append({"role": "assistant", "content": prompt})
    session_info["data"]["chat_history"] = chat_history
    
    # Clear the follow-up questions since we've added them to the chat
    session_info["data"]["follow_up_questions"] = []
    save_session_data(session_info["session_id"], session_info["data"])
    
    return {"message": "Seeded chat with follow-up questions", "prompt": prompt}

@router.post("/accept-memo")
async def accept_memo(session_info: Dict[str, Any] = Depends(get_current_session)):
    """Mark the current memo as accepted."""
    if not session_info["data"].get("cached_memo_dict"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No memo to accept. Generate a memo first."
        )
    
    # Mark the memo as accepted
    memo_dict = session_info["data"]["cached_memo_dict"]
    memo_dict["memo"]["is_accepted"] = True
    session_info["data"]["cached_memo_dict"] = memo_dict
    save_session_data(session_info["session_id"], session_info["data"])
    
    return {"message": "Memo accepted successfully"}

@router.post("/evaluate-message")
async def evaluate_message(
    message_data: MessageEvaluation,
    session_info: dict = Depends(get_current_session)
):
    """
    Evaluate if a message contains information that should trigger memo regeneration.
    Returns structured data extracted from the message and whether regeneration is needed.
    """
    session_id = session_info["session_id"]
    session_data = session_info["data"]
    
    # Check if standard is selected and agreement uploaded
    if not session_data.get("selected_standard"):
        raise HTTPException(status_code=400, detail="No standard selected")
    if not session_data.get("agreement_uploaded"):
        raise HTTPException(status_code=400, detail="No agreement uploaded")
    
    standard = session_data["selected_standard"]
    standard_index = load_standard_index(standard)
    if not standard_index:
        raise HTTPException(status_code=500, detail=f"Failed to load standard index: {standard}")
    
    agreement_index = load_agreement_index(session_id)
    if not agreement_index:
        raise HTTPException(status_code=500, detail="Failed to load agreement index")
    
    # Process the message for structured data extraction without updating session
    try:
        # Create structured output LLM
        structured_llm = llm.with_structured_output(StructuredMergerData)
        
        # Create extraction prompt
        extraction_prompt = f"""
        Based on this message:
        
        "{message_data.message}"
        
        Extract any key information relevant for a business combination memo.
        Only include fields where you have medium or high confidence in the information.
        If no relevant information exists for a field, omit it entirely.
        Focus on factual information with specific details about the business combination.
        """
        
        # Get structured output directly
        structured_data = structured_llm.invoke(extraction_prompt)
        
        # Convert to dict for compatibility with existing code
        structured_output = structured_data.model_dump(exclude_none=True)
        
        # Determine if the structured data should trigger regeneration
        # Check if any key fields are present in the structured data
        key_fields = [
            "acquisition_date", "acquirer", "acquiree", 
            "consideration", "goodwill", "fair_value",
            "identifiable_assets", "liabilities"
        ]
        
        should_regenerate = False
        detected_fields = []
        
        if structured_output:
            # Check if any key fields exist and have non-empty values
            for field in key_fields:
                if field in structured_output:
                    should_regenerate = True
                    detected_fields.append(field)
        
        return {
            "structured_output": structured_output,
            "should_regenerate": should_regenerate,
            "fields_detected": detected_fields
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error evaluating message: {str(e)}")

@router.get("/agreement-pdf/{session_id}")
async def get_agreement_pdf(
    session_id: str,
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """
    Serves the user's agreement PDF securely.
    Only allows access to the authenticated user's own agreement.
    """
    # Security check: Users can only access their own agreement
    if session_info["session_id"] != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied: You can only access your own agreement"
        )
    
    # Check if user has uploaded an agreement
    if not session_info["data"].get("agreement_uploaded"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No agreement uploaded for this session"
        )
    
    agreement_path = USER_DATA_DIR / session_id / "agreement.pdf"
    
    if not agreement_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agreement file not found"
        )
    
    return FileResponse(
        path=agreement_path, 
        filename="agreement.pdf", 
        media_type="application/pdf"
    )

@router.get("/standard-pdf/{standard}")
async def get_standard_pdf(
    standard: str,
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """
    Serves a standard PDF securely.
    Only allows access if the user has selected that standard.
    """
    # Validate standard name
    standard = standard.lower()
    if standard not in ["ifrs", "asc805"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid standard. Must be 'ifrs' or 'asc805'"
        )
    
    # Optional: Check if user has this standard selected (for stricter security)
    if session_info["data"].get("selected_standard") != standard:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You must select {standard} standard first"
        )
    
    # Determine filename based on standard
    filename = "ifrs.pdf" if standard == "ifrs" else "blueprint.pdf"
    standard_path = Path("/app/data") / filename
    
    # Fallback paths if running outside Docker or in development
    if not standard_path.exists():
        standard_path = Path("/app/app/data") / filename
    if not standard_path.exists():
        standard_path = Path("app/data") / filename
    
    if not standard_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Standard file not found: {filename}"
        )
    
    return FileResponse(
        path=standard_path, 
        filename=filename, 
        media_type="application/pdf"
    )

# TODO: Add endpoint to serve the user's agreement PDF securely?
# Needs careful implementation to prevent accessing other users' data.
# @router.get("/agreement-pdf/{session_id}")
# async def get_agreement_pdf(...) 