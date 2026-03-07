from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agent import chat_async
import uvicorn

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

class Message(BaseModel):
    message: str

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/chat")
async def chat_endpoint(msg: Message):
    response = await chat_async(msg.message)
    return {"response": response}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)