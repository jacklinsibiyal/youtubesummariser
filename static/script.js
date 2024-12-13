let userScrolled = false;

window.addEventListener('scroll', () => {
    userScrolled = true;
});

async function extractVideoId(url) {
    try {
        const parsedUrl = new URL(url);

        if (parsedUrl.hostname === 'www.youtube.com' || parsedUrl.hostname === 'youtube.com') {
            const queryParams = new URLSearchParams(parsedUrl.search);
            // Handle regular YouTube URLs
            if (queryParams.has('v')) {
                return queryParams.get('v');
            }

            // Handle YouTube Shorts (e.g., https://www.youtube.com/shorts/VIDEO_ID)
            const pathParts = parsedUrl.pathname.split('/');
            if (pathParts[1] === 'shorts') {
                return pathParts[2]; // The video ID is after '/shorts/'
            }

        } else if (parsedUrl.hostname === 'youtu.be') {
            // Handle short YouTube URLs (e.g., https://youtu.be/VIDEO_ID)
            return parsedUrl.pathname.slice(1); // Extract video ID from youtu.be link
        }
    } catch (error) {
        console.error('Invalid URL:', error);
    }
    return null;
}


async function fetchTranscript() {
    const url = document.getElementById('youtube-url').value;
    const videoId = await extractVideoId(url);

    if (videoId) {
        try {
            showLoading(true);
            const response = await fetch(`/api/transcript/${videoId}`);
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }
            document.getElementById('video-title').textContent = data.title;
            document.getElementById('transcript').textContent = data.transcript;
            document.getElementById('summarize-btn').disabled = false;
            showToast('Transcript fetched successfully', 'success');

            // Scroll the transcript container to the top
            document.querySelector('.transcript-container').scrollTop = 0;

            document.getElementById('youtube-url').value = '';
        } catch (error) {
            showToast(`Error fetching transcript: ${error.message}`, 'error');
        } finally {
            showLoading(false);
        }
    } else {
        showToast('Invalid YouTube URL', 'error');
    }
}

async function summarizeTranscript() {
    const transcriptText = document.getElementById('transcript').textContent;
    const videoTitle = document.getElementById('video-title').textContent;

    if (!transcriptText) {
        showToast('No transcript available to summarize!', 'error');
        return;
    }

    try {
        showLoading(true);
        const response = await fetch('/api/summarize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: transcriptText,
                title: videoTitle
            }),
        });

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById('transcript').innerHTML = data.summary_html;
        showToast('Transcript summarized successfully', 'success');
    } catch (error) {
        showToast(`Error summarizing transcript: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

function copyTranscript() {
    const transcript = document.getElementById('transcript').textContent;
    navigator.clipboard.writeText(transcript)
        .then(() => {
            showToast('Transcript copied to clipboard!', 'success');
            const copyBtn = document.getElementById('copy-btn');
            copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>';
            setTimeout(() => {
                copyBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>';
            }, 2000);
        })
        .catch(err => {
            showToast('Failed to copy transcript', 'error');
        });
}

function clearTranscript() {
    document.getElementById('video-title').textContent = '';
    document.getElementById('transcript').textContent = '';
    document.getElementById('summarize-btn').disabled = true;
    showToast('Transcript cleared', 'info');
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

function showLoading(isLoading) {
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.textContent = isLoading ? 'Loading...' : 'Submit';
    submitBtn.disabled = isLoading;
}

document.getElementById('youtube-url').addEventListener('keyup', (event) => {
    if (event.key === 'Enter') {
        fetchTranscript();
    }
});

const themeToggle = document.getElementById('theme-toggle');
themeToggle.addEventListener('change', () => {
    document.body.classList.toggle('dark-mode');
});