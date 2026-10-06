import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
PERSON_CLASS_ID = 0  # id "person" di COCO dataset

cap = cv2.VideoCapture(0)  # 0 = webcam default laptop

if not cap.isOpened():
    print("Webcam gak kedetect. Cek permission kamera di OS lo.")
    exit()

print("Jalan... tekan 'q' buat keluar")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Gagal baca frame dari webcam")
        break

    results = model.predict(
        frame, conf=0.4, classes=[PERSON_CLASS_ID], verbose=False
    )

    annotated = results[0].plot()
    jumlah_orang = len(results[0].boxes)

    cv2.putText(
        annotated, f"Orang terdeteksi: {jumlah_orang}",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
    )

    cv2.imshow("Person Detection - Laptop", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()