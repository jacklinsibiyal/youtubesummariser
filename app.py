import os
from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from googleapiclient.discovery import build
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.schema import Document 
import math
import markdown
import logging
from flask_cors import CORS
import yt_dlp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Get the API key from the environment
groq_api_key = os.getenv('GROQ_API_KEY')
youtube_api_key = os.getenv('YOUTUBE_API_KEY')

# Initialize the YouTube API client
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

# Initialize the LLM model
llm = ChatGroq(groq_api_key=groq_api_key, model_name="llama-3.3-70b-versatile")

# Define the summarization prompt template
prompt = ChatPromptTemplate.from_template(
    """
    Summarize the provided youtube transcript. Write a short summary and then Mention all key points in a clear and concise manner in bullet points.
    Mention the youtube title and then summarise it.

    <context>
    {context}
    <context>
    """
)

@app.route('/')
def index():
    return render_template('index.html')

# Fetch video metadata including the title
def get_video_title(video_id):
    try:
        video_response = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()

        video_title = video_response['items'][0]['snippet']['title']
        return video_title
    except Exception as e:
        return None

@app.route('/api/transcript/<video_id>', methods=['GET'])
def get_transcript(video_id):
    try:
        logger.info(f"Fetching transcript for video ID: {video_id}")
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as e:
        logger.warning(f"YouTubeTranscriptApi failed, falling back to yt-dlp: {str(e)}") # yt-dlp is a better alternative
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'writesubtitles': True,
                'subtitleslangs': ['en'],
                'writeautomaticsub': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                subtitles = info_dict.get("subtitles") or info_dict.get("automatic_captions")
                if subtitles and 'en' in subtitles:
                    transcript = [{'text': sub['text'], 'start': sub['start'], 'duration': sub['duration']} for sub in subtitles['en']]
                else:
                    raise Exception("No subtitles available.")
        except Exception as yt_dlp_error:
            logger.error(f"Error fetching transcript from yt-dlp: {str(yt_dlp_error)}")
            return jsonify({"error": "Could not retrieve transcript"}), 500

    formatted_transcript = format_transcript_with_timestamps(transcript)

    logger.info("Fetching video title")
    video_title = get_video_title(video_id)
    if not video_title:
        video_title = "Unknown Title"
        logger.warning("Could not fetch video title")

    return jsonify({
        "title": video_title,
        "transcript": formatted_transcript
    })

@app.route('/api/summarize', methods=['POST'])
def summarize_transcript():
    try:
        logger.info("Starting summarisation request")
        data = request.json
        transcript_text = data.get('text')
        video_title = data.get('title')

        if not transcript_text or not video_title:
            return jsonify({'error': 'No transcript or title provided'}), 400

        # Combine the video title and transcript text
        full_context = f"Youtube Video Title: {video_title}\n\nTranscript: {transcript_text}"

        # Convert the combined text to a Document object
        document = Document(page_content=full_context)

        # Create a chain for summarizing documents
        document_chain = create_stuff_documents_chain(llm, prompt)

        # Invoke the chain with the document object (wrapped in a list)
        response = document_chain.invoke({'context': [document]})

        # Check if the response is valid
        if not response or response.strip() == "":
            return jsonify({'error': 'No summary available'}), 500

        # Convert LLM's Markdown response to HTML
        html_summary = markdown.markdown(response, extensions=['extra', 'sane_lists'])

        # Return both Markdown and HTML in the JSON response
        return jsonify({
            'summary_markdown': response,  # Original Markdown
            'summary_html': html_summary   # HTML conversion
        })
        
    except Exception as e:
        logger.error(f"Error in summarize_transcript: {str(e)}")
        return jsonify({'error': str(e)}), 500


def format_transcript_with_timestamps(transcript):
    formatted_transcript = []
    current_time = 0
    for entry in transcript:
        start_time = entry['start']
        duration = entry['duration']
        text = entry['text']
        
        # Add a timestamp every 30 seconds
        if start_time >= current_time + 30:
            current_time = math.floor(start_time / 30) * 30
            formatted_transcript.append(f"[{format_time(current_time)}]\n")
        
        formatted_entry = f"{text}\n"
        formatted_transcript.append(formatted_entry)
    return ''.join(formatted_transcript)

def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

if __name__ == '__main__':
    app.run(host='0.0.0.0')