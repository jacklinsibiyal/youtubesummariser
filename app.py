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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatted_transcript = format_transcript_with_timestamps(transcript)

        # Get the video title using YouTube Data API
        video_title = get_video_title(video_id)
        if not video_title:
            video_title = "Unknown Title"

        return jsonify({
            "title": video_title,
            "transcript": formatted_transcript
        })
    except YouTubeTranscriptApi.CouldNotRetrieveTranscript as e:
        return jsonify({"error": "Could not retrieve transcript"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/summarize', methods=['POST'])
def summarize_transcript():
    try:
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
    app.run(debug=True,port=5000)