import os
import json
import re
from datetime import datetime, timedelta
from collections import Counter
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

CACHE_FILE = 'data/cache.json'

def get_youtube_client():
    """Get authenticated YouTube client using Replit integration"""
    try:
        hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
        x_replit_token = None
        
        repl_identity = os.getenv('REPL_IDENTITY')
        web_repl_renewal = os.getenv('WEB_REPL_RENEWAL')
        
        if repl_identity:
            x_replit_token = 'repl ' + repl_identity
        elif web_repl_renewal:
            x_replit_token = 'depl ' + web_repl_renewal
        
        if not x_replit_token or not hostname:
            raise Exception("Replit environment not configured")
        
        response = requests.get(
            f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=youtube',
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            }
        )
        
        connection_data = response.json()
        if not connection_data.get('items'):
            raise Exception("YouTube not connected. Please set up the YouTube integration.")
        
        connection_settings = connection_data['items'][0]
        
        access_token = connection_settings.get('settings', {}).get('access_token')
        refresh_token = connection_settings.get('settings', {}).get('refresh_token')
        expires_at = connection_settings.get('settings', {}).get('expires_at')
        
        if not access_token:
            oauth_data = connection_settings.get('settings', {}).get('oauth', {})
            credentials_data = oauth_data.get('credentials', {})
            access_token = credentials_data.get('access_token')
            refresh_token = credentials_data.get('refresh_token')
            expires_at = oauth_data.get('expires_at')
        
        if not access_token:
            raise Exception("No access token found in connector settings")
        
        expiry = None
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except:
                pass
        
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=connection_settings.get('settings', {}).get('oauth', {}).get('client_id'),
            client_secret=connection_settings.get('settings', {}).get('oauth', {}).get('client_secret'),
            expiry=expiry
        )
        
        youtube = build('youtube', 'v3', credentials=credentials)
        return youtube
        
    except Exception as e:
        print(f"Error getting YouTube client with connector: {e}")
        api_key = os.getenv('YOUTUBE_API_KEY')
        if api_key:
            print("Falling back to YOUTUBE_API_KEY from environment")
            return build('youtube', 'v3', developerKey=api_key)
        raise Exception(f"YouTube authentication failed: {e}")

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def load_cache():
    """Load cached API responses"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Save API responses to cache"""
    os.makedirs('data', exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def get_video_details(youtube, video_ids):
    """Fetch video details from YouTube API"""
    cache = load_cache()
    results = []
    uncached_ids = []
    
    for video_id in video_ids:
        if video_id in cache.get('videos', {}):
            results.append(cache['videos'][video_id])
        else:
            uncached_ids.append(video_id)
    
    if uncached_ids:
        try:
            response = youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(uncached_ids)
            ).execute()
            
            for item in response.get('items', []):
                video_data = {
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'upload_date': item['snippet']['publishedAt'],
                    'views': int(item['statistics'].get('viewCount', 0)),
                    'likes': int(item['statistics'].get('likeCount', 0)),
                    'comments': int(item['statistics'].get('commentCount', 0)),
                    'duration': item['contentDetails']['duration'],
                    'tags': item['snippet'].get('tags', [])
                }
                results.append(video_data)
                
                if 'videos' not in cache:
                    cache['videos'] = {}
                cache['videos'][item['id']] = video_data
            
            save_cache(cache)
        except Exception as e:
            print(f"Error fetching video details: {e}")
    
    return results

def get_channel_stats(youtube, channel_ids):
    """Fetch channel statistics"""
    cache = load_cache()
    results = {}
    uncached_ids = []
    
    for channel_id in channel_ids:
        if channel_id in cache.get('channels', {}):
            results[channel_id] = cache['channels'][channel_id]
        else:
            uncached_ids.append(channel_id)
    
    if uncached_ids:
        try:
            response = youtube.channels().list(
                part='statistics',
                id=','.join(uncached_ids)
            ).execute()
            
            for item in response.get('items', []):
                channel_data = {
                    'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
                    'video_count': int(item['statistics'].get('videoCount', 0))
                }
                results[item['id']] = channel_data
                
                if 'channels' not in cache:
                    cache['channels'] = {}
                cache['channels'][item['id']] = channel_data
            
            save_cache(cache)
        except Exception as e:
            print(f"Error fetching channel stats: {e}")
    
    return results

def parse_duration(duration):
    """Parse ISO 8601 duration to minutes"""
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 60 + minutes + seconds / 60
    return 0

def extract_keywords(titles, top_n=3):
    """Extract main keywords from video titles"""
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'how', 'what', 'why', 'when', 'where', 'who', 'this', 'that', 'these', 'those', 'i', 'you', 'we', 'they', 'my', 'your', 'our', 'their', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
    
    words = []
    for title in titles:
        cleaned = re.sub(r'[^\w\s]', '', title.lower())
        words.extend([w for w in cleaned.split() if w not in stop_words and len(w) > 3])
    
    counter = Counter(words)
    return [word for word, count in counter.most_common(top_n)]

def get_related_videos(youtube, video_id, max_results=5):
    """Fetch related videos for a given video"""
    cache = load_cache()
    cache_key = f'related_{video_id}_{max_results}'
    
    if cache_key in cache.get('related', {}):
        return cache['related'][cache_key]
    
    try:
        response = youtube.search().list(
            part='snippet',
            relatedToVideoId=video_id,
            type='video',
            maxResults=max_results
        ).execute()
        
        related = []
        for item in response.get('items', []):
            related.append({
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel_title': item['snippet']['channelTitle']
            })
        
        if 'related' not in cache:
            cache['related'] = {}
        cache['related'][cache_key] = related
        save_cache(cache)
        
        return related
    except Exception as e:
        print(f"Error fetching related videos: {e}")
        return []

def calculate_metrics(video_data, channel_stats):
    """Calculate all metrics for videos"""
    results = []
    
    for video in video_data:
        channel_id = video['channel_id']
        channel_info = channel_stats.get(channel_id, {})
        
        upload_date = datetime.fromisoformat(video['upload_date'].replace('Z', '+00:00'))
        days_since_upload = (datetime.now(upload_date.tzinfo) - upload_date).days
        days_since_upload = max(days_since_upload, 1)
        
        duration_minutes = parse_duration(video['duration'])
        view_velocity = video['views'] / days_since_upload if days_since_upload > 0 else 0
        engagement = ((video['likes'] + video['comments']) / video['views'] * 100) if video['views'] > 0 else 0
        
        subscriber_count = channel_info.get('subscriber_count', 0)
        video_count = channel_info.get('video_count', 1)
        
        competition_score = (
            (subscriber_count / 1000000 * 40) +
            (video_count / 1000 * 30) +
            (view_velocity / 10000 * 30)
        )
        competition_score = min(competition_score, 100)
        
        results.append({
            'video_id': video['video_id'],
            'title': video['title'],
            'channel': video['channel_title'],
            'channel_subs': subscriber_count,
            'views': video['views'],
            'likes': video['likes'],
            'comments': video['comments'],
            'duration_min': round(duration_minutes, 1),
            'upload_date': upload_date.strftime('%Y-%m-%d'),
            'days_since_upload': days_since_upload,
            'view_velocity': round(view_velocity, 2),
            'engagement_pct': round(engagement, 2),
            'competition_score': round(competition_score, 2),
            'tags': video.get('tags', [])
        })
    
    return results

def cluster_niches(results):
    """Cluster videos into niches based on keywords"""
    for result in results:
        keywords = extract_keywords([result['title']], top_n=2)
        result['main_keyword'] = keywords[0] if keywords else 'unknown'
        result['niche'] = ' '.join(keywords[:2]) if len(keywords) >= 2 else keywords[0] if keywords else 'general'
    
    return results

@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('index.html')

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    """Analyze videos and return results"""
    try:
        if request.method == 'POST':
            urls = (request.json or {}).get('urls', [])
        else:
            with open('seeds.txt', 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        
        video_ids = [extract_video_id(url) for url in urls]
        video_ids = [vid for vid in video_ids if vid]
        
        if not video_ids:
            return jsonify({'error': 'No valid video IDs found'}), 400
        
        youtube = get_youtube_client()
        
        video_data = get_video_details(youtube, video_ids)
        
        channel_ids = list(set([v['channel_id'] for v in video_data]))
        channel_stats = get_channel_stats(youtube, channel_ids)
        
        results = calculate_metrics(video_data, channel_stats)
        
        results = [r for r in results if 10 <= r['duration_min'] <= 30]
        
        results = cluster_niches(results)
        
        for result in results:
            related = get_related_videos(youtube, result['video_id'], max_results=5)
            result['related_videos'] = related
        
        df = pd.DataFrame(results)
        df.to_csv('data/results.csv', index=False)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/related/<video_id>')
def get_related(video_id):
    """Get related videos for a specific video"""
    try:
        youtube = get_youtube_client()
        related = get_related_videos(youtube, video_id, max_results=10)
        return jsonify({'success': True, 'related': related})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export')
def export_csv():
    """Download results as CSV"""
    try:
        return send_file('data/results.csv', as_attachment=True, download_name='youtube_analysis.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
