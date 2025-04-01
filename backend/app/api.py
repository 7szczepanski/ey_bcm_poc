import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, Response, Depends, HTTPException, status, UploadFile, File, Cookie, Body
from fastapi.security import OAuth2PasswordBearer # Not used directly, but common
from fastapi.responses import JSONResponse

from app.models.auth import LoginRequest, StandardSelectionRequest
from app.models.chat import ChatRequest, ChatResponse
from app.models.memo import MemoResponse
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
from app.chatbot import get_chatbot_response
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

@router.post("/chatbot", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_info: Dict[str, Any] = Depends(get_current_session)
):
    """Chat endpoint that uses both standard and agreement indexes."""
    if not session_info["data"].get("selected_standard"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No standard selected")
    if not session_info["data"].get("agreement_uploaded"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No agreement uploaded")
    
    standard = session_info["data"]["selected_standard"]
    standard_index = load_standard_index(standard)
    if not standard_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load standard index: {standard}")
    
    agreement_index = load_agreement_index(session_info["session_id"])
    if not agreement_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load agreement index")
    
    response, structured_output = get_chatbot_response(
        request.message,
        standard_index,
        agreement_index,
        session_info["data"].get("chat_history", [])
    )
    
    # Update session with chat history and structured output
    session_info["data"]["chat_history"] = session_info["data"].get("chat_history", []) + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": response}
    ]
    if structured_output:
        session_info["data"]["structured_output"] = structured_output
    save_session_data(session_info["session_id"], session_info["data"])
    
    return ChatResponse(
        response=response,
        structured_output=structured_output
    )

@router.post("/generate-memo", response_model=MemoResponse)
async def generate_memo_endpoint(session_info: Dict[str, Any] = Depends(get_current_session)):
    """Generate a memo using the selected standard and uploaded agreement."""
    if not session_info["data"].get("selected_standard"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No standard selected")
    if not session_info["data"].get("agreement_uploaded"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No agreement uploaded")
    
    standard = session_info["data"]["selected_standard"]
    standard_index = load_standard_index(standard)
    if not standard_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load standard index: {standard}")
    
    agreement_index = load_agreement_index(session_info["session_id"])
    if not agreement_index:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load agreement index")
    
    try:
        memo, evidence = generate_memo(
            standard_index,
            agreement_index,
            session_info["data"].get("structured_output", {})
        )
        return MemoResponse(memo=memo, evidence=evidence)
    except Exception as e:
        print(f"Error generating memo: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate memo. Check server logs.")

# TODO: Add endpoint to serve the user's agreement PDF securely?
# Needs careful implementation to prevent accessing other users' data.
# @router.get("/agreement-pdf/{session_id}")
# async def get_agreement_pdf(...) 