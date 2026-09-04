# yt-dl-songs-manager
Simple wrapper built on yt-dl that downloads songs and creates playlists from them. I also use it in cron to keep local music updated.



````md
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
````

Install FFmpeg using your package manager.

## Fedora

```bash
sudo dnf install ffmpeg
```

## Ubuntu

```bash
sudo apt install ffmpeg
```

## Arch Linux

```bash
sudo pacman -S ffmpeg
```

---

# Folder Structure

```
music-sync/
│
├── music_sync.py
├── config.json
├── playlists.json
├── sync.log
└── Music/
```

---

# Configuration

Example `config.json`

```json
{
    "library": "~/Music/YouTube",
    "audio_format": "mp3",
    "audio_quality": "0",
    "parallel_downloads": 8,
    "embed_metadata": true,
    "embed_thumbnail": true,
    "retries": 3,
    "write_m3u": true,
    "log_file": "sync.log"
}
```

## Options

| Option             | Description              |
| ------------------ | ------------------------ |
| library            | Output directory         |
| audio_format       | mp3, opus, m4a, flac...  |
| audio_quality      | yt-dlp audio quality     |
| parallel_downloads | Number of worker threads |
| embed_metadata     | Embed ID3 metadata       |
| embed_thumbnail    | Embed album artwork      |
| retries            | Retry failed downloads   |
| write_m3u          | Generate playlist files  |
| log_file           | Log filename             |

---

# Playlists

Example `playlists.json`

```json
{
    "playlists": [
        {
            "name": "Rock",
            "url": "https://youtube.com/playlist?list=XXXXXXXX"
        },
        {
            "name": "Synthwave",
            "url": "https://youtube.com/playlist?list=YYYYYYYY"
        }
    ]
}
```

Each playlist receives its own folder:

```
Music/
├── Rock/
│   ├── Song A [VIDEOID].mp3
│   ├── Song B [VIDEOID].mp3
│   ├── Rock.m3u
│   └── .downloaded
│
└── Synthwave/
```

---

# Commands

Synchronize library

```bash
python music_sync.py sync
```

Verify downloaded files

```bash
python music_sync.py verify
```

Display statistics

```bash
python music_sync.py stats
```

Running without arguments defaults to:

```bash
python music_sync.py
```

which performs a synchronization.

---

# How It Works

1. Reads every configured playlist.
2. Fetches playlist metadata without downloading.
3. Reads the local download archive.
4. Skips songs already downloaded.
5. Creates a download queue.
6. Starts worker threads.
7. Downloads only missing songs.
8. Updates the archive.
9. Generates `.m3u` playlist files.

---

# Download Archive

Music Sync uses yt-dlp's download archive to remember previously downloaded videos.

This allows future synchronizations to skip existing songs without repeatedly checking every file.

Archive example:

```
youtube dQw4w9WgXcQ
youtube xxxxxxxxxxx
youtube yyyyyyyyyyy
```

---

# Parallel Downloads

Unlike downloading an entire playlist sequentially, Music Sync creates one job per missing song.

Each worker thread launches a `yt-dlp` process for its assigned song.

This greatly improves synchronization speed, especially for large playlists.

---

# Progress

During synchronization you'll see a live progress bar showing:

* Remaining songs
* Percentage complete
* Estimated remaining time

---

# Logging

Every synchronization is logged.

Example:

```
2026-08-01 19:43:11 INFO Downloaded:
Never Gonna Give You Up

2026-08-01 19:43:17 INFO Finished playlist Rock
```

---

# Cron

Example: synchronize every night at 2 AM

```cron
0 * * * * cd /home/kuba/Code/Python/yt-dl-songs-manager && /usr/bin/python3 sync_music.py sync >> /home/kuba/Code/Python/yt-dl-songs-manager/log/sync_cron.log 2>&1
```

---
# Docker

Get Dockerfile then:
```docker build --no-cache -t yt-dl-songs-manager .```
then when creating container set:

Volumes:

host path : <your path on pc> e.g.  ```D:\Download\```

container path: ```/mnt/Downloads```

---

# Verification

Verification scans every configured playlist folder and ensures files referenced by the archive still exist.

Useful after:

* Disk failures
* Manual file deletion
* Moving files
* Restoring backups

---

# Statistics

Shows the number of downloaded songs per playlist and the total library size.

Example:

```
Rock                 843
Synthwave            291
Jazz                 134

Total songs: 1268
```

---

# Future Improvements

Possible future features include:

* SQLite database
* SponsorBlock support
* Automatic yt-dlp updates
* Discord notifications
* Desktop notifications
* Duplicate detection
* FLAC support
* Playlist rename detection
* Smart cleanup of removed songs
* Web interface
* Jellyfin/Navidrome integration
* Automatic archive repair
* Batch downloads per worker
* Scheduled synchronization from within the application

---

# License

Use at your own risk.

This project is intended for synchronizing playlists you are authorized to download. Ensure your usage complies with YouTube's Terms of Service and applicable copyright laws in your jurisdiction.

```
```
