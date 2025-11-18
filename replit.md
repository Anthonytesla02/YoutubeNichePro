# YouTube Niche Analysis Dashboard

## Overview
A comprehensive Flask-based web application that analyzes YouTube videos to identify high-engagement, low-competition niches. The application fetches video statistics via YouTube Data API v3, calculates engagement metrics, competition scores, and displays results in an interactive sortable dashboard.

**Status**: ✅ Fully Functional  
**Last Updated**: November 18, 2025

## Features
- 🔐 **Secure Authentication**: Uses Replit YouTube connector for OAuth-based API authentication
- 🤖 **Automated Niche Discovery**: Search YouTube by keyword/niche with advanced filtering - no manual URL input needed!
- 🎯 **Smart Filtering System**: Filter by video length (shorts/medium/long), subscriber range, view count, and channel age
- 🏅 **Potential Score Algorithm**: Identifies high-opportunity channels (high views but low subscribers)
- 📊 **Comprehensive Analytics**: Fetches video stats (views, likes, comments, duration, upload date, channel age)
- 📈 **Engagement Metrics**: Calculates engagement percentage, view velocity, and competition scores
- 🔍 **Channel Discovery**: Find smaller channels (e.g., <100k subs) with high engagement and viral potential
- 🏆 **Channel-Wide Analysis**: Analyzes ALL videos from each discovered channel (up to 50 per channel)
- 🎭 **Niche Competitor Analysis**: Identifies top-performing competitors in each niche with detailed stats
- 💾 **API Quota Preservation**: Caches API responses locally to minimize quota usage
- 📥 **CSV Export**: Download search results as CSV for further analysis
- 🎨 **Interactive UI**: Clean dashboard with DataTables, sorting, search, and visual indicators

## Project Structure
```
.
├── app.py                  # Main Flask application with YouTube API integration
├── templates/
│   └── index.html         # Frontend dashboard with DataTables
├── static/
│   └── style.css          # Custom styling
├── data/
│   ├── cache.json         # API response cache (auto-generated)
│   └── results.csv        # Analysis results (auto-generated)
├── seeds.txt              # Default video URLs for analysis
├── .env.example           # Environment variable template
└── .gitignore            # Git ignore configuration

```

## Technology Stack
**Backend:**
- Python 3.11
- Flask (web framework)
- google-api-python-client (YouTube API v3)
- pandas (data analysis)
- python-dateutil (date handling)
- requests (HTTP client)

**Frontend:**
- Tailwind CSS (styling)
- jQuery + DataTables.js (interactive tables)
- Vanilla JavaScript (UI logic)

**Integration:**
- Replit YouTube Connector (OAuth authentication)

## Authentication Methods

### Primary: Replit YouTube Connector (Recommended)
The application uses the Replit YouTube connector which handles OAuth authentication automatically. The connector:
- Manages access tokens and refresh tokens
- Handles token expiration and renewal
- Provides secure credential storage

### Fallback: Manual API Key
If the connector isn't available, set `YOUTUBE_API_KEY` in your environment variables.

## How to Use

### 1. Automated Search (Primary Method)
1. Open the dashboard (automatically loads at http://localhost:5000)
2. Enter a keyword or niche (e.g., "cooking tips", "fitness", "tech reviews")
3. Configure your filters:
   - **Video Length**: Choose Shorts (<4 min), Medium (4-20 min), Long (>20 min), or Any
   - **Subscriber Range**: Set min/max to find smaller channels (default: 0-100k)
   - **View Range**: Filter by video views (optional)
   - **Max Channel Age**: Find newer channels (e.g., 365 days for 1 year old)
   - **Max Results**: Number of videos to analyze (25-100)
4. Click "🔍 Search for High-Potential Videos"

### 2. View Results
The analysis displays videos sorted by **Potential Score** (high views + low subs = high opportunity):
- **Green highlights**: Videos with 75+ potential score (excellent opportunities)
- **Blue highlights**: Videos with 50-75 potential score (good opportunities)
- **Channel Age**: Shows how old each channel is in days
- Filter, sort, and search using the interactive table

### 3. Understanding Metrics
- **Potential Score**: View-to-subscriber ratio - higher means more viral potential with less competition
- **Engagement %**: (Likes + Comments) / Views × 100 - above 3% is excellent
- **Competition Score**: Market saturation - below 40 indicates easier niches
- **View Velocity**: Views per day - shows content momentum

### 4. Export Data
Click "Export Data ▼" to download search results as CSV for further analysis

## Metrics Explained

### Engagement Percentage
```
Engagement % = (Likes + Comments) / Views × 100
```
Higher is better. >3% indicates strong audience engagement.

### View Velocity
```
View Velocity = Total Views / Days Since Upload
```
Measures how quickly a video gains views. Higher values indicate viral or trending content.

### Competition Score
```
Competition = (Channel Subs/1M × 40) + (Video Count/1K × 30) + (View Velocity/10K × 30)
```
Weighted score (0-100) where:
- Lower scores (<40) indicate easier niches to compete in
- Higher scores suggest saturated markets

### Potential Score
```
Potential Score = (Views / Subscribers) × 100 × Multiplier
```
Multiplier increases for channels with fewer subscribers:
- Channels <10k subs: 1.5x multiplier
- Channels 10k-50k subs: 1.2x multiplier
- Channels >50k subs: 1.0x multiplier

Higher scores (75+) indicate videos with exceptional viral potential relative to channel size - perfect opportunities for entering a niche.

### Niche Clustering
Videos are grouped by extracting main keywords from titles, filtering stop words, and identifying common themes.

## API Endpoints

### `GET /`
Main dashboard page with automated search interface

### `POST /search`
Automated YouTube search with advanced filters
```json
{
  "keyword": "cooking tips",
  "video_duration": "short",
  "min_subs": 0,
  "max_subs": 100000,
  "min_views": 0,
  "max_views": 999999999,
  "max_channel_age_days": 365,
  "max_results": 50
}
```

### `GET /analyze`
Legacy endpoint - analyzes default seed videos from seeds.txt

### `POST /analyze`
Analyzes custom video URLs
```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2"
  ]
}
```

### `GET /related/<video_id>`
Fetches top 5-10 related videos for a specific video

### `GET /export`
Downloads seed video analysis results as CSV file

### `GET /export/niches`
Downloads niche competitor analysis as CSV file

### `GET /export/all_videos`
Downloads all channel videos analysis as CSV file

## Caching System
API responses are cached in `data/cache.json` with the following structure:
```json
{
  "videos": {
    "VIDEO_ID": { /* video details */ }
  },
  "channels": {
    "CHANNEL_ID": { /* channel stats */ }
  },
  "related": {
    "related_VIDEO_ID": [ /* related videos */ ]
  }
}
```

This reduces API quota consumption by avoiding duplicate requests.

## Development

### Local Setup
1. Ensure Python 3.11 is installed
2. Dependencies are auto-installed via Replit packager
3. Set up YouTube connector via Replit integrations
4. Run `python app.py`

### Environment Variables
```bash
# Optional: Fallback API key
YOUTUBE_API_KEY=your_youtube_api_key

# Flask configuration (auto-generated)
SECRET_KEY=your_secret_key
FLASK_ENV=development
```

### Adding New Video URLs
Edit `seeds.txt` and add YouTube URLs (one per line):
```
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
```

## Troubleshooting

### "YouTube not connected" Error
- Ensure the Replit YouTube connector is set up
- Check that OAuth permissions are granted
- Verify REPLIT_CONNECTORS_HOSTNAME is available

### API Quota Exceeded
- The app uses caching to minimize API calls
- Delete `data/cache.json` only if you need fresh data
- Consider spreading analysis across multiple days

### Videos Not Showing
- Only videos between 10-30 minutes are displayed (filter applied)
- Check that video IDs are correctly extracted from URLs
- Verify videos are public and accessible

## Recent Changes
- **Nov 18, 2025 (v3.0)**: Automated niche discovery with advanced filtering
  - Replaced manual URL input with keyword-based automated search
  - Implemented YouTube search API integration with video duration filtering
  - Added smart filtering: subscriber range, view range, channel age
  - Created Potential Score algorithm to identify high-opportunity channels (high views/low subs)
  - Added channel age tracking and display
  - Updated UI with comprehensive filter controls and search parameters display
  - Results now sorted by Potential Score (best opportunities first)
  - Enhanced table with color-coded potential scores (green=excellent, blue=good)
  - Updated caching system for search results and channel details

- **Oct 14, 2025 (v2.0)**: Channel-wide analysis and niche competitor feature
  - Added channel-wide video analysis (up to 50 videos per channel)
  - Implemented niche competitor identification and ranking
  - Created interactive niche breakdown UI with top performers
  - Added multiple CSV export options (seed videos, niche analysis, all videos)
  - Fixed related videos search using keyword-based approach
  - Enhanced caching for channel video lists

- **Oct 14, 2025 (v1.0)**: Initial implementation
  - YouTube OAuth integration via Replit connector
  - Full analytics pipeline with caching
  - Interactive dashboard with DataTables
  - CSV export functionality
  - Token expiry handling for proactive refresh

## User Preferences
None specified yet.

## Next Steps (Future Enhancements)
1. Batch URL upload via file import
2. Advanced TF-IDF-based niche clustering
3. Trend analysis over time periods
4. Competitive landscape visualization (charts/graphs)
5. Saved analysis sessions with comparison features
6. Email reports for niche opportunities
