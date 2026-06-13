# Setup Audio Sensor On Raspberry Pi
PortAudio - lower level C/C++ lib
sounddevice - Python bindings for PortAudio

For raspberry pi setup - 
[docs](https://learn.adafruit.com/adafruit-i2s-mems-microphone-breakout/)  

raspberry-pi-wiring-test
required libs
```bash
sudo apt-get install libportaudio2
```

## Test Audio Capture
Make sure device shows up -
```bash
arecord -l
```
Test a 30 sec recording - 
```bash
arecord -D plughw:1 -c1 -r 48000 -f S32_LE -t wav -V mono -d 30 -f cd 30_sec_test.wav
```

copy over .wav file to test processing
```bash
nmcli connection show --active
scp rpi@raspberrypi.lan:/home/rpi/30_sec_test.wav ./
```

### Continuously Capture Audio And Send (simple)
Run audio capture script in the background
```bash
chmod +x test_collection.sh
./test_collection.sh &
```

Run python script to process audio files and send results over LoRa 

```bash
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
python process_audio.py
```

### Todo
Capture audio with no gaps
Add tests