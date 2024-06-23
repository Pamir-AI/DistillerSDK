import audioop
import numpy as np
import logging

def get_volume(data: bytes) -> int:
    if not data:
        return 0
    
    if len(data) % 2 != 0:
        data = data[:-(len(data) % 2)]
    
    try:
        rms = audioop.rms(data, 2)  # The '2' indicates 16-bit samples
        db = 20 * np.log10(rms) if rms > 0 else 0.0
        return int(db)
    except audioop.error as e:
        logging.error(f"Audio processing error: {e}")
        return 0
