#!/bin/bash
set -e

# If the historical data directory is a bind-mount from the host, its owner
# may not match the 'app' user inside the container. Fix permissions before
# dropping to the unprivileged user.
DATA_DIR="${BACKEND_HISTORICAL_DIR:-/data/historical}"
if [ -d "$DATA_DIR" ]; then
    if [ "$(id -u)" = "0" ]; then
        # Running as root (e.g. in docker-compose without user: override).
        # Make the directory writable by the app group.
        chown -R app:app "$DATA_DIR" 2>/dev/null || chmod -R 777 "$DATA_DIR" 2>/dev/null || true
        exec gosu app "$@"
    fi
fi

exec "$@"
