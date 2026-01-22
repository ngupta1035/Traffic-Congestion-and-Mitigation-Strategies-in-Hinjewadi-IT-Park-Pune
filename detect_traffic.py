"""import cv2
import time
import csv
from ultralytics import YOLO

# -----------------------------
# CONFIGURATION
# -----------------------------
VIDEO_PATH = "videos/traffic.mp4"   # change if needed
MODEL_PATH = "yolov8n.pt"            # lightweight YOLO model
CSV_PATH = "data/traffic_data.csv"

LOW_THRESHOLD = 20
MEDIUM_THRESHOLD = 50

# -----------------------------
# LOAD YOLO MODEL
# -----------------------------
model = YOLO(MODEL_PATH)

# -----------------------------
# VIDEO CAPTURE
# -----------------------------
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# -----------------------------
# CSV FILE SETUP
# -----------------------------
with open(CSV_PATH, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Time", "Vehicle_Count", "Congestion_Level"])

start_time = time.time()

# -----------------------------
# MAIN LOOP
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO detection
    results = model(frame, stream=True)

    vehicle_count = 0

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]

            # count only vehicles
            if label in ["car", "motorcycle", "bus", "truck"]:
                vehicle_count += 1

                # draw bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

    # -----------------------------
    # CONGESTION CLASSIFICATION
    # -----------------------------
    if vehicle_count <= LOW_THRESHOLD:
        congestion = "LOW"
        color = (0, 255, 0)
    elif vehicle_count <= MEDIUM_THRESHOLD:
        congestion = "MEDIUM"
        color = (0, 255, 255)
    else:
        congestion = "HIGH"
        color = (0, 0, 255)

    # -----------------------------
    # DISPLAY INFO
    # -----------------------------
    cv2.putText(
        frame,
        f"Vehicles: {vehicle_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2,
    )

    cv2.putText(
        frame,
        f"Congestion: {congestion}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2,
    )

    cv2.imshow("Traffic Congestion Detection", frame)

    # -----------------------------
    # SAVE DATA EVERY 5 SECONDS
    # -----------------------------
    current_time = time.time()
    if int(current_time - start_time) % 5 == 0:
        timestamp = time.strftime("%H:%M:%S")
        with open(CSV_PATH, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, vehicle_count, congestion])

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# -----------------------------
# CLEANUP
# -----------------------------
cap.release()
cv2.destroyAllWindows()
print("Program ended successfully.")
"""
import cv2
import time
import csv
from ultralytics import YOLO

print("Program started")

# -----------------------------
# CONFIGURATION
# -----------------------------
VIDEO_PATH = "videos/traffic.mp4"
MODEL_PATH = "yolov8n.pt"
CSV_PATH = "data/traffic_data.csv"

LOW_THRESHOLD = 20
MEDIUM_THRESHOLD = 50

# -----------------------------
# LOAD YOLO MODEL
# -----------------------------
print("Loading YOLO model...")
model = YOLO(MODEL_PATH)
print("YOLO model loaded")

# -----------------------------
# VIDEO CAPTURE
# -----------------------------
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

print("Video opened successfully")

# -----------------------------
# CSV FILE SETUP
# -----------------------------
with open(CSV_PATH, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Time", "Vehicle_Count", "Congestion_Level"])

start_time = time.time()
last_saved_time = 0

# -----------------------------
# MAIN LOOP
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame)

    vehicle_count = 0

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]

            if label in ["car", "motorcycle", "bus", "truck"]:
                vehicle_count += 1

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

    # -----------------------------
    # CONGESTION CLASSIFICATION
    # -----------------------------
    if vehicle_count <= LOW_THRESHOLD:
        congestion = "LOW"
        color = (0, 255, 0)
    elif vehicle_count <= MEDIUM_THRESHOLD:
        congestion = "MEDIUM"
        color = (0, 255, 255)
    else:
        congestion = "HIGH"
        color = (0, 0, 255)

    # -----------------------------
    # DISPLAY INFO
    # -----------------------------
    cv2.putText(
        frame,
        f"Vehicles: {vehicle_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2
    )

    cv2.putText(
        frame,
        f"Congestion: {congestion}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2
    )

    cv2.imshow("Traffic Congestion Detection", frame)

    # -----------------------------
    # SAVE DATA EVERY 5 SECONDS
    # -----------------------------
    current_time = time.time()
    if current_time - last_saved_time >= 5:
        timestamp = time.strftime("%H:%M:%S")
        with open(CSV_PATH, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, vehicle_count, congestion])
        last_saved_time = current_time

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# -----------------------------
# CLEANUP
# -----------------------------
cap.release()
cv2.destroyAllWindows()
print("Program ended successfully")
