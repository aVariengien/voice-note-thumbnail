import streamlit as st
import io
import json
import random
import math
from PIL import Image, ImageDraw, ImageFont
import requests
from litellm import completion
from groq import Groq
import tempfile
import os

st.set_page_config(page_title="Voice Note Thumbnail Generator", page_icon="🎤", layout="wide")

@st.cache_data
def get_emoji_image(emoji, size=64):
    """Download emoji image from Twemoji and return PIL Image"""
    try:
        # Convert emoji to unicode codepoint
        codepoint = format(ord(emoji), 'x')
        
        # Twemoji URL format - use larger source image for better quality
        url = f"https://twemoji.maxcdn.com/v/latest/svg/{codepoint}.svg"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            # For SVG, we'll try PNG as backup since PIL doesn't handle SVG well
            pass
    except:
        pass
    
    # Try PNG version
    try:
        codepoint = format(ord(emoji), 'x')
        url = f"https://twemoji.maxcdn.com/v/latest/72x72/{codepoint}.png"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            emoji_img = Image.open(io.BytesIO(response.content))
            # Use high-quality resampling for better results
            emoji_img = emoji_img.resize((size, size), Image.Resampling.LANCZOS)
            return emoji_img
    except:
        pass
    
    # Fallback: create a colored circle with higher quality
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255), 
              (255, 255, 100), (255, 100, 255), (100, 255, 255)]
    color = random.choice(colors)
    # Add gradient effect for better quality
    for i in range(size//4):
        shade = int(255 * (1 - i/(size//4) * 0.3))
        circle_color = tuple(min(255, int(c * shade/255)) for c in color) + (180,)
        draw.ellipse([i, i, size-i-1, size-i-1], fill=circle_color)
    return img

def main():
    st.title("🎤 Voice Note Thumbnail Generator")
    st.markdown("Upload a voice note and generate a visual thumbnail with quotes and emojis!")
    
    # Check for Groq API key
    if 'GROQ_API_KEY' not in os.environ:
        st.error("Please set your GROQ_API_KEY environment variable")
        st.info("Get your API key from: https://console.groq.com/keys")
        st.code("export GROQ_API_KEY='your-api-key-here'")
        return
    
    uploaded_file = st.file_uploader("Choose an audio file", type=['mp3', 'wav', 'm4a', 'flac', 'ogg', 'oga'])
    
    if uploaded_file is not None:
        st.audio(uploaded_file, format='audio/wav')
        
        if st.button("Generate Thumbnail", type="primary"):
            with st.spinner("Processing your voice note..."):
                try:
                    # Process the audio file and store in session state
                    quotes_data = process_voice_note_data(uploaded_file)
                    st.session_state.quotes_data = quotes_data
                    st.session_state.has_data = True
                    
                except Exception as e:
                    st.error(f"Error processing voice note: {str(e)}")
        
        # Display controls and thumbnail if we have data
        if hasattr(st.session_state, 'has_data') and st.session_state.has_data:
            st.success("Voice note processed successfully!")
            

            # Add manual text size control
            st.subheader("Adjust Text Size")
            text_size_multiplier = st.slider(
                "Text Size Multiplier", 
                min_value=0.1, 
                max_value=1.0, 
                value=0.35, 
                step=0.05,
                help="Adjust the overall text size",
                key="text_size_slider"
            )
            
            # Generate thumbnail with current settings
            with st.spinner("Generating thumbnail..."):
                thumbnail = create_thumbnail(st.session_state.quotes_data, text_size_multiplier)
            
            st.image(thumbnail, caption="Your Voice Note Thumbnail", width=400)
            
            # Option to download
            buf = io.BytesIO()
            thumbnail.save(buf, format='PNG')
            buf.seek(0)
            
            st.download_button(
                label="Download Thumbnail",
                data=buf,
                file_name="voice_note_thumbnail.png",
                mime="image/png"
            )
            
            # Option to clear and start over
            if st.button("Process New Audio", type="secondary"):
                if 'has_data' in st.session_state:
                    del st.session_state.has_data
                if 'quotes_data' in st.session_state:
                    del st.session_state.quotes_data
                st.rerun()

            # Live prompt editor
            st.subheader("Customize Quote Extraction")
            
            # Default prompt
            default_prompt = """Based on this transcript: "{transcript}"

Please provide a JSON response with:
1. "quotes": 5 most impactful quotes/sentences/questions from the transcript with importance scores 1-10
   - Extract actual sentences, questions, key phrases, or action points from the transcript
   - Choose the most memorable, important, or striking parts
   - You can remove audio sounds 'like', 'hmmm', 'huu', for clarity but keep the sentence close to the transcript, like a how a quote can be edited in a newspaper
   - Keep the quote short (< 30 words)
2. "emojis": 10 most relevant emojis with weights 1-10 (higher weight = more frequent)

Format:
{{
    "quotes": [
        {{"text": "actual quote from transcript", "importance": 9}},
        {{"text": "key question asked", "importance": 8}},
        ...
    ],
    "emojis": [
        {{"emoji": "🎵", "weight": 9}},
        ...
    ]
}}

Only respond with valid JSON, no other text."""

            # Live prompt editor
            custom_prompt = st.text_area(
                "Edit Prompt (use {transcript} placeholder):",
                value=default_prompt,
                height=300,
                help="Modify the prompt to change how quotes are extracted. Use {transcript} where the transcript should be inserted.",
                key="custom_prompt"
            )
            
            # Re-extract quotes when prompt changes or button pressed
            if st.button("Re-extract Quotes with Custom Prompt", type="secondary"):
                with st.spinner("Re-extracting quotes with custom prompt..."):
                    st.session_state.quotes_data = extract_quotes_with_custom_prompt(
                        st.session_state.transcript, 
                        custom_prompt
                    )
            
            st.subheader("Transcript")
            st.write(st.session_state.transcript)

def process_voice_note_data(uploaded_file):
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    
    try:
        # Initialize Groq client
        client = Groq()
        
        # Transcribe using Groq Whisper 3
        st.info("Transcribing audio with Groq Whisper 3 Turbo...")
        
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(tmp_path, audio_file.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
            )
        
        transcript = transcription.text
        st.write("**Transcript:**", transcript)
        
        # Store transcript in session state for later use
        st.session_state.transcript = transcript
        
        # Extract quotes and get emojis using Llama 70B
        quotes_data = extract_quotes_and_emojis(transcript)
        
        return quotes_data
        
    finally:
        # Clean up temp file
        os.unlink(tmp_path)

def extract_quotes_and_emojis(transcript):
    st.info("Extracting quotes and emojis with Llama 70B...")
    
    prompt = f"""
    Based on this transcript: "{transcript}"
    
    Please provide a JSON response with:
    1. "quotes": 5 most impactful quotes/sentences/questions from the transcript with importance scores 1-10
    - Extract actual sentences, questions, key phrases, or action points from the transcript
    - Choose the most memorable, important, or striking parts
    - You can remove audio sounds 'like', 'hmmm', 'huu', for clarity but keep the sentence close to the transcript, like a how a quote can be edited in a newspaper but still really needs to stay faithful to what the person says
    - Keep the quote short, but this can be a full sentence (< 30 words)
    - For the first quote, add a sort of title for the whole voice note
    2. "emojis": 10 most relevant emojis with weights 1-10 (higher weight = more frequent)
    
    Format:
    {{
        "quotes": [
            {{"text": "actual quote from transcript", "importance": 9}},
            {{"text": "key question asked", "importance": 8}},
            ...
        ],
        "emojis": [
            {{"emoji": "🎵", "weight": 9}},
            ...
        ]
    }}
    
    Only respond with valid JSON, no other text.
    """
    
    try:
        response = completion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{
                "role": "user", 
                "content": prompt
            }],
            max_tokens=1000,
            temperature=0.3
        )
        
        # Extract JSON from response
        json_text = response.choices[0].message.content
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]
        
        data = json.loads(json_text.strip())
        
        st.write("**Key Quotes:**", [f"'{k['text']}' ({k['importance']})" for k in data['quotes']])
        st.write("**Emojis:**", [f"{e['emoji']} ({e['weight']})" for e in data['emojis']])
        
        return data
        
    except Exception as e:
        st.error(f"Error parsing quotes/emojis: {e}")
        # Fallback data
        return {
            "quotes": [{"text": "voice note", "importance": 5}],
            "emojis": [{"emoji": "🎤", "weight": 5}]
        }

def extract_quotes_with_custom_prompt(transcript, custom_prompt):
    """Extract quotes using a custom user-provided prompt"""
    st.info("Re-extracting quotes with custom prompt...")
    
    # Format the custom prompt with the transcript
    formatted_prompt = custom_prompt.format(transcript=transcript)
    
    try:
        response = completion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{
                "role": "user", 
                "content": formatted_prompt
            }],
            max_tokens=1000,
            temperature=0.3
        )
        
        # Extract JSON from response
        json_text = response.choices[0].message.content
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]
        
        data = json.loads(json_text.strip())
        
        st.write("**Updated Quotes:**", [f"'{k['text']}' ({k['importance']})" for k in data['quotes']])
        st.write("**Updated Emojis:**", [f"{e['emoji']} ({e['weight']})" for e in data['emojis']])
        
        return data
        
    except Exception as e:
        st.error(f"Error with custom prompt: {e}")
        # Return existing data if custom prompt fails
        return st.session_state.quotes_data if hasattr(st.session_state, 'quotes_data') else {
            "quotes": [{"text": "voice note", "importance": 5}],
            "emojis": [{"emoji": "🎤", "weight": 5}]
        }

def create_thumbnail(data, text_size_multiplier=1.0):
    st.info("Generating thumbnail image...")
    
    # High resolution image dimensions
    size = 1024  # Doubled for higher quality
    
    # Create gradient background
    img = create_gradient_background(size)
    
    # Create emoji background
    create_emoji_background(img, size, data['emojis'])
    
    # Add quote text overlay with custom size
    add_text_overlay(img, size, data['quotes'], text_size_multiplier)
    
    return img

def create_gradient_background(size):
    # Create a subtle gradient background
    img = Image.new('RGB', (size, size))
    
    # Color palette options
    palettes = [
        [(240, 248, 255), (176, 196, 222)],  # Light blue gradient
        [(255, 248, 240), (255, 218, 185)],  # Warm orange gradient
        [(248, 255, 248), (200, 255, 200)],  # Light green gradient
        [(255, 240, 245), (255, 182, 193)],  # Pink gradient
        [(248, 248, 255), (221, 160, 221)],  # Purple gradient
    ]
    
    # Randomly select a palette
    colors = random.choice(palettes)
    
    pixels = []
    for y in range(size):
        ratio = y / size
        r = int(colors[0][0] * (1 - ratio) + colors[1][0] * ratio)
        g = int(colors[0][1] * (1 - ratio) + colors[1][1] * ratio)
        b = int(colors[0][2] * (1 - ratio) + colors[1][2] * ratio)
        
        for _ in range(size):
            pixels.append((r, g, b))
    
    img.putdata(pixels)
    return img

def create_emoji_background(img, size, emojis):
    try:
        # Create grid of emojis based on weights - more emojis for full coverage
        emoji_positions = []
        for emoji_data in emojis:
            count = max(2, emoji_data['weight'])  # More emojis per weight
            for _ in range(count):
                emoji_positions.append(emoji_data['emoji'])
        
        # Shuffle for random placement
        random.shuffle(emoji_positions)
        
        # Calculate emoji size for the image
        emoji_size = 64  # Larger emoji size
        
        # Place emojis randomly across the entire image for even distribution
        for emoji in emoji_positions:
            # Random position across the entire image
            x = random.randint(0, size - emoji_size)
            y = random.randint(0, size - emoji_size)
            
            # Get emoji image
            emoji_img = get_emoji_image(emoji, emoji_size)
            
            # Create semi-transparent version
            if emoji_img.mode != 'RGBA':
                emoji_img = emoji_img.convert('RGBA')
            
            # Apply moderate transparency
            alpha = emoji_img.split()[-1]
            alpha = alpha.point(lambda p: int(p * 0.6))  # 60% opacity (more visible)
            emoji_img.putalpha(alpha)
            
            # Paste onto background
            img.paste(emoji_img, (int(x), int(y)), emoji_img)
                
    except Exception as e:
        st.warning(f"Using fallback background: {e}")
        # Simple colored shapes fallback with full coverage
        draw = ImageDraw.Draw(img)
        colors = [(255, 200, 200, 150), (200, 255, 200, 150), (200, 200, 255, 150), 
                  (255, 255, 200, 150), (255, 200, 255, 150), (200, 255, 255, 150)]
        for _ in range(80):  # Many more shapes for full coverage
            x = random.randint(0, size - 60)
            y = random.randint(0, size - 60)
            color = random.choice(colors)
            shape_size = random.randint(30, 80)
            draw.ellipse([x, y, x + shape_size, y + shape_size], fill=color)  # Various sizes

def wrap_text(text, font, max_width):
    """Wrap text to fit within max_width"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), test_line, font=font)
        test_width = bbox[2] - bbox[0]
        
        if test_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)  # Word is too long, but add it anyway
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def add_text_overlay(img, size, quotes, text_size_multiplier=1.0):
    # Sort quotes by importance
    quotes.sort(key=lambda k: k['importance'], reverse=True)
    
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to load a nice bold font
        font_paths = [
            "/System/Library/Fonts/Arial Bold.ttc",
            "/System/Library/Fonts/Helvetica-Bold.ttc",
            "/System/Library/Fonts/Arial.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Windows/Fonts/arialbd.ttf",
            "/Windows/Fonts/arial.ttf"
        ]
        base_font = None
        for font_path in font_paths:
            try:
                ImageFont.truetype(font_path, 20)  # Test if font works
                base_font = font_path
                break
            except:
                continue
    except:
        pass
    
    y_offset = size // 12  # Start higher up
    max_text_width = size - 120  # Leave margins
    
    for quote in quotes:  # Limit to top 3 quotes
        # Calculate font size based on importance - MASSIVE text
        base_size = size // 4  # Much bigger base (1024/4 = 256px base!)
        font_size = int(base_size * (quote['importance'] / 10) * text_size_multiplier)
        font_size = max(int(150 * text_size_multiplier), min(font_size, int(size // 2 * text_size_multiplier)))  # Apply multiplier
        
        text = quote['text']
        
        # Load font - force a real font, not default
        font = None
        if base_font:
            try:
                font = ImageFont.truetype(base_font, font_size)
                print(f"Loaded font {base_font} at size {font_size}")
            except Exception as e:
                print(f"Failed to load {base_font}: {e}")
        
        # If no font loaded, try system fonts directly
        if font is None:
            system_fonts = [
                "/System/Library/Fonts/Arial.ttc",
                "/System/Library/Fonts/Helvetica.ttc"
            ]
            for font_path in system_fonts:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"Loaded system font {font_path} at size {font_size}")
                    break
                except:
                    continue
        
        # Absolute fallback - but still try to make it big
        if font is None:
            print(f"Using default font - this might be small!")
            font = ImageFont.load_default()
        
        # Show debug info in Streamlit
        
        # Wrap text if needed
        lines = wrap_text(text, font, max_text_width)
        
        # Calculate total height for all lines
        total_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            line_heights.append(line_height)
            total_height += line_height
        
        # Add line spacing
        line_spacing = font_size // 4
        total_height += line_spacing * (len(lines) - 1)
        
        # Check if text fits vertically
        if y_offset + total_height < size - 100:
            current_y = y_offset
            
            for i, line in enumerate(lines):
                # Get line dimensions
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                line_height = line_heights[i]
                
                # Center line horizontally
                x = (size - line_width) // 2
                
                # Draw text outline for visibility - very thick
                outline_width = 4
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, current_y + dy), line, font=font, fill='white')
                
                # Draw main text
                draw.text((x, current_y), line, font=font, fill='black')
                
                current_y += line_height + line_spacing
            
            y_offset = current_y + 40  # Space between quotes

if __name__ == "__main__":
    main()