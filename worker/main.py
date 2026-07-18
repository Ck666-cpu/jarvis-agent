import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tasks import process_telegram_message

app = FastAPI(title="Jarvis Python Worker")

class TelegramPayload(BaseModel):
    raw_text: str
    image_paths: list = []

@app.post("/api/v1/process_listing")
def trigger_processing(payload: TelegramPayload):
    # 接收到外部请求，直接移交给 tasks 主管
    result = process_telegram_message(payload.raw_text, payload.image_paths)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)