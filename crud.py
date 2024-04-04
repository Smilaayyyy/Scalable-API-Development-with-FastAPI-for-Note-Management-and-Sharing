from model import NoteInDB
from db import db
from bson import ObjectId

async def create_note(note: NoteInDB):
    note_dict = note.dict()
    note_dict["id"] = str(ObjectId())
    result = await db.notes.insert_one(note_dict)
    return note_dict["id"]

async def get_note_by_id(note_id: str):
    note = await db.notes.find_one({"id": note_id})
    return NoteInDB(**note) if note else None

async def get_notes_by_user(user_id: str):
    notes = []
    async for note in db.notes.find({"created_by": user_id}):
        notes.append(NoteInDB(**note))
    return notes

async def update_note(note_id: str, note: NoteInDB):
    result = await db.notes.update_one({"id": note_id}, {"$set": note.dict()})
    return result.modified_count > 0

async def delete_note(note_id: str):
    result = await db.notes.delete_one({"id": note_id})
    return result.deleted_count > 0
