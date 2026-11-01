
import cv2
import numpy as np


# Adjustable starting values; validate with your own webcam.
MIN_FACE_WIDTH = 100
MIN_FACE_HEIGHT = 100
MIN_BRIGHTNESS = 45
MAX_BRIGHTNESS = 215
MIN_SHARPNESS = 45.0


def check_face_quality(frame, face):
    """
    Returns (accepted, message, metrics).
    A quality pass does not guarantee a correct identity.
    """
    x, y, width, height = map(int, face[:4])

    metrics = {
        "face_width": width,
        "face_height": height,
        "brightness": None,
        "sharpness": None,
    }

    frame_height, frame_width = frame.shape[:2]

    # Ensure the detected face rectangle stays inside the frame.
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(frame_width, x + width)
    y2 = min(frame_height, y + height)

    if x2 <= x1 or y2 <= y1:
        return False, "Move into the camera view", metrics

    face_image = frame[y1:y2, x1:x2]

    if width < MIN_FACE_WIDTH or height < MIN_FACE_HEIGHT:
        return False, "Move closer to the camera", metrics

    gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)

    brightness = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    metrics["brightness"] = round(brightness, 2)
    metrics["sharpness"] = round(sharpness, 2)

    if brightness < MIN_BRIGHTNESS:
        return False, "Too dark — improve the lighting", metrics

    if brightness > MAX_BRIGHTNESS:
        return False, "Too bright — reduce direct light", metrics

    if sharpness < MIN_SHARPNESS:
        return False, "Image blurry — hold still", metrics

    return True, "Face quality OK — verifying identity", metrics
