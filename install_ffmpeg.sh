#!/usr/bin/env bash
# Install ffmpeg at runtime instead of build
if ! command -v ffmpeg &> /dev/null
then
    echo "Installing ffmpeg..."
    apt-get update && apt-get install -y ffmpeg
else
    echo "ffmpeg already installed."
fi

# Start the app
uvicorn main:app --host 0.0.0.0 --port 8000
