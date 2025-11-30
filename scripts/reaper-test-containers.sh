#!/bin/bash
# scripts/reaper-test-containers.sh
# Kill orphaned test Qdrant containers
#
# Usage: ./scripts/reaper-test-containers.sh
#
# Add to crontab for automatic cleanup:
#   */5 * * * * /path/to/reaper-test-containers.sh
#
# Or add to launchd on macOS for more reliable scheduling.

MAX_AGE_MINUTES=10
CONTAINER_PREFIX="qdrant-test"

echo "=== Test Container Reaper ==="
echo "Looking for containers older than $MAX_AGE_MINUTES minutes..."

# Find containers matching prefix that are older than MAX_AGE
docker ps \
    --filter "name=${CONTAINER_PREFIX}" \
    --format "{{.Names}}\t{{.RunningFor}}" | \
while read name age; do
    # Skip empty lines
    [ -z "$name" ] && continue

    # Parse age (e.g., "15 minutes ago", "2 hours ago")
    if echo "$age" | grep -qE "([0-9]+) minutes"; then
        minutes=$(echo "$age" | grep -oE "[0-9]+" | head -1)
        if [ "$minutes" -gt "$MAX_AGE_MINUTES" ]; then
            echo "Reaping $name (running for $age)"
            docker rm -f "$name" 2>/dev/null
        else
            echo "Keeping $name (running for $age)"
        fi
    elif echo "$age" | grep -qE "(hour|day)"; then
        # Anything in hours or days is definitely stale
        echo "Reaping $name (running for $age)"
        docker rm -f "$name" 2>/dev/null
    elif echo "$age" | grep -qE "([0-9]+) seconds"; then
        echo "Keeping $name (running for $age)"
    else
        echo "Keeping $name (running for $age - unrecognized format)"
    fi
done

echo "Done."
