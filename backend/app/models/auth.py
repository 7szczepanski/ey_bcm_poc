from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class StandardSelectionRequest(BaseModel):
    standard: str 