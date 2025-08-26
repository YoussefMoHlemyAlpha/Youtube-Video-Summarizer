import streamlit as st
import yt_dlp
import requests
import re
import os
from dotenv import load_dotenv
import json
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def extract_transcript_yt_dlp(video_url):
    try:
        # Extract video_id for thumbnail
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            raise ValueError("Invalid YouTube URL format")


        # yt-dlp options to extract subtitles
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US'],
            'skip_download': True,
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subtitles = info.get('subtitles', {}).get('en') or info.get('subtitles', {}).get('en-US') or \
                       info.get('automatic_captions', {}).get('en') or info.get('automatic_captions', {}).get('en-US')
            
            if not subtitles:
                st.error("No English subtitles or captions found for this video.")
                st.write("Available subtitle languages:", list(info.get('subtitles', {}).keys()))
                st.write("Available caption languages:", list(info.get('automatic_captions', {}).keys()))
                return None, video_id

            # Select subtitle format (prefer vtt or srt)
            subtitle_url = None
            for entry in subtitles:
                if entry.get('ext') in ['vtt', 'srt']:
                    subtitle_url = entry['url']
                    break
                elif entry.get('ext') == 'json3' and not subtitle_url:
                    subtitle_url = entry['url']

            if not subtitle_url:
                st.error("No suitable subtitle format (vtt, srt, or json3) found.")
                return None, video_id

            # Fetch subtitle content
            response = requests.get(subtitle_url)
            response.raise_for_status()
            subtitle_content = response.text

            # Parse subtitle content
            transcript_text = []
            if subtitle_url.endswith('vtt'):
                lines = subtitle_content.split('\n')
                for line in lines:
                    if not line.strip() or line.startswith('WEBVTT') or '-->' in line:
                        continue
                    transcript_text.append(line.strip())
            elif subtitle_url.endswith('srt'):
                lines = subtitle_content.split('\n')
                for line in lines:
                    if not line.strip() or '-->' in line or line.isdigit():
                        continue
                    transcript_text.append(line.strip())
            elif subtitle_url.endswith('json3'):
                subtitle_data = json.loads(subtitle_content)
                events = subtitle_data.get('events', [])
                for event in events:
                    segments = event.get('segs', [])
                    for seg in segments:
                        text = seg.get('utf8', '').strip()
                        if text:
                            transcript_text.append(text)

            if not transcript_text:
                st.error("No valid transcript text extracted from subtitles.")
                return None, video_id

            transcript = " ".join(transcript_text)
            return transcript, video_id

    except Exception as e:
        st.error(f"Error extracting transcript with yt-dlp: {str(e)}")
        return None, video_id
#Prompt

prompt="""You are Yotube video summarizer. You will be taking the transcript text
and summarizing the entire video and providing the important summary in points
within 300 words. Please provide the summary of the text given here:  """


# Summarization
def summarize_transcript(transcript_text):
    try:
        # Validate transcript length
        transcript_length = len(transcript_text.strip())
        if not transcript_text or transcript_length < 50:
            st.error(f"Transcript is too short for summarization ({transcript_length} characters). Minimum required: 50 characters.")
            return None

        model=genai.GenerativeModel('gemini-2.5-flash')    
        response=model.generate_content(prompt+transcript_text)
        return response.text

    except Exception as e:
        st.error(f"Error summarizing transcript: {str(e)}")
        return None

# Streamlit UI
st.title("YouTube Video Summarizer")
video_url = st.text_input("Enter YouTube Video URL:")

if video_url:
    try:
        # Extract transcript and video ID
        transcript_text, video_id = extract_transcript_yt_dlp(video_url)
        
        # Display thumbnail if video_id is valid
        if video_id:
            st.image(f"https://img.youtube.com/vi/{video_id}/0.jpg", width=700)

        if st.button("Summarize"):
            if transcript_text:
                with st.spinner("Generating summary..."):
                    summary = summarize_transcript(transcript_text)
                    if summary:
                        st.subheader("Summary:")
                        st.write(summary)
            else:
                st.error("Cannot generate summary: No transcript available.")
    except Exception as e:
        st.error(f"Error processing URL: {str(e)}")