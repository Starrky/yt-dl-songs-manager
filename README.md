# Music Sync

A lightweight Python tool for keeping a local music library synchronized with one or more YouTube playlists.

Instead of downloading entire playlists every time, Music Sync:

- Downloads **only new songs**
- Skips songs already downloaded
- Downloads multiple songs in parallel
- Automatically generates `.m3u` playlists
- Is designed to be run manually or from `cron`

---

# Features

- Multiple playlists
- Parallel downloads
- Progress bar using `rich`
- Uses `yt-dlp`
- Downloads best available audio
- Converts audio to MP3 (or another configured format)
- Embeds metadata
- Embeds thumbnails
- Retry support
- Playlist verification
- Statistics command
- Graceful Ctrl+C handling
- Cron friendly

---

# Requirements

- Python 3.10+
- FFmpeg
- yt-dlp

Install Python dependencies:

```bash
pip install yt-dlp rich
