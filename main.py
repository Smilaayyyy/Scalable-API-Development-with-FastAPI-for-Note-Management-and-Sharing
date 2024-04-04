from fastapi import FastAPI, HTTPException, Depends, Path, Request, status
from typing import List
from pydantic import BaseModel, ValidationError
from bson import ObjectId
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
import pymongo
import jwt
from fastapi.encoders import jsonable_encoder
from collections import defaultdict
from starlette.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI()

# MongoDB Connection
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["list"]
users_collection = db["data"]
notes_collection = db["notes"]  # Define notes_collection here

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(BaseModel):
    username: str
    password: str

    class Config:
        orm_mode = True

class Note(BaseModel):
    title: str
    content: str
    owner: str

class Token(BaseModel):
    access_token: str
    token_type: str

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, "secret_key", algorithm="HS256")
    return encoded_jwt

def get_current_user(token: str = Depends(lambda x: x)):
    try:
        payload = jwt.decode(token, "secret_key", algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.exception_handler(RequestValidationError)
async def custom_form_validation_error(request: Request, exc: RequestValidationError):
    reformatted_message = defaultdict(list)
    for pydantic_error in exc.errors():
        loc, msg = pydantic_error["loc"], pydantic_error["msg"]
        filtered_loc = loc[1:] if loc[0] in ("body", "query", "path") else loc
        field_string = ".".join(filtered_loc)  # nested fields with dot-notation
        reformatted_message[field_string].append(msg)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder(
            {"detail": "Invalid request", "errors": reformatted_message}
        ),
    )

@app.post("/api/auth/signup", response_model=User)
async def signup(user: User):
    user_dict = user.dict()
    hashed_password = get_password_hash(user_dict["password"])
    user_dict["password"] = hashed_password
    user_dict["id"] = str(ObjectId())

    # Insert user into MongoDB
    user_id = users_collection.insert_one(user_dict).inserted_id
    user_dict["_id"] = user_id

    return User(**user_dict)

@app.post("/api/auth/login", response_model=Token)
async def login(user: User):
    stored_user = users_collection.find_one({"username": user.username})
    if not stored_user or not verify_password(user.password, stored_user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/notes", response_model=List[Note])
async def read_notes(token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    return [note for note in notes_collection.find({"owner": token["sub"]})]

@app.post("/api/notes", response_model=Note)
async def create_note(note: Note, token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    new_note = note.dict()
    new_note["owner"] = token["sub"]

    # Insert note into MongoDB
    note_id = notes_collection.insert_one(new_note).inserted_id
    new_note["_id"] = note_id

    return Note(**new_note)

@app.get("/api/notes/{note_id}", response_model=Note)
async def read_note(
        note_id: str = Path(..., description="The ID of the note to retrieve."),
        token: str = Depends(get_current_user)
):
    notes_collection = db["notes"]
    print(f"Requested note_id: {note_id}")  # Debugging line
    print(f"Owner token: {token['sub']}")  # Debugging line

    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=422, detail="Invalid ObjectId format")

    note = notes_collection.find_one({"_id": ObjectId(note_id), "owner": token["sub"]})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@app.put("/api/notes/{note_id}", response_model=Note)
async def update_note(note_id: str, note: Note, token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    stored_note = notes_collection.find_one({"_id": ObjectId(note_id), "owner": token["sub"]})
    if not stored_note:
        raise HTTPException(status_code=404, detail="Note not found")

    updated_note = note.dict()
    notes_collection.update_one({"_id": ObjectId(note_id)}, {"$set": updated_note})

    return Note(**updated_note)

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str, token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    stored_note = notes_collection.find_one({"_id": ObjectId(note_id), "owner": token["sub"]})
    if not stored_note:
        raise HTTPException(status_code=404, detail="Note not found")

    notes_collection.delete_one({"_id": ObjectId(note_id)})

    return {"message": "Note deleted successfully"}

@app.post("/api/notes/{note_id}/share")
async def share_note(note_id: str, share_with: str, token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    stored_note = notes_collection.find_one({"_id": ObjectId(note_id), "owner": token["sub"]})
    if not stored_note:
        raise HTTPException(status_code=404, detail="Note not found")

    shared_note = stored_note.copy()
    shared_note["owner"] = share_with
    shared_note.pop("_id")

    # Insert shared note into MongoDB
    shared_note_id = notes_collection.insert_one(shared_note).inserted_id

    return {"message": "Note shared successfully"}

@app.get("/api/search", response_model=List[Note])
async def search_notes(q: str, token: str = Depends(get_current_user)):
    notes_collection = db["notes"]
    return [note for note in notes_collection.find({"owner": token["sub"],
                                                    "$or": [{"title": {"$regex": q, "$options": "i"}},
                                                            {"content": {"$regex": q, "$options": "i"}}]})]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
