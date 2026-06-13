#!/bin/bash

# Note - just for testing - there will be gaps in audio 

# Configuration
DEVICE="plughw:1"
DURATION=60
SAMPLE_RATE=16000
FORMAT="S16_LE"

echo "Starting continuous recording on $DEVICE..."

while true; do
    # Generate a filename with a timestamp
    FILENAME="recording_$(date +%Y%m%d_%H%M%S).wav"
    
    echo "Recording $FILENAME..."
    
    # Run arecord
    arecord -D "$DEVICE" -c1 -r "$SAMPLE_RATE" -f "$FORMAT" -d "$DURATION" "$FILENAME"
    
    # Optional: Short sleep to ensure clean file rotation
    # sleep 1 
done