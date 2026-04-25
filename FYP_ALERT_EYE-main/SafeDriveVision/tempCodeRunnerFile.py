 results = model(frame_bgr)
            detections = results.xyxy[0].cpu().numpy()
            for detection in detections:
                if int(detection[5]) == 67:  # Assuming 67 is the class id for cell phones
                    x1, y1, x2, y2, conf = int(detection[0]), int(detection[1]), int(detection[2]), int(detection[3]), detection[4]
                    cv2.rectangle(img_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(img_draw, f'Cell Phone {conf:.2f}', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    COUNTER2 += 1
                    if COUNTER2 >= 3:
                        cv2.putText(img_draw, "Rangez votre CELL PHONE!", (x1, y1 - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        sound_thread("phone")
                        COUNTER2 = 0
