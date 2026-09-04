#!/bin/bash
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
cd /home/yt-dl-songs-manager || exit 1
/usr/bin/python3 sync_music.py sync