import os
import json
import logging
import httpx
from fastapi import FastAPI, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "ai-voice-api"
        })

logger = logging.getLogger("voice_logger")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI()

AI_API_KEY = os.getenv("AI_API_KEY", "missing-key")
EXTERNAL_AI_URL = os.getenv("EXTERNAL_AI_URL", "https://httpbin.org/status/200")
APP_VERSION = os.getenv("APP_VERSION", "v1.0")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.RequestError) | retry_if_exception_type(httpx.HTTPStatusError),
    reraise=True
)
async def call_external_voice_api(text: str):
    logger.info(f"Calling external AI API for text length: {len(text)}")
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(
            EXTERNAL_AI_URL,
            headers={"Authorization": f"Bearer {AI_API_KEY}"}
        )
        response.raise_for_status()
        return {"audio_url": "https://cdn.example.com/output.mp3", "status": "generated"}

@app.get("/health")
def health_check():
    if AI_API_KEY == "missing-key":
        logger.error("Health check failed: AI_API_KEY is missing")
        raise HTTPException(status_code=500, detail="Missing API credentials")
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/generate-voice")
async def generate_voice(payload: dict):
    text = payload.get("text", "Hello world")
    try:
        result = await call_external_voice_api(text)
        logger.info("Voice generated successfully")
        return result
    except Exception as e:
        logger.error(f"CRITICAL: External AI API failed after 3 retries: {str(e)}")
        raise HTTPException(status_code=503, detail="External AI Service Unavailable")
