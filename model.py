from pydantic import BaseModel, Field
from typing import List
from bson import ObjectId

class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    pass

class NoteInDB(NoteBase):
    id: str

class NoteList(BaseModel):
    notes: List[NoteInDB]

class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6)

class UserCreate(UserBase):
    pass

class UserInDB(UserBase):
    id: str
