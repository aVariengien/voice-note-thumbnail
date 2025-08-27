# Voice Note Thumbnail Generator

A Streamlit application that converts voice notes into visual thumbnails using Groq's high-speed AI inference with Whisper 3 and Llama 70B.

## Features

- Upload audio files (MP3, WAV, M4A, FLAC)
- **Ultra-fast transcription** using Groq Whisper 3
- **Smart quote extraction** using Llama 3.1 70B Versatile
- **Manual text size control** with real-time adjustment
- **High-resolution thumbnails** (1024x1024) with:
  - Beautiful gradient backgrounds
  - Real emoji images from Twemoji
  - Actual quotes from your voice notes
  - Size-based importance hierarchy

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Get your Groq API key:**
   - Visit [https://console.groq.com/keys](https://console.groq.com/keys)
   - Create a free account and generate an API key

3. **Set up environment:**
```bash
export GROQ_API_KEY="your-groq-api-key-here"
```

4. **Run the application:**
```bash
streamlit run app.py
```

## Usage

1. Upload an audio file
2. Click "Generate Thumbnail" 
3. Use the **Text Size Multiplier** slider to adjust text size
4. Download your custom thumbnail

## Technology Stack

- **Transcription**: Groq Whisper Large v3 (ultra-fast, high-accuracy)
- **Quote Analysis**: Llama 3.1 70B Versatile (powerful language understanding)
- **Emoji Rendering**: Twemoji (high-quality emoji images)
- **Text Rendering**: Cross-platform font handling with wrapping
- **Interface**: Streamlit with real-time controls

## Performance

- **Lightning Fast**: Groq's LPU inference delivers 276+ tokens/second
- **High Quality**: 1024x1024 resolution thumbnails
- **Smart Caching**: Emoji images cached for faster regeneration
- **Real-time Updates**: Instant text size adjustments