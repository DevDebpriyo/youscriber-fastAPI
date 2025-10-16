from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import os
from pathlib import Path
import yt_dlp

# Initialize FastAPI app
app = FastAPI(
    title="YouScriber Transcription API",
    description="FastAPI service for transcribing YouTube audio using Faster-Whisper",
    version="1.1.0"
)

# Allow CORS from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Later restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Faster-Whisper
model_size = "small"  # You can change to base.en, medium.en, etc.
model = WhisperModel(model_size, device="cpu", compute_type="int8")

# Temp folder for audio files (absolute path to avoid CWD issues)
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/transcribe")
async def transcribe(youtube_url: str = Form(...)):
    """
    Accepts a YouTube URL, downloads audio, transcribes it, and returns JSON.
    """
    # Download audio from YouTube using yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        # Let yt-dlp manage the file name, ensure it's placed in TEMP_DIR
        'outtmpl': str(Path(TEMP_DIR) / '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        # Point to the bin directory so yt-dlp can find ffmpeg and ffprobe
        'ffmpeg_location': r"C:\ffmpeg-8.0-essentials_build\bin",
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dl_info = ydl.extract_info(youtube_url, download=True)

            # Try to get the final output path after post-processing
            audio_path = None
            requested = dl_info.get('requested_downloads') if isinstance(dl_info, dict) else None
            if requested:
                # Newer yt-dlp populates the final filepath here
                audio_path = requested[0].get('filepath')
            if not audio_path:
                # Fallback: construct from prepared filename, assuming mp3 after postproc
                prepared = ydl.prepare_filename(dl_info)
                audio_path = str(Path(prepared).with_suffix('.mp3'))
    except Exception as e:
        return {"error": f"Failed to download audio: {str(e)}"}
    

    # Run Faster-Whisper transcription
    try:
        # Ensure the file actually exists before transcribing
        if not os.path.exists(audio_path):
            return {"error": f"Audio file not found after download: {audio_path}"}

        segments, asr_info = model.transcribe(audio_path, beam_size=5)
        text = " ".join([seg.text for seg in segments])
    except Exception as e:
        # Best-effort cleanup on failure
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass
        return {"error": f"Transcription failed: {str(e)}"}

    # Remove temp file
    try:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        # Do not fail the request if cleanup fails
        pass

    return {
        "language_detected": asr_info.language,
        "transcription": text
    }
