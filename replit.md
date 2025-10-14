# YouTube Niche Analysis Dashboard

## Overview
A comprehensive Flask-based web application that analyzes YouTube videos to identify high-engagement, low-competition niches. The application fetches video statistics via YouTube Data API v3, calculates engagement metrics, competition scores, and displays results in an interactive sortable dashboard.

**Status**: ✅ Fully Functional  
**Last Updated**: October 14, 2025

## Features
- 🔐 **Secure Authentication**: Uses Replit YouTube connector for OAuth-based API authentication
- 📊 **Comprehensive Analytics**: Fetches video stats (views, likes, comments, duration, upload date)
- 🎯 **Niche Identification**: Clusters videos by keywords and identifies low-competition opportunities
- 📈 **Engagement Metrics**: Calculates engagement percentage, view velocity, and competition scores
- 🔍 **Related Videos**: Discovers top competitor videos for each analyzed video
- 🏆 **Channel-Wide Analysis**: Analyzes ALL videos from each discovered channel (up to 50 per channel)
- 🎭 **Niche Competitor Analysis**: Identifies top-performing competitors in each niche with detailed stats
- 💾 **API Quota Preservation**: Caches API responses locally to minimize quota usage
- 📥 **Multiple CSV Exports**: Download seed videos, niche analysis, or all channel videos separately
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

### 1. Run Analysis
1. Open the dashboard (automatically loads at http://localhost:5000)
2. Leave the text area empty to analyze the default 13 seed videos, OR
3. Paste custom YouTube video URLs (one per line)
4. Click "Run Analysis"

### 2. View Results
The analysis displays:
- **Green rows**: High engagement videos (>3% engagement rate)
- **Blue rows**: Low competition niches (<40 competition score)
- **Purple gradient**: Videos with both high engagement AND low competition

### 3. View Niche Competitor Analysis
After analysis completes, scroll down to see:
- Breakdown of videos by niche
- Top 5 performing competitors in each niche
- Channel stats including avg engagement and competition scores
- Top 3 videos from each competitor channel

### 4. Export Data
Click "Export Data ▼" and choose from:
- **Seed Videos CSV**: Original analyzed videos
- **Niche Analysis CSV**: Competitor breakdown by niche
- **All Videos CSV**: All videos from all discovered channels

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

### Niche Clustering
Videos are grouped by extracting main keywords from titles, filtering stop words, and identifying common themes.

## API Endpoints

### `GET /` or `POST /`
Main dashboard page

### `GET /analyze`
Analyzes default seed videos from seeds.txt

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
