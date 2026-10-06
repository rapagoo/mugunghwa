# Author kccistc KSH 
import cv2
from ultralytics import YOLO

def plot_counter(img, label1, org):
    font= cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 1
    color = (0,255,0)
    thickness = 2
    cv2.putText(img, label1, org, font, fontScale, color, thickness, cv2.LINE_AA)

model = YOLO('yolov8n.pt')

cap = cv2.VideoCapture(0)
org = (50, 50)

while cap.isOpened():
    success, frame = cap.read()
    
    if success:
        results= model(frame)
        
        annotated_frame = results[0].plot()
        
        cv2.imshow("YOLOv8 Inference", annotated_frame)
        for result in results:
            if result.boxes.cls is None:
                continue
#            print(result.names)
            names = model.names
            person_id = list(names)[list(names.values()).index('person')]
            person_cnt = results[0].boxes.cls.tolist().count(person_id)
            print(person_id)
            print(person_cnt)

            total_det_per_class = '%g %ss' % (person_cnt, names[int(person_id)])
            print(total_det_per_class)
            plot_counter(annotated_frame, total_det_per_class, org)
            if person_cnt != 0:
                print("Detected person or vehicle, turning on LED...")    

        cv2.imshow("YOLOv8 Inference", annotated_frame)
        if cv2.waitKey(1)&0xFF == ord("q"):
            break
    else:
        print("cap.read")
        break
    
cap.release()
cv2.destroyAllWindows()
