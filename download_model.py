"""Fetch the official, versioned MediaPipe model, checking its SHA-256."""
import hashlib
from pathlib import Path
import urllib.request

URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
SHA256 = 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'
TARGET = Path(__file__).resolve().parent/'models'/'hand_landmarker.task'


def main():
    if TARGET.exists() and hashlib.sha256(TARGET.read_bytes()).hexdigest() == SHA256:
        print('Hand model: OK')
        return
    TARGET.parent.mkdir(exist_ok=True)
    with urllib.request.urlopen(URL, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError('Model checksum mismatch. Download was not saved.')
    temp = TARGET.with_suffix('.download')
    temp.write_bytes(data)
    temp.replace(TARGET)
    print('Hand model downloaded and verified.')


if __name__ == '__main__':
    main()
