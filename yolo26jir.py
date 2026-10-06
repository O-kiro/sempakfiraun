import cv2
import torch
from ultralytics import YOLO

if torch.backends.mps.is_available():
    device = "mps"  # Apple Silicon GPU (M-series chip)
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

print(f"Pake device: {device}")

model = YOLO("yolo26x.pt")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Webcam gak kedetect. Cek permission kamera di OS lo.")
    exit()

print("Jalan... tekan 'q' buat keluar")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal baca frame dari webcam")
        break

    results = model.predict(frame, conf=0.4, device=device, verbose=False)

    annotated = results[0].plot()
    jumlah_objek = len(results[0].boxes)

    cv2.putText(
        annotated, f"Objek terdeteksi: {jumlah_objek}",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
    )

    cv2.imshow("Detect All - YOLO26x", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()