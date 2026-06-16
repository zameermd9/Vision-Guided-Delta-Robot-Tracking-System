import cv2
import numpy as np
from collections import deque
from pymodbus.client.sync import ModbusTcpClient

# =========================
# PLC MODBUS SETTINGS
# =========================
PLC_IP = "192.168.0.1"
PLC_PORT = 1502
UNIT_ID = 1

DI_TRIGGER = 0

HR_X = 0
HR_Y = 1
HR_VALID = 2
HR_SEQ = 3

X_OFFSET = 10000
Y_OFFSET = 10000

# =========================
# CAMERA SETTINGS
# =========================
CAM_INDEX = 0
FRAME_W = 640
FRAME_H = 480

ROI_W = 360
ROI_H = 260

# =========================
# 2D CAMERA TO ROBOT CALIBRATION
# RobotX = AX*u + BX*v + CX
# RobotY = AY*u + BY*v + CY
# =========================
AX = -0.54813911
BX = 1.00117558
CX = -40.83893043

AY = -0.40978904
BY = -0.66968832
CY = 264.84386595

# =========================
# DETECTION SETTINGS
# =========================
MIN_AREA = 250
MAX_AREA = 10000

STABLE_WINDOW = 5
center_buffer = deque(maxlen=STABLE_WINDOW)

seq_counter = 0


def pixel_to_robot_xy(u, v):
    robot_x = AX * u + BX * v + CX
    robot_y = AY * u + BY * v + CY

    return int(round(robot_x)), int(round(robot_y))


def encode_signed(value, offset):
    return int(value + offset)


def limit_value(value, min_val, max_val):
    if value > max_val:
        return max_val
    elif value < min_val:
        return min_val
    return value


def detect_object(frame):
    h, w = frame.shape[:2]

    cx = w // 2
    cy = h // 2

    x1 = cx - ROI_W // 2
    y1 = cy - ROI_H // 2
    x2 = cx + ROI_W // 2
    y2 = cy + ROI_H // 2

    roi = frame[y1:y2, x1:x2].copy()

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower = np.array([0, 0, 115])
    upper = np.array([180, 90, 255])

    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5, 5), np.uint8)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        if area < MIN_AREA or area > MAX_AREA:
            continue

        if len(cnt) < 5:
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)

        if bh == 0:
            continue

        aspect = bw / float(bh)

        if aspect < 0.45 or aspect > 2.2:
            continue

        perimeter = cv2.arcLength(cnt, True)

        if perimeter == 0:
            continue

        circularity = 4 * np.pi * area / (perimeter * perimeter)

        if circularity < 0.35:
            continue

        ellipse = cv2.fitEllipse(cnt)
        (ex, ey), (MA, ma), angle = ellipse

        if MA < 20 or ma < 15:
            continue

        if MA > 130 or ma > 130:
            continue

        score = area * circularity
        candidates.append((score, ellipse, ex, ey, area, MA, ma))

    if not candidates:
        return None, roi, mask

    candidates.sort(key=lambda x: x[0], reverse=True)

    score, ellipse, ex, ey, area, MA, ma = candidates[0]

    camera_x = int(x1 + ex)
    camera_y = int(y1 + ey)

    center_buffer.append((camera_x, camera_y))

    stable_u = int(np.mean([p[0] for p in center_buffer]))
    stable_v = int(np.mean([p[1] for p in center_buffer]))

    robot_x, robot_y = pixel_to_robot_xy(stable_u, stable_v)

    # Safety limit matching PLC testing range
    robot_x = limit_value(robot_x, -45, 45)
    robot_y = limit_value(robot_y, -35, 35)

    roi_x = stable_u - x1
    roi_y = stable_v - y1

    cv2.ellipse(roi, ellipse, (0, 255, 0), 2)
    cv2.circle(roi, (roi_x, roi_y), 6, (0, 0, 255), -1)

    cv2.line(roi, (roi_x - 15, roi_y), (roi_x + 15, roi_y), (255, 0, 0), 2)
    cv2.line(roi, (roi_x, roi_y - 15), (roi_x, roi_y + 15), (255, 0, 0), 2)

    cv2.putText(
        roi,
        f"CAM X={stable_u} Y={stable_v}",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 0),
        2
    )

    cv2.putText(
        roi,
        f"ROBOT X={robot_x} Y={robot_y}",
        (10, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 255),
        2
    )

    return (robot_x, robot_y, stable_u, stable_v), roi, mask


def main():
    global seq_counter

    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)

    if not client.connect():
        print("Could not connect to PLC")
        return

    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("Camera not opened")
        client.close()
        return

    print("System ready")
    print("Waiting for PLC trigger...")

    while True:
        trigger = client.read_discrete_inputs(DI_TRIGGER, 1, unit=UNIT_ID)

        if trigger.isError():
            print("Trigger read error")
            continue

        trigger_on = trigger.bits[0]

        ret, frame = cap.read()

        if not ret:
            continue

        if trigger_on:
            result, roi, mask = detect_object(frame)

            if result is not None:
                robot_x, robot_y, pixel_x, pixel_y = result

                x_reg = encode_signed(robot_x, X_OFFSET)
                y_reg = encode_signed(robot_y, Y_OFFSET)

                seq_counter = (seq_counter + 1) % 65535

                client.write_registers(
                    HR_X,
                    [x_reg, y_reg, 1, seq_counter],
                    unit=UNIT_ID
                )

                print(
                    f"SENT -> RobotX={robot_x}, RobotY={robot_y}, "
                    f"CamX={pixel_x}, CamY={pixel_y}, Seq={seq_counter}"
                )

            else:
                center_buffer.clear()
                client.write_register(HR_VALID, 0, unit=UNIT_ID)
                print("Object not detected")

            cv2.imshow("Tracking ROI", roi)
            cv2.imshow("Mask", mask)

        else:
            center_buffer.clear()
            client.write_register(HR_VALID, 0, unit=UNIT_ID)

        cv2.imshow("Full Camera", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    client.close()


if __name__ == "__main__":
    main()
