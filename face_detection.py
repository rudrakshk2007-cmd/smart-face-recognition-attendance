
import cv2
from pathlib import Path

# Paths to the downloaded AI models
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

yunet_path = MODEL_DIR / "face_detection_yunet_2023mar.onnx"

# Check whether the model exists
if not yunet_path.exists():
    raise FileNotFoundError(
        f"YuNet model not found: {yunet_path}"
    )

# Open your laptop webcam
camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise RuntimeError("Could not open webcam.")

detector = cv2.FaceDetectorYN.create(
    str(yunet_path),
    "",
    (320, 320),
    0.8,
    0.3,
    5000
)

print("Face detection started. Press Q to quit.")

try:
    while True:
        success, frame = camera.read()

        if not success:
            print("Could not capture frame.")
            break

        height, width = frame.shape[:2]

        # Update detector with the actual camera resolution
        detector.setInputSize((width, height))

        _, faces = detector.detect(frame)

        if faces is not None:
            for face in faces:
                x, y, w, h = face[:4].astype(int)

                # Draw a rectangle around the detected face
                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    "Face Detected",
                    (x, max(y - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

        cv2.imshow("Smart Attendance - Face Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.release()
    cv2.destroyAllWindows()
