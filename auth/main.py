from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login import LoginManager
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv

from backend.utils.db import (
    create_tables, add_user, get_user_by_username,
    get_all_sessions, get_messages_for_session, add_message_to_session,
    user_owns_session, create_new_session  # ✅ Use correct function name
)

# Load environment variables
load_dotenv()
SECRET = os.getenv("FASTAPI_SECRET_KEY", "supersecretkey")

app = FastAPI()

# CORS setup to allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Update if frontend is deployed elsewhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing config
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Login manager setup
manager = LoginManager(SECRET, token_url="/auth/login", use_cookie=True)
manager.cookie_name = "pm_auth"

# ======================= Pydantic Models =======================

class UserRegister(BaseModel):
    username: EmailStr
    password: str
    name: str

class NewChatSession(BaseModel):
    session_name: str

class ChatMessage(BaseModel):
    message: str

class MessageOut(BaseModel):
    role: str
    content: str
    timestamp: str

# ======================= App Lifecycle =======================

@app.on_event("startup")
def startup_event():
    create_tables()

# ======================= Auth =======================

@manager.user_loader()
def load_user(username: str):
    return get_user_by_username(username)

@app.post("/auth/register", status_code=201)
def register(user: UserRegister):
    if not user.username.lower().endswith("@calgary.ca"):
        raise HTTPException(status_code=400, detail="Only @calgary.ca emails allowed.")
    
    if get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = pwd_context.hash(user.password)
    add_user(user.username, hashed_password, user.name)
    return {"msg": "User created successfully"}

@app.post("/auth/login")
def login(data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(data.username)
    if not user or not pwd_context.verify(data.password, user["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = manager.create_access_token(data={"sub": data.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "name": user["name"]
    }

# ======================= Chat Endpoints =======================

@app.get("/chats")
def list_chats(user=Depends(manager)):
    sessions = get_all_sessions(user["username"])
    return {"sessions": sessions}

@app.post("/chats/new", status_code=201)
def create_chat(chat: NewChatSession, user=Depends(manager)):
    # ✅ Fix: use `create_new_session` not undefined `add_chat_for_user`
    session_id = create_new_session(user["username"], chat.session_name)
    return {"session_id": session_id}

@app.get("/chats/{session_id}/messages", response_model=list[MessageOut])
def get_messages(session_id: int, user=Depends(manager)):
    if not user_owns_session(user["username"], session_id):
        raise HTTPException(status_code=403, detail="Unauthorized access to this session")

    messages = get_messages_for_session(user["username"], session_id)
    return messages

@app.post("/chats/{session_id}/messages", status_code=201)
def add_message(session_id: int, message: ChatMessage, user=Depends(manager)):
    if not user_owns_session(user["username"], session_id):
        raise HTTPException(status_code=403, detail="Unauthorized access to this session")

    add_message_to_session(user["username"], session_id, message.message, role="user")
    return {"msg": "Message saved"}
