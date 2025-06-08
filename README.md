
# 🎙️ Multi-Speaker Text-to-Speech API

Convert your scripts into dynamic audio with distinct voices for different speakers. This FastAPI application transforms dialogue into an MP3 audio file, ideal for podcasts, audiobooks, or presentations.

---

## ✨ Features

* **Multi-Speaker Support**: Assigns distinct voices (S1, S2) to different speakers.
* **In-Memory Audio Generation**: Efficiently creates audio directly in memory, optimizing for deployment.
* **Streaming Responses**: Delivers audio as a streaming MP3 file.
* **Health Checks**: Includes an endpoint for monitoring application status.

---

## 🚀 Quick Start

### Running the Application

To run the application, use Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be accessible at `http://0.0.0.0:8000`.

---

## 💡 Usage

### Web Interface

Access the interactive web interface in your browser:

`http://localhost:8000/`

Enter your script here to generate audio.

### API Endpoint

**Endpoint**: `POST /generate-audio`

**Request Body**:

```json
{
  "script": "S1: Hello there!\nS2: General Kenobi."
}
```

**Example `curl` Request**:

```bash
curl -X POST "http://localhost:8000/generate-audio" \
-H "Content-Type: application/json" \
-d '{
  "script": "S1: Welcome to our podcast!\nS2: Today, we\'re discussing AI."
}' \
--output podcast_example.mp3
```

This downloads the generated audio as `podcast_example.mp3`.

---

## 📝 Script Format

Use this format to assign speakers:

```
S1: Welcome to our podcast!
S2: Today, we're discussing the latest in AI.
```

---

## 🗣️ Voice Mapping

* **S1**: `en-US-AriaNeural` (US English)
* **S2**: `en-GB-RyanNeural` (UK English)

---
