import os
import json
import re
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Any, Optional
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import requests
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

CACHE_FILE = 'data/cache.json'

connection_settings_cache: dict[str, Any] = {'data': None, 'expires_at': None}

def get_replit_connector_headers():
    """Get headers for Replit connector API calls"""
    repl_identity = os.getenv('REPL_IDENTITY')
    web_repl_renewal = os.getenv('WEB_REPL_RENEWAL')
    
    x_replit_token = None
    if repl_identity:
        x_replit_token = 'repl ' + repl_identity
    elif web_repl_renewal:
        x_replit_token = 'depl ' + web_repl_renewal
    
    if not x_replit_token:
        raise Exception("Replit environment not configured")
    
    return {
        'Accept': 'application/json',
        'X_REPLIT_TOKEN': x_replit_token
    }

def get_youtube_connection_info():
    """Get YouTube connection info and settings"""
    hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
    if not hostname:
        raise Exception("Replit environment not configured")
    
    headers = get_replit_connector_headers()
    response = requests.get(
        f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=youtube',
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to connect to YouTube connector: HTTP {response.status_code}")
    
    connection_data = response.json()
    if not connection_data.get('items'):
        return None
    
    return connection_data['items'][0]

def get_access_token():
    """Get fresh access token, checking cache first"""
    global connection_settings_cache
    
    if (connection_settings_cache['data'] and 
        connection_settings_cache['expires_at'] and 
        datetime.now(timezone.utc) < connection_settings_cache['expires_at']):
        print("Using cached access token")
        return connection_settings_cache['data'].get('settings', {}).get('access_token')
    
    print("Fetching fresh access token from connector")
    connection_settings = get_youtube_connection_info()
    
    if not connection_settings:
        raise Exception("YouTube not connected. Please set up the YouTube integration.")
    
    settings = connection_settings.get('settings', {})
    access_token = settings.get('access_token')
    
    if not access_token:
        raise Exception("No access token found in connector settings")
    
    expires_at_str = settings.get('expires_at')
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            connection_settings_cache['expires_at'] = expires_at
        except:
            connection_settings_cache['expires_at'] = datetime.now(timezone.utc) + timedelta(hours=1)
    else:
        connection_settings_cache['expires_at'] = datetime.now(timezone.utc) + timedelta(hours=1)
    
    connection_settings_cache['data'] = connection_settings
    
    return access_token

def get_youtube_client():
    """Get authenticated YouTube client using Replit integration
    
    WARNING: Never cache this client.
    Access tokens expire, so a new client must be created each time.
    Always call this function again to get a fresh client.
    """
    try:
        access_token = get_access_token()
        
        print(f"Successfully retrieved access token")
        
        credentials = Credentials(token=access_token)
        
        youtube = build('youtube', 'v3', credentials=credentials)
        print("YouTube client created successfully")
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
    """Fetch video details from YouTube API with efficient batching (1 unit per video)"""
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
            # Batch requests: YouTube API allows up to 50 IDs per request
            # Cost: 1 quota unit per request
            for i in range(0, len(uncached_ids), 50):
                batch = uncached_ids[i:i+50]
                print(f"Fetching details for {len(batch)} videos (1 quota unit)")
                
                response = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch)
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

def get_all_channel_videos(youtube, channel_id, max_videos=50):
    """Fetch all videos from a channel (up to max_videos)"""
    cache = load_cache()
    cache_key = f'channel_videos_{channel_id}_{max_videos}'
    
    if cache_key in cache.get('channel_videos', {}):
        return cache['channel_videos'][cache_key]
    
    video_ids = []
    try:
        next_page_token = None
        while len(video_ids) < max_videos:
            response = youtube.search().list(
                part='id',
                channelId=channel_id,
                type='video',
                order='date',
                maxResults=min(50, max_videos - len(video_ids)),
                pageToken=next_page_token
            ).execute()
            
            for item in response.get('items', []):
                video_ids.append(item['id']['videoId'])
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        if 'channel_videos' not in cache:
            cache['channel_videos'] = {}
        cache['channel_videos'][cache_key] = video_ids
        save_cache(cache)
        
        return video_ids
    except Exception as e:
        print(f"Error fetching channel videos: {e}")
        return []

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
    """Fetch related videos using channel-based search as fallback"""
    cache = load_cache()
    cache_key = f'related_{video_id}_{max_results}'
    
    if cache_key in cache.get('related', {}):
        return cache['related'][cache_key]
    
    try:
        video_info = cache.get('videos', {}).get(video_id)
        if not video_info:
            video_data = get_video_details(youtube, [video_id])
            if video_data:
                video_info = video_data[0]
        
        if not video_info:
            return []
        
        keywords = extract_keywords([video_info['title']], top_n=3)
        search_query = ' '.join(keywords[:2]) if len(keywords) >= 2 else keywords[0] if keywords else video_info['title'][:50]
        
        response = youtube.search().list(
            part='snippet',
            q=search_query,
            type='video',
            maxResults=max_results + 5,
            order='viewCount'
        ).execute()
        
        related = []
        for item in response.get('items', []):
            if item['id']['videoId'] != video_id and len(related) < max_results:
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
            'channel_id': video['channel_id'],
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

def identify_niche_competitors(all_results):
    """Identify top-performing competitors in each niche"""
    niche_data = {}
    
    for result in all_results:
        niche = result.get('niche', 'general')
        if niche not in niche_data:
            niche_data[niche] = {
                'channels': {},
                'total_videos': 0,
                'avg_engagement': 0,
                'avg_competition': 0
            }
        
        channel = result['channel']
        if channel not in niche_data[niche]['channels']:
            niche_data[niche]['channels'][channel] = {
                'channel': channel,
                'channel_id': result['channel_id'],
                'channel_subs': result['channel_subs'],
                'video_count': 0,
                'total_views': 0,
                'total_engagement': 0,
                'avg_engagement': 0,
                'competition_score': result['competition_score'],
                'videos': []
            }
        
        channel_data = niche_data[niche]['channels'][channel]
        channel_data['video_count'] += 1
        channel_data['total_views'] += result['views']
        channel_data['total_engagement'] += result['engagement_pct']
        channel_data['videos'].append({
            'title': result['title'],
            'video_id': result['video_id'],
            'views': result['views'],
            'engagement_pct': result['engagement_pct']
        })
        
        niche_data[niche]['total_videos'] += 1
    
    for niche, data in niche_data.items():
        engagement_sum = 0
        competition_sum = 0
        
        for channel, channel_data in data['channels'].items():
            channel_data['avg_engagement'] = channel_data['total_engagement'] / channel_data['video_count']
            engagement_sum += channel_data['avg_engagement']
            competition_sum += channel_data['competition_score']
            
            channel_data['videos'] = sorted(
                channel_data['videos'], 
                key=lambda x: x['views'], 
                reverse=True
            )[:5]
        
        data['avg_engagement'] = engagement_sum / len(data['channels']) if data['channels'] else 0
        data['avg_competition'] = competition_sum / len(data['channels']) if data['channels'] else 0
        
        data['top_competitors'] = sorted(
            data['channels'].values(),
            key=lambda x: (x['avg_engagement'], -x['competition_score']),
            reverse=True
        )[:10]
    
    return niche_data

def automated_search(youtube, keyword, video_duration='short', max_results=20):
    """Search YouTube for videos by keyword with duration filter
    COST: 100 quota units per search API call
    Default max_results=20 to minimize quota usage (fits in 1 call)
    """
    from googleapiclient.errors import HttpError
    
    cache = load_cache()
    cache_key = f'search_{keyword}_{video_duration}_{max_results}'
    
    # Check cache first - saves 100 units!
    if cache_key in cache.get('searches', {}):
        print(f"Using cached search results for '{keyword}' (saved 100 quota units)")
        return cache['searches'][cache_key]
    
    try:
        video_ids = []
        next_page_token = None
        api_calls = 0
        
        while len(video_ids) < max_results:
            api_calls += 1
            batch_size = min(50, max_results - len(video_ids))
            print(f"Search API call #{api_calls} for '{keyword}' - fetching {batch_size} results (100 quota units)")
            
            response = youtube.search().list(
                part='id',
                q=keyword,
                type='video',
                videoDuration=video_duration,
                maxResults=batch_size,
                order='viewCount',
                pageToken=next_page_token
            ).execute()
            
            for item in response.get('items', []):
                if 'videoId' in item['id']:
                    video_ids.append(item['id']['videoId'])
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token or len(video_ids) >= max_results:
                break
        
        print(f"Search complete: Found {len(video_ids)} videos using {api_calls * 100} quota units")
        
        if 'searches' not in cache:
            cache['searches'] = {}
        cache['searches'][cache_key] = video_ids
        save_cache(cache)
        
        return video_ids
    except HttpError as e:
        error_message = str(e)
        print(f"Error in automated search: {error_message}")
        if 'quotaExceeded' in error_message or '403' in str(e.resp.status):
            raise Exception("QUOTA_EXCEEDED")
        raise e
    except Exception as e:
        print(f"Error in automated search: {e}")
        raise e

def filter_by_channel_age(channel_data, max_age_days=None):
    """Filter channels by age"""
    if max_age_days is None:
        return True
    
    published_at = channel_data.get('published_at')
    if not published_at:
        return True
    
    try:
        channel_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        days_old = (datetime.now(channel_date.tzinfo) - channel_date).days
        return days_old <= max_age_days
    except:
        return True

def get_channel_details(youtube, channel_ids):
    """Fetch channel details including creation date with efficient batching (1 unit per 50 channels)"""
    cache = load_cache()
    results = {}
    uncached_ids = []
    
    for channel_id in channel_ids:
        cache_key = f'channel_details_{channel_id}'
        if cache_key in cache.get('channel_details', {}):
            results[channel_id] = cache['channel_details'][cache_key]
        else:
            uncached_ids.append(channel_id)
    
    if uncached_ids:
        try:
            # Batch requests: up to 50 channel IDs per request
            # Cost: 1 quota unit per request
            for i in range(0, len(uncached_ids), 50):
                batch = uncached_ids[i:i+50]
                print(f"Fetching details for {len(batch)} channels (1 quota unit)")
                
                response = youtube.channels().list(
                    part='snippet,statistics',
                    id=','.join(batch)
                ).execute()
                
                for item in response.get('items', []):
                    channel_data = {
                        'channel_id': item['id'],
                        'title': item['snippet']['title'],
                        'published_at': item['snippet']['publishedAt'],
                        'subscriber_count': int(item['statistics'].get('subscriberCount', 0)),
                        'video_count': int(item['statistics'].get('videoCount', 0)),
                        'view_count': int(item['statistics'].get('viewCount', 0))
                    }
                    results[item['id']] = channel_data
                    
                    if 'channel_details' not in cache:
                        cache['channel_details'] = {}
                    cache['channel_details'][f'channel_details_{item["id"]}'] = channel_data
            
            save_cache(cache)
        except Exception as e:
            print(f"Error fetching channel details: {e}")
    
    return results

def calculate_potential_score(video_data, channel_data):
    """Calculate potential score for videos (high views, low subs = high potential)"""
    views = video_data.get('views', 0)
    subs = channel_data.get('subscriber_count', 1)
    
    if subs == 0:
        subs = 1
    
    view_to_sub_ratio = views / subs if subs > 0 else 0
    
    base_score = min(view_to_sub_ratio * 100, 100)
    
    if subs < 10000:
        base_score *= 1.5
    elif subs < 50000:
        base_score *= 1.2
    
    return min(base_score, 100)

@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_niche():
    """Automated search for videos by keyword with filters"""
    try:
        data = request.json or {}
        keyword = data.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        
        video_duration = data.get('video_duration', 'short')
        min_subs = data.get('min_subs', 0)
        max_subs = data.get('max_subs', 1000000)
        min_views = data.get('min_views', 0)
        max_views = data.get('max_views', 999999999)
        max_channel_age_days = data.get('max_channel_age_days')
        max_results = min(data.get('max_results', 20), 100)  # Default 20 for efficiency
        
        youtube = get_youtube_client()
        
        print(f"Searching for '{keyword}' with duration={video_duration}, max_results={max_results}")
        video_ids = automated_search(youtube, keyword, video_duration, max_results)
        
        if not video_ids:
            return jsonify({'error': 'No videos found for this search'}), 404
        
        print(f"Found {len(video_ids)} videos, fetching details...")
        video_data = get_video_details(youtube, video_ids)
        
        channel_ids = list(set([v['channel_id'] for v in video_data]))
        print(f"Fetching details for {len(channel_ids)} channels...")
        channel_details = get_channel_details(youtube, channel_ids)
        
        filtered_results = []
        for video in video_data:
            channel_id = video['channel_id']
            channel_info = channel_details.get(channel_id, {})
            
            subs = channel_info.get('subscriber_count', 0)
            views = video.get('views', 0)
            
            if not (min_subs <= subs <= max_subs):
                continue
            if not (min_views <= views <= max_views):
                continue
            
            if max_channel_age_days and not filter_by_channel_age(channel_info, max_channel_age_days):
                continue
            
            filtered_results.append({
                'video': video,
                'channel': channel_info
            })
        
        print(f"After filtering: {len(filtered_results)} videos match criteria")
        
        if not filtered_results:
            return jsonify({'error': 'No videos match your filter criteria'}), 404
        
        channel_stats = {ch_id: {'subscriber_count': ch['subscriber_count'], 'video_count': ch['video_count']} 
                        for ch_id, ch in channel_details.items()}
        
        results = calculate_metrics([item['video'] for item in filtered_results], channel_stats)
        results = cluster_niches(results)
        
        for i, result in enumerate(results):
            channel_info = filtered_results[i]['channel']
            result['potential_score'] = round(calculate_potential_score(filtered_results[i]['video'], channel_info), 2)
            result['channel_age_days'] = (datetime.now(datetime.fromisoformat(channel_info['published_at'].replace('Z', '+00:00')).tzinfo) - 
                                         datetime.fromisoformat(channel_info['published_at'].replace('Z', '+00:00'))).days if channel_info.get('published_at') else None
        
        results = sorted(results, key=lambda x: x['potential_score'], reverse=True)
        
        seed_df = pd.DataFrame(results)
        seed_df.to_csv('data/search_results.csv', index=False)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'search_params': {
                'keyword': keyword,
                'video_duration': video_duration,
                'subs_range': f'{min_subs:,} - {max_subs:,}',
                'views_range': f'{min_views:,} - {max_views:,}',
                'max_channel_age_days': max_channel_age_days
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        error_msg = str(e)
        if 'QUOTA_EXCEEDED' in error_msg:
            return jsonify({
                'error': 'YouTube API Quota Exceeded',
                'details': 'Your YouTube API quota has been exceeded. YouTube API has a daily limit of 10,000 units per day. Please try again tomorrow or increase your quota in the Google Cloud Console.',
                'help_link': 'https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas'
            }), 429
        
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    """Analyze videos and return results with channel-wide analysis"""
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
        
        all_channel_videos = []
        print(f"Fetching all videos from {len(channel_ids)} channels...")
        
        for channel_id in channel_ids:
            channel_video_ids = get_all_channel_videos(youtube, channel_id, max_videos=50)
            if channel_video_ids:
                channel_video_data = get_video_details(youtube, channel_video_ids)
                channel_results = calculate_metrics(channel_video_data, channel_stats)
                channel_results = [r for r in channel_results if 10 <= r['duration_min'] <= 30]
                channel_results = cluster_niches(channel_results)
                all_channel_videos.extend(channel_results)
        
        print(f"Analyzed {len(all_channel_videos)} total videos from all channels")
        
        niche_competitors = identify_niche_competitors(all_channel_videos)
        
        all_videos_df = pd.DataFrame(all_channel_videos) if all_channel_videos else pd.DataFrame()
        if not all_videos_df.empty:
            all_videos_df.to_csv('data/all_channel_videos.csv', index=False)
        
        niche_summary = []
        for niche, data in niche_competitors.items():
            niche_summary.append({
                'niche': niche,
                'total_videos': data['total_videos'],
                'total_channels': len(data['channels']),
                'avg_engagement': round(data['avg_engagement'], 2),
                'avg_competition': round(data['avg_competition'], 2),
                'top_competitors': data['top_competitors'][:5]
            })
        
        niche_summary = sorted(niche_summary, key=lambda x: (-x['avg_engagement'], x['avg_competition']))
        
        niche_df = pd.DataFrame(niche_summary)
        if not niche_df.empty:
            niche_df.to_csv('data/niche_competitors.csv', index=False)
        
        seed_df = pd.DataFrame(results)
        seed_df.to_csv('data/results.csv', index=False)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'niche_analysis': niche_summary,
            'total_channel_videos': len(all_channel_videos)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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

@app.route('/export/niches')
def export_niches_csv():
    """Download niche competitor analysis as CSV"""
    try:
        return send_file('data/niche_competitors.csv', as_attachment=True, download_name='niche_competitors.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/export/all_videos')
def export_all_videos_csv():
    """Download all channel videos as CSV"""
    try:
        return send_file('data/all_channel_videos.csv', as_attachment=True, download_name='all_channel_videos.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/account/info')
def get_account_info():
    """Get current YouTube account connection status"""
    try:
        connection_info = get_youtube_connection_info()
        
        if not connection_info:
            return jsonify({
                'success': False,
                'connected': False,
                'error': 'No YouTube connection found'
            }), 404
        
        status = connection_info.get('status', 'unknown')
        
        if status not in ['connected', 'healthy']:
            return jsonify({
                'success': False,
                'connected': False,
                'error': f'YouTube connection status: {status}'
            }), 404
        
        try:
            youtube = get_youtube_client()
            
            response = youtube.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if response.get('items'):
                channel = response['items'][0]
                subscriber_count = channel['statistics'].get('subscriberCount', 'Hidden')
                if subscriber_count != 'Hidden':
                    subscriber_count = int(subscriber_count)
                    if subscriber_count >= 1000000:
                        subscriber_count = f'{subscriber_count/1000000:.1f}M'
                    elif subscriber_count >= 1000:
                        subscriber_count = f'{subscriber_count/1000:.1f}K'
                    else:
                        subscriber_count = str(subscriber_count)
                
                return jsonify({
                    'success': True,
                    'connected': True,
                    'account': {
                        'channel_name': channel['snippet']['title'],
                        'channel_id': channel['id'],
                        'subscriber_count': subscriber_count,
                        'thumbnail': channel['snippet']['thumbnails'].get('default', {}).get('url', '')
                    }
                })
        except Exception as api_error:
            error_str = str(api_error)
            print(f"Error getting account info: {api_error}")
            if 'quotaExceeded' in error_str or '403' in error_str:
                return jsonify({
                    'success': True,
                    'connected': True,
                    'quota_exceeded': True,
                    'account': {
                        'channel_name': 'YouTube Connected',
                        'channel_id': None,
                        'subscriber_count': 'Quota exceeded',
                        'thumbnail': ''
                    }
                })
        
        return jsonify({
            'success': True,
            'connected': True,
            'account': {
                'channel_name': 'YouTube Connected',
                'channel_id': None,
                'subscriber_count': status,
                'thumbnail': ''
            }
        })
    except Exception as e:
        print(f"Error in get_account_info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'connected': False,
            'error': str(e)
        }), 500

@app.route('/api/account/disconnect', methods=['POST'])
def disconnect_account():
    """Disconnect YouTube account to allow reconnection with different account"""
    try:
        global connection_settings_cache
        
        hostname = os.getenv('REPLIT_CONNECTORS_HOSTNAME')
        if not hostname:
            return jsonify({'error': 'Replit environment not configured'}), 500
        
        connection_info = get_youtube_connection_info()
        if not connection_info:
            return jsonify({'error': 'No YouTube connection found'}), 404
        
        connection_id = connection_info.get('id')
        if not connection_id:
            return jsonify({'error': 'Connection ID not found'}), 500
        
        headers = get_replit_connector_headers()
        
        delete_response = requests.delete(
            f'https://{hostname}/api/v2/connection/{connection_id}',
            headers=headers
        )
        
        if delete_response.status_code in [200, 204]:
            connection_settings_cache = {'data': None, 'expires_at': None}
            
            return jsonify({
                'success': True,
                'message': 'YouTube account disconnected successfully. You will be prompted to reconnect on the next search.'
            })
        else:
            return jsonify({
                'error': f'Failed to disconnect: HTTP {delete_response.status_code}'
            }), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
