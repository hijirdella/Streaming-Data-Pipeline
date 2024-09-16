#!/bin/bash
if [[   $(docker ps --filter name=streaming* -aq) ]]; then
    echo 'Stopping Container...'
    docker ps --filter name=streaming* -aq | xargs docker stop
    echo 'All Container Stopped...'
    echo 'Removing Container...'
    docker ps --filter name=streaming* -aq | xargs docker rm
    echo 'All Container Removed...'
    docker network inspect streaming-network >/dev/null 2>&1
else
    echo "All Cleaned UP!"
fi