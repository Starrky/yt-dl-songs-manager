from __future__ import annotations

import concurrent.futures
import json
import logging
import subprocess
import sys
import threading
import signal
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Dict, List, Set

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
)

console = Console()

# -------------------------------------------------------
# Shutdown support
# -------------------------------------------------------

shutdown_requested = False


def signal_handler(sig, frame):
    global shutdown_requested
    shutdown_requested = True
    console.print("\n[yellow]Stopping after current downloads...[/yellow]")


signal.signal(signal.SIGINT, signal_handler)

# -------------------------------------------------------
# Config
# -------------------------------------------------------

CONFIG_FILE = Path("config.json")
PLAYLIST_FILE = Path("playlists.json")

if not CONFIG_FILE.exists():
    console.print("[red]Missing config.json[/red]")
    sys.exit(1)

if not PLAYLIST_FILE.exists():
    console.print("[red]Missing playlists.json[/red]")
    sys.exit(1)

with CONFIG_FILE.open() as f:
    CONFIG = json.load(f)

with PLAYLIST_FILE.open() as f:
    PLAYLISTS = json.load(f)["playlists"]

LIBRARY = Path(CONFIG["library"]).expanduser().resolve()

LIBRARY.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------
# Logging
# -------------------------------------------------------

logging.basicConfig(
    filename=CONFIG.get("log_file", "sync.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

log = logging.getLogger("music_sync")

# -------------------------------------------------------
# Dataclasses
# -------------------------------------------------------

@dataclass
class Playlist:

    name: str
    url: str
    folder: Path


@dataclass
class DownloadJob:

    playlist: Playlist
    video_id: str
    title: str


# -------------------------------------------------------
# Globals
# -------------------------------------------------------

jobs: Queue = Queue()

playlist_objects: List[Playlist] = []

downloaded = 0
skipped = 0
failed = 0

stats_lock = threading.Lock()

existing_songs: Set[str] = set()
existing_songs_lock = threading.Lock()

# -------------------------------------------------------
# Helpers
# -------------------------------------------------------

def run_command(command: List[str]) -> subprocess.CompletedProcess:

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        console.print(
            f"[red]Command not found: {command[0]}[/red]"
        )
        raise


def extract_video_id(filename: str) -> str | None:

    start = filename.rfind("[")
    end = filename.rfind("]")

    if start != -1 and end != -1 and end > start:

        return filename[start + 1:end]

    return None


def scan_existing_songs() -> Set[str]:

    ids = set()

    for playlist in playlist_objects:

        for ext in (
            "*.mp3",
            "*.opus",
            "*.m4a",
            "*.flac",
            "*.ogg",
            "*.wav",
        ):

            for file in playlist.folder.glob(ext):

                video_id = extract_video_id(file.name)

                if video_id:
                    ids.add(video_id)

    return ids


def ensure_folder(folder: Path):

    folder.mkdir(parents=True, exist_ok=True)


def playlist_output_template(folder: Path):

    return str(folder / "%(title)s.%(ext)s")


# -------------------------------------------------------
# Build Playlist objects
# -------------------------------------------------------

for playlist in PLAYLISTS:

    folder = LIBRARY / playlist["name"]

    ensure_folder(folder)

    playlist_objects.append(
        Playlist(
            name=playlist["name"],
            url=playlist["url"],
            folder=folder,
        )
    )

console.print(
    f"[green]Loaded {len(playlist_objects)} playlist(s).[/green]"
)

existing_songs = scan_existing_songs()

console.print(
    f"[green]Found {len(existing_songs)} existing song(s) on disk.[/green]"
)

# -------------------------------------------------------
# Playlist scanning
# -------------------------------------------------------

def fetch_playlist_entries(playlist: Playlist):
    """
    Fetch playlist metadata without downloading anything.

    Returns:
        [
            {
                "id": "...",
                "title": "..."
            }
        ]
    """

    console.print(f"[cyan]Reading playlist:[/cyan] {playlist.name}")

    try:
        result = run_command([
            "yt-dlp",
            "--flat-playlist",
            "--dump-single-json",
            playlist.url,
        ])
    except FileNotFoundError:
        return []

    if result.returncode != 0:

        log.error(result.stderr)

        console.print(
            f"[red]Failed reading playlist {playlist.name}[/red]"
        )

        return []

    try:

        data = json.loads(result.stdout)

    except Exception as e:

        log.exception(e)

        return []

    return data.get("entries", [])


# -------------------------------------------------------
# Queue builder
# -------------------------------------------------------

def queue_playlist(playlist: Playlist):

    global skipped

    entries = fetch_playlist_entries(playlist)

    queued = 0

    for entry in entries:

        if shutdown_requested:
            return

        video_id = entry.get("id")

        if not video_id:
            continue

        # already on disk (in any playlist folder)

        with existing_songs_lock:

            if video_id in existing_songs:

                skipped += 1
                continue

            existing_songs.add(video_id)

        title = entry.get("title") or video_id

        jobs.put(
            DownloadJob(
                playlist=playlist,
                video_id=video_id,
                title=title,
            )
        )

        queued += 1

    console.print(
        f"[green]{playlist.name}[/green] "
        f"Queued {queued} new song(s), "
        f"Skipped {len(entries)-queued}"
    )


# -------------------------------------------------------
# Build global queue
# -------------------------------------------------------

def build_queue():

    console.print()

    console.rule("[bold blue]Scanning playlists")

    #
    # Scan multiple playlists simultaneously.
    #
    # Downloading is handled later.
    #

    workers = min(
        len(playlist_objects),
        max(1, CONFIG.get("parallel_downloads", 8)),
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        executor.map(queue_playlist, playlist_objects)

    console.rule()

    console.print(
        f"[green]Songs to download:[/green] {jobs.qsize()}"
    )

    console.print(
        f"[yellow]Already downloaded:[/yellow] {skipped}"
    )

    console.print()


# -------------------------------------------------------
# Playlist writer
# -------------------------------------------------------

def write_playlist_file(playlist: Playlist):

    if not CONFIG.get("write_m3u", True):
        return

    playlist_file = playlist.folder / f"{playlist.name}.m3u"

    files = []

    #
    # Collect every supported audio file.
    #

    for extension in (
        "*.mp3",
        "*.opus",
        "*.m4a",
        "*.flac",
        "*.ogg",
        "*.wav",
    ):

        files.extend(
            playlist.folder.glob(extension)
        )

    files.sort()

    with playlist_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write("#EXTM3U\n")

        for song in files:

            f.write(song.name + "\n")


# -------------------------------------------------------
# Playlist statistics
# -------------------------------------------------------

def print_summary():

    console.rule("[bold green]Summary")

    console.print(
        f"Queued      : {jobs.qsize()}"
    )

    console.print(
        f"Skipped     : {skipped}"
    )

    console.print(
        f"Downloaded  : {downloaded}"
    )

    console.print(
        f"Failed      : {failed}"
    )

    console.rule()


# -------------------------------------------------------
# Downloader
# -------------------------------------------------------

def download_song(job: DownloadJob) -> bool:

    url = f"https://www.youtube.com/watch?v={job.video_id}"

    output = str(
        job.playlist.folder /
        "%(title)s [%(id)s].%(ext)s"
    )

    command = [
        "yt-dlp",

        url,

        "--extract-audio",

        "--audio-format",
        CONFIG["audio_format"],

        "--audio-quality",
        CONFIG["audio_quality"],

        "--ignore-errors",

        "--retries",
        str(CONFIG.get("retries", 3)),

        "-o",
        output,
    ]

    if CONFIG.get("embed_metadata", True):
        command.append("--embed-metadata")

    if CONFIG.get("embed_thumbnail", True):
        command.append("--embed-thumbnail")

    result = subprocess.run(command)

    return result.returncode == 0


# -------------------------------------------------------
# Worker
# -------------------------------------------------------

def worker(progress, task):

    global downloaded
    global failed

    while not shutdown_requested:

        try:
            job = jobs.get_nowait()

        except Exception:
            return

        ok = False

        #
        # Retry loop
        #

        for _ in range(CONFIG.get("retries", 3)):

            if download_song(job):

                ok = True
                break

        with stats_lock:

            if ok:
                downloaded += 1
                with existing_songs_lock:
                    existing_songs.add(job.video_id)
            else:
                failed += 1

            progress.advance(task)

        jobs.task_done()


# -------------------------------------------------------
# Download everything
# -------------------------------------------------------

def download_all():

    total = jobs.qsize()

    if total == 0:

        console.print(
            "[green]Everything already synchronized.[/green]"
        )

        return

    console.rule("[bold green]Downloading")

    workers = CONFIG.get(
        "parallel_downloads",
        8,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn(
            "[progress.description]{task.description}"
        ),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        task = progress.add_task(
            "Downloading songs",
            total=total,
        )

        threads = []

        for _ in range(workers):

            t = threading.Thread(
                target=worker,
                args=(progress, task),
                daemon=True,
            )

            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    console.rule()

# -------------------------------------------------------
# Verification
# -------------------------------------------------------

def verify():

    console.rule("[bold cyan]Verifying library")

    duplicates = 0
    bad_names = 0

    seen: Dict[str, str] = {}

    for playlist in playlist_objects:

        for ext in (
            "*.mp3",
            "*.opus",
            "*.m4a",
            "*.flac",
            "*.ogg",
            "*.wav",
        ):

            for file in playlist.folder.glob(ext):

                video_id = extract_video_id(file.name)

                if not video_id:

                    bad_names += 1

                    console.print(
                        f"[yellow]{playlist.name}[/yellow] "
                        f"Cannot extract ID from {file.name}"
                    )

                    continue

                if video_id in seen:

                    duplicates += 1

                    console.print(
                        f"[yellow]{playlist.name}[/yellow] "
                        f"Duplicate of {seen[video_id]}: {file.name}"
                    )

                else:

                    seen[video_id] = f"{playlist.name}/{file.name}"

    if duplicates == 0 and bad_names == 0:

        console.print(
            "[green]Library verified successfully.[/green]"
        )

    else:

        console.print(
            f"[red]{duplicates} duplicate(s), "
            f"{bad_names} bad file name(s).[/red]"
        )


# -------------------------------------------------------
# Statistics
# -------------------------------------------------------

def stats():

    console.rule("[bold cyan]Statistics")

    total_files = 0

    for playlist in playlist_objects:

        count = 0

        for ext in (
            "*.mp3",
            "*.m4a",
            "*.opus",
            "*.flac",
            "*.ogg",
        ):

            count += len(
                list(playlist.folder.glob(ext))
            )

        console.print(
            f"{playlist.name:<20} {count}"
        )

        total_files += count

    console.rule()

    console.print(
        f"Total songs: {total_files}"
    )


# -------------------------------------------------------
# Sync
# -------------------------------------------------------

def sync():

    build_queue()

    download_all()

    if CONFIG.get(
        "write_m3u",
        True,
    ):

        console.print()

        console.print(
            "[cyan]Writing playlists...[/cyan]"
        )

        for playlist in playlist_objects:

            write_playlist_file(playlist)

    print_summary()


# -------------------------------------------------------
# CLI
# -------------------------------------------------------

def usage():

    print()

    print("Usage:")

    print("  python music_sync.py sync")
    print("  python music_sync.py verify")
    print("  python music_sync.py stats")

    print()


# -------------------------------------------------------
# Main
# -------------------------------------------------------

def main():

    if len(sys.argv) == 1:

        sync()

        return

    command = sys.argv[1].lower()

    if command == "sync":

        sync()

        return

    if command == "verify":

        verify()

        return

    if command == "stats":

        stats()

        return

    usage()


# -------------------------------------------------------

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        console.print()

        console.print(
            "[yellow]Interrupted.[/yellow]"
        )

        sys.exit(130)

    except Exception as e:

        log.exception(e)

        console.print_exception()

        sys.exit(1)