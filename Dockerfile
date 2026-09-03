FROM fedora:latest

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN dnf -y update && \
    dnf -y install \
        python3 \
        python3-pip \
        ffmpeg \
        git \
        cronie \
        ca-certificates && \
    dnf clean all

# Clone the project
RUN git clone \
    https://github.com/Starrky/yt-dl-songs-manager \
    /home/yt-dl-songs-manager

WORKDIR /home/yt-dl-songs-manager

# Replace desktop config with Docker config/home/yt-dl-songs-manager
RUN rm /home/yt-dl-songs-manager/config.json

RUN mv /home/yt-dl-songs-manager/docker-config.json /home/yt-dl-songs-manager/config.json

# Install Python dependencies
RUN python3 -m pip install --no-cache-dir \
    yt-dlp \
    rich

# Create log directory
RUN mkdir -p /home/yt-dl-songs-manager/log

# Configure cron
RUN printf '%s\n' \
    '0 * * * * cd /home/yt-dl-songs-manager && /usr/bin/python3 sync_music.py sync >> /home/yt-dl-songs-manager/log/sync_cron.log 2>&1' \
    > /etc/cron.d/yt-dl-songs-manager

# Correct permissions
RUN chmod 0644 /etc/cron.d/yt-dl-songs-manager

# Install cron job
RUN crontab /etc/cron.d/yt-dl-songs-manager

# Run cron in foreground
CMD ["/usr/sbin/crond", "-n"]
