import cv2
from ultralytics import YOLO
from picamera2 import Picamera2
model = YOLO("yolov8n.pt")
PERSON_CLASS_ID = 0  #id di dataset
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (320, 320)}
)
picam2.configure(config)
picam2.start()
while True:
    frame = picam2.capture_array()
    results = model.predict(
        frame, imgsz=320, conf=0.4, classes=[PERSON_CLASS_ID], verbose=False
    )
    annotated = results[0].plot()
    jumlah_orang = len(results[0].boxes)

    cv2.putText(
        annotated, f"Orang terdeteksi: {jumlah_orang}",
        (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
    )
    cv2.imshow("Person Detection - PiCamera2", annotated)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
picam2.stop()
cv2.destroyAllWindows()