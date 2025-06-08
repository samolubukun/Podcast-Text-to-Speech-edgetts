import os
import asyncio
import edge_tts
from pydub import AudioSegment
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import tempfile
import shutil
from typing import List, Dict
import uuid
import io
from contextlib import asynccontextmanager

app = FastAPI(title="Text-to-Speech API", description="Convert script to audio with multiple speakers")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Map speaker codes to specific English text-to-speech voices
VOICE_MAP = {
    "S1": "en-US-AriaNeural",   # Speaker 1 - US English voice
    "S2": "en-GB-RyanNeural"    # Speaker 2 - UK English voice
}

class ScriptRequest(BaseModel):
    script: str

def parse_script(text: str) -> List[Dict[str, str]]:
    """Parse script into dialogue format"""
    lines = text.strip().splitlines()
    dialogue = []
    for line in lines:
        line = line.strip()
        if ":" in line and line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                speaker, content = parts
                speaker = speaker.strip().upper()
                content = content.strip()
                
                if speaker in ["S1", "S2"] and content:
                    dialogue.append({"speaker": speaker, "text": content})
    return dialogue

async def generate_audio_in_memory(dialogue: List[Dict[str, str]]) -> bytes:
    """
    Generate audio entirely in memory without using temporary files
    Better for deployment environments like Render
    """
    audio_segments = []
    
    for line in dialogue:
        # Get the voice for the current speaker
        voice = VOICE_MAP.get(line["speaker"], "en-US-GuyNeural")
        
        # Generate audio in memory
        communicate = edge_tts.Communicate(text=line["text"], voice=voice)
        
        # Save to memory buffer instead of file
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        # Convert to AudioSegment
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        audio_segments.append(audio_segment)
    
    # Combine all segments with pauses
    combined = AudioSegment.empty()
    for segment in audio_segments:
        combined += segment + AudioSegment.silent(duration=700)
    
    # Export to bytes
    output_buffer = io.BytesIO()
    combined.export(output_buffer, format="mp3")
    return output_buffer.getvalue()

@asynccontextmanager
async def cleanup_temp_dir():
    """Context manager for safe temporary directory handling"""
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="tts_")
        yield temp_dir
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                print(f"Warning: Could not clean up {temp_dir}: {e}")

async def generate_audio_with_temp_files(dialogue: List[Dict[str, str]]) -> bytes:
    """
    Alternative method using temporary files with proper cleanup
    Fallback if in-memory generation has issues
    """
    async with cleanup_temp_dir() as temp_dir:
        segments_dir = os.path.join(temp_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        # Generate individual segments
        for i, line in enumerate(dialogue):
            voice = VOICE_MAP.get(line["speaker"], "en-US-GuyNeural")
            output_file = os.path.join(segments_dir, f"line_{i:03d}.mp3")
            
            communicate = edge_tts.Communicate(text=line["text"], voice=voice)
            await communicate.save(output_file)
        
        # Merge segments
        combined = AudioSegment.empty()
        files = [f for f in os.listdir(segments_dir) if f.endswith(".mp3")]
        files.sort(key=lambda x: int(x.split("_")[1].split(".")[0]))
        
        for file in files:
            file_path = os.path.join(segments_dir, file)
            if os.path.exists(file_path):
                seg = AudioSegment.from_file(file_path)
                combined += seg + AudioSegment.silent(duration=700)
        
        # Export to bytes
        output_buffer = io.BytesIO()
        combined.export(output_buffer, format="mp3")
        return output_buffer.getvalue()

@app.get("/")
async def get_index(request: Request):
    """Serve the main HTML template"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate-audio")
async def generate_audio(request: ScriptRequest):
    """
    Generate audio from script - optimized for deployment environments
    Returns audio as streaming response instead of file
    """
    try:
        # Validate input
        if not request.script.strip():
            raise HTTPException(status_code=400, detail="Script cannot be empty")
        
        # Parse the script
        dialogue = parse_script(request.script)
        
        if not dialogue:
            raise HTTPException(
                status_code=400, 
                detail="No valid dialogue found. Please use format 'S1: text' or 'S2: text'"
            )
        
        # Generate audio in memory (preferred for deployment)
        try:
            audio_bytes = await generate_audio_in_memory(dialogue)
        except Exception as e:
            print(f"In-memory generation failed: {e}")
            # Fallback to temp files method
            audio_bytes = await generate_audio_with_temp_files(dialogue)
        
        # Generate filename
        session_id = str(uuid.uuid4())[:8]  # Shortened for filename
        filename = f"podcast_{session_id}.mp3"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "environment": "production"}

@app.get("/system-info")
async def system_info():
    """Get system information for debugging"""
    temp_dir = tempfile.gettempdir()
    disk_usage = shutil.disk_usage(temp_dir)
    
    return {
        "temp_directory": temp_dir,
        "disk_usage": {
            "total_gb": round(disk_usage.total / (1024**3), 2),
            "used_gb": round(disk_usage.used / (1024**3), 2),
            "free_gb": round(disk_usage.free / (1024**3), 2)
        },
        "platform": os.name,
        "environment_vars": {
            "PORT": os.getenv("PORT", "Not set"),
            "RENDER": os.getenv("RENDER", "Not set"),
        }
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    print("Text-to-Speech API started successfully!")
    print(f"Temp directory: {tempfile.gettempdir()}")
    
    # Check if running on Render
    if os.getenv("RENDER"):
        print("Running on Render deployment")
    else:
        print("Running in local/development environment")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)