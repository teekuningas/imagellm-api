from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Message(BaseModel):
    messages: list[str]

@app.post("/generate_response")
async def generate_response(message: Message):
    response = message.messages + ["This is a generated response"]
    return {"messages": response}
