import cv2
import numpy as nm
import autopy
import handtracking as htm
import time
import pyautogui
import math


class OneEuroFilter:
    def __init__(self, min_cutoff=1.25, beta=0.03, d_cutoff=1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    def reset(self):
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    @staticmethod
    def _alpha(dt, cutoff):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x, t_now):
        if self.t_prev is None or self.x_prev is None:
            self.t_prev = t_now
            self.x_prev = float(x)
            return float(x)

        dt = max(t_now - self.t_prev, 1e-3)
        dx = (float(x) - self.x_prev) / dt
        alpha_d = self._alpha(dt, self.d_cutoff)
        dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_prev

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        alpha = self._alpha(dt, cutoff)
        x_hat = alpha * float(x) + (1.0 - alpha) * self.x_prev

        self.t_prev = t_now
        self.dx_prev = dx_hat
        self.x_prev = x_hat
        return x_hat


def landmark_distance(lm_list, p1, p2):
    x1, y1 = lm_list[p1][1], lm_list[p1][2]
    x2, y2 = lm_list[p2][1], lm_list[p2][2]
    return math.hypot(x2 - x1, y2 - y1)


def hand_scale_px(lm_list):
    palm_width = landmark_distance(lm_list, 5, 17)
    palm_height = landmark_distance(lm_list, 0, 9)
    # Weighted blend is steadier than using only one pair of landmarks.
    return max(35.0, 0.7 * palm_width + 0.3 * palm_height)


def map_and_filter_cursor(
    x_cam,
    y_cam,
    t_now,
    map_x_min,
    map_x_max,
    map_y_min,
    map_y_max,
    wscr,
    hscr,
    y_gain,
    x_filter,
    y_filter,
    last_move_x,
    last_move_y,
    last_move_time,
    deadzone_px,
    gain_x,
    gain_y,
    edge_snap_ratio,
    max_speed_px_s,
):
    span_x = max(1.0, float(map_x_max - map_x_min))
    span_y = max(1.0, float(map_y_max - map_y_min))

    nx = (float(x_cam) - float(map_x_min)) / span_x
    ny = (float(y_cam) - float(map_y_min)) / span_y

    # Gain around center reduces physical travel needed for full-screen coverage.
    nx = 0.5 + (nx - 0.5) * gain_x
    ny = 0.5 + (ny - 0.5) * gain_y

    nx = float(nm.clip(nx, 0.0, 1.0))
    ny = float(nm.clip(ny, 0.0, 1.0))

    if nx <= edge_snap_ratio:
        nx = 0.0
    elif nx >= 1.0 - edge_snap_ratio:
        nx = 1.0

    if ny <= edge_snap_ratio:
        ny = 0.0
    elif ny >= 1.0 - edge_snap_ratio:
        ny = 1.0

    x_target = nx * (wscr - 1)
    y_target = ny * ((hscr - 1) * y_gain)

    x_target = float(nm.clip(x_target, 0, wscr - 1))
    y_target = float(nm.clip(y_target, 0, hscr - 1))

    x_filtered = x_filter.filter(x_target, t_now)
    y_filtered = y_filter.filter(y_target, t_now)

    move_x = float(nm.clip(wscr - x_filtered, 0, wscr - 1))
    move_y = float(nm.clip(y_filtered, 0, hscr - 1))

    cursor_speed = 0.0
    if last_move_time > 0:
        dt = max(t_now - last_move_time, 1e-3)
        dx = move_x - last_move_x
        dy = move_y - last_move_y
        step = math.hypot(dx, dy)
        max_step = max_speed_px_s * dt
        if step > max_step and step > 0:
            scale = max_step / step
            move_x = last_move_x + dx * scale
            move_y = last_move_y + dy * scale
            dx = move_x - last_move_x
            dy = move_y - last_move_y
        if abs(dx) < deadzone_px and abs(dy) < deadzone_px:
            move_x = last_move_x
            move_y = last_move_y
            cursor_speed = 0.0
        else:
            cursor_speed = math.hypot(dx, dy) / dt

    return move_x, move_y, cursor_speed


# Webcam setup
wcam, hcam = 640, 480

# Cursor mapping region defaults
frame_left_ratio = 0.0
frame_right_ratio = 0.0
frame_top_ratio = 0.0
frame_bottom_ratio = 0.0
vertical_reach_gain = 1.0

# Cursor movement amplification
cursor_gain_x = 1.55
cursor_gain_y = 1.72
cursor_edge_snap_ratio = 0.015
cursor_max_speed_px_s = 4800.0

# Cursor filter and stabilization
cursor_deadzone_px = 2.0
cursor_x_filter = OneEuroFilter(min_cutoff=1.1, beta=0.05, d_cutoff=1.0)
cursor_y_filter = OneEuroFilter(min_cutoff=1.1, beta=0.05, d_cutoff=1.0)
last_move_x, last_move_y = 0.0, 0.0
last_move_time = 0.0
cursor_speed = 0.0

# Camera-space smoothing to reduce landmark jitter without adding much latency.
cam_smoothing_alpha = 0.35
smoothed_cam_x = None
smoothed_cam_y = None

# Action gating by cursor speed
action_speed_limit = 999999.0
click_speed_limit = 999999.0

# Auto calibration
auto_calibration_window = 2.0
auto_calibration_padding = 0.10
auto_calibration_min_samples = 35
auto_calibrating = True
calibration_started_at = None
calibration_samples = 0
calib_min_x, calib_max_x = float("inf"), float("-inf")
calib_min_y, calib_max_y = float("inf"), float("-inf")
calibrated_bounds = None

# Exit gesture detection
exit_gesture_time = 0
exit_gesture_delay = 0.5

# Click timing
double_click_hold_seconds = 2.0
single_click_min_hold = 0.06
click_pinch_start_time = 0
double_click_fired = False
last_left_action_time = 0
left_action_cooldown = 0.08
click_confirm_frames = 2
click_pinch_frames = 0

# Right-click timing
last_right_click_time = 0
right_click_cooldown = 0.45

# Scroll tuning (continuous + smooth)
scroll_deadzone_px = 2.5
scroll_sensitivity = 28.8
scroll_max_per_frame = 1560
scroll_smooth_alpha = 0.35
scroll_accum = 0.0
scroll_dy_smooth = 0.0
scroll_last_y = None

# Drag state
dragging = False

# Gesture stability (frames)
gesture_hold_frames = 5
right_click_frames = 0
drag_start_frames = 0
drag_release_frames = 0
right_click_latched = False

# Gesture thresholds normalized to hand scale
click_pinch_ratio_threshold = 0.68
drag_start_ratio_threshold = 0.45
drag_stop_ratio_threshold = 0.82
scroll_delta_ratio_threshold = 0.12

# Hand-loss handling
hand_lost_frames = 0
hand_lost_release_frames = 5
hand_lost_filter_reset_frames = 10

# Action-safe area guards
action_side_guard = 0
action_top_guard = 0
action_bottom_guard = 0
click_side_guard = 0
click_bottom_guard = 0

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(3, wcam)
cap.set(4, hcam)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cap.set(cv2.CAP_PROP_FPS, 60)

pTime = 0
detector = htm.handDetector(maxHands=1)
wscr, hscr = autopy.screen.size()
wscr, hscr = int(wscr), int(hscr)

window_name = "Virtual Mouse"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 920, 690)

while True:
    success, img = cap.read()
    if not success:
        continue

    now = time.time()
    cam_h, cam_w = img.shape[:2]

    default_left = max(2, int(cam_w * frame_left_ratio))
    default_right = min(cam_w - 2, cam_w - max(2, int(cam_w * frame_right_ratio)))
    default_top = max(2, int(cam_h * frame_top_ratio))
    default_bottom = min(cam_h - 2, cam_h - max(2, int(cam_h * frame_bottom_ratio)))

    map_x_min, map_x_max = default_left, default_right
    map_y_min, map_y_max = default_top, default_bottom

    if calibrated_bounds is not None:
        map_x_min, map_x_max, map_y_min, map_y_max = calibrated_bounds

    img = detector.findHands(img)
    lmList, bbox = detector.findPosition(img)

    if len(lmList) != 0:
        hand_lost_frames = 0
        x1, y1 = lmList[8][1:]   # index tip
        x2, y2 = lmList[12][1:]  # middle tip
        x_thumb, y_thumb = lmList[4][1:]  # thumb tip
        fingers = detector.fingersUp()
        scale = hand_scale_px(lmList)

        if smoothed_cam_x is None:
            smoothed_cam_x, smoothed_cam_y = float(x1), float(y1)
        else:
            smoothed_cam_x = (cam_smoothing_alpha * float(x1)) + ((1.0 - cam_smoothing_alpha) * smoothed_cam_x)
            smoothed_cam_y = (cam_smoothing_alpha * float(y1)) + ((1.0 - cam_smoothing_alpha) * smoothed_cam_y)

        click_pinch_threshold = scale * click_pinch_ratio_threshold
        drag_start_threshold = scale * drag_start_ratio_threshold
        drag_stop_threshold = scale * drag_stop_ratio_threshold
        scroll_delta_threshold = scale * scroll_delta_ratio_threshold

        # Auto calibration builds a better movement box from real motion.
        if auto_calibrating:
            if calibration_started_at is None:
                calibration_started_at = now

            calib_min_x = min(calib_min_x, x1)
            calib_max_x = max(calib_max_x, x1)
            calib_min_y = min(calib_min_y, y1)
            calib_max_y = max(calib_max_y, y1)
            calibration_samples += 1

            elapsed = now - calibration_started_at
            if elapsed >= auto_calibration_window:
                if calibration_samples >= auto_calibration_min_samples:
                    span_x = max(1.0, calib_max_x - calib_min_x)
                    span_y = max(1.0, calib_max_y - calib_min_y)
                    pad_x = int(span_x * auto_calibration_padding)
                    pad_y = int(span_y * auto_calibration_padding)

                    cal_left = max(0, int(calib_min_x - pad_x))
                    cal_right = min(cam_w - 1, int(calib_max_x + pad_x))
                    cal_top = max(0, int(calib_min_y - pad_y))
                    cal_bottom = min(cam_h - 1, int(calib_max_y + pad_y))

                    # Never shrink below defaults; calibration only improves reach.
                    map_x_min = min(default_left, cal_left)
                    map_x_max = max(default_right, cal_right)
                    map_y_min = min(default_top, cal_top)
                    map_y_max = max(default_bottom, cal_bottom)
                    calibrated_bounds = (map_x_min, map_x_max, map_y_min, map_y_max)

                auto_calibrating = False

        # Exit gesture
        if fingers == [1, 0, 0, 0, 0] and y_thumb < y2:
            if exit_gesture_time == 0:
                exit_gesture_time = now
            if now - exit_gesture_time > exit_gesture_delay:
                print("Exit gesture detected. Terminating program...")
                break
            cv2.circle(img, (x_thumb, y_thumb), 20, (0, 0, 255), cv2.FILLED)
            # Intentionally no on-screen text here; keep overlay to FPS only.
        else:
            exit_gesture_time = 0

        # Movement mapping region
        cv2.rectangle(
            img,
            (map_x_min, map_y_min),
            (map_x_max, map_y_max),
            (255, 23, 14),
            2,
        )

        action_top_limit = map_y_min + action_top_guard
        action_bottom_limit = max(action_top_limit, map_y_max - action_bottom_guard)
        click_top_limit = map_y_min + action_top_guard
        click_bottom_limit = max(click_top_limit, map_y_max - click_bottom_guard)

        action_zone = (
            (map_x_min + action_side_guard) <= smoothed_cam_x <= (map_x_max - action_side_guard)
            and action_top_limit <= smoothed_cam_y <= action_bottom_limit
            and cursor_speed < action_speed_limit
        )
        click_zone = (
            (map_x_min + click_side_guard) <= smoothed_cam_x <= (map_x_max - click_side_guard)
            and click_top_limit <= smoothed_cam_y <= click_bottom_limit
            and cursor_speed < click_speed_limit
        )

        # Cursor movement (kept independent from action zone)
        if fingers[1] == 1 and fingers[2] == 0 and fingers[0] == 0:
            move_x, move_y, cursor_speed = map_and_filter_cursor(
                smoothed_cam_x,
                smoothed_cam_y,
                now,
                map_x_min,
                map_x_max,
                map_y_min,
                map_y_max,
                wscr,
                hscr,
                vertical_reach_gain,
                cursor_x_filter,
                cursor_y_filter,
                last_move_x,
                last_move_y,
                last_move_time,
                cursor_deadzone_px,
                cursor_gain_x,
                cursor_gain_y,
                cursor_edge_snap_ratio,
                cursor_max_speed_px_s,
            )
            autopy.mouse.move(move_x, move_y)
            last_move_x, last_move_y, last_move_time = move_x, move_y, now
            cv2.circle(img, (int(smoothed_cam_x), int(smoothed_cam_y)), 15, (255, 0, 255), cv2.FILLED)

        # Left click / double click (index + middle pinch)
        # Hold pinch >= 2 seconds for double-click, release earlier for single-click.
        pinch_active = False
        if fingers[1] == 1 and fingers[2] == 1 and click_zone:
            length, img, lineInfo = detector.findDistance(8, 12, img)
            if length < click_pinch_threshold:
                click_pinch_frames += 1
                if click_pinch_frames >= click_confirm_frames:
                    pinch_active = True
                    cv2.circle(img, (lineInfo[4], lineInfo[5]), 15, (0, 255, 0), cv2.FILLED)

                    if click_pinch_start_time == 0:
                        click_pinch_start_time = now
                        double_click_fired = False

                    hold_time = now - click_pinch_start_time
                    if hold_time >= double_click_hold_seconds and not double_click_fired:
                        if now - last_left_action_time > left_action_cooldown:
                            autopy.mouse.click(autopy.mouse.Button.LEFT)
                            autopy.mouse.click(autopy.mouse.Button.LEFT)
                            last_left_action_time = now
                            double_click_fired = True
                            print("Double Click")
            else:
                click_pinch_frames = 0
        else:
            click_pinch_frames = 0

        if not pinch_active and click_pinch_start_time != 0:
            hold_time = now - click_pinch_start_time
            if single_click_min_hold <= hold_time < double_click_hold_seconds and not double_click_fired:
                if now - last_left_action_time > left_action_cooldown:
                    autopy.mouse.click(autopy.mouse.Button.LEFT)
                    last_left_action_time = now
                    print("Single Click")
            click_pinch_start_time = 0
            double_click_fired = False

        # Drag (index + thumb pinch), with hold and hysteresis
        if fingers[1] == 1 and fingers[0] == 1 and (action_zone or dragging):
            length_thumb_index, img, lineInfo = detector.findDistance(4, 8, img)

            if length_thumb_index < drag_start_threshold:
                drag_start_frames += 1
                drag_release_frames = 0
            elif dragging and length_thumb_index > drag_stop_threshold:
                drag_release_frames += 1
                drag_start_frames = 0
            else:
                drag_start_frames = 0
                drag_release_frames = 0

            if not dragging and drag_start_frames >= gesture_hold_frames:
                pyautogui.mouseDown(button="left")
                dragging = True
                print("Drag Started")

            if dragging:
                if drag_release_frames >= gesture_hold_frames:
                    pyautogui.mouseUp(button="left")
                    dragging = False
                    print("Drag Stopped")
                else:
                    move_x, move_y, cursor_speed = map_and_filter_cursor(
                        smoothed_cam_x,
                        smoothed_cam_y,
                        now,
                        map_x_min,
                        map_x_max,
                        map_y_min,
                        map_y_max,
                        wscr,
                        hscr,
                        vertical_reach_gain,
                        cursor_x_filter,
                        cursor_y_filter,
                        last_move_x,
                        last_move_y,
                        last_move_time,
                        cursor_deadzone_px,
                        cursor_gain_x,
                        cursor_gain_y,
                        cursor_edge_snap_ratio,
                        cursor_max_speed_px_s,
                    )
                    autopy.mouse.move(move_x, move_y)
                    last_move_x, last_move_y, last_move_time = move_x, move_y, now
        else:
            drag_start_frames = 0
            drag_release_frames = 0
            if dragging and not action_zone:
                pyautogui.mouseUp(button="left")
                dragging = False
                print("Drag Stopped")

        # Right click (index + pinky), with hold and cooldown
        right_condition = fingers[1] == 1 and fingers[2] == 0 and fingers[4] == 1 and action_zone
        if right_condition:
            right_click_frames += 1
        else:
            right_click_frames = 0
            right_click_latched = False

        if right_click_frames >= gesture_hold_frames and not right_click_latched:
            if now - last_right_click_time > right_click_cooldown:
                autopy.mouse.click(autopy.mouse.Button.RIGHT)
                last_right_click_time = now
                right_click_latched = True
                print("Right Click")

        # Scroll (open hand), tolerant to thumb detection jitter and smooth per-frame.
        scroll_condition = action_zone and (fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 1)
        if scroll_condition:
            if scroll_last_y is None:
                scroll_last_y = smoothed_cam_y
            delta_y = smoothed_cam_y - scroll_last_y
            scroll_last_y = smoothed_cam_y

            if abs(delta_y) < scroll_deadzone_px:
                delta_y = 0.0

            scroll_dy_smooth = (scroll_smooth_alpha * delta_y) + ((1.0 - scroll_smooth_alpha) * scroll_dy_smooth)
            scroll_accum += scroll_dy_smooth * scroll_sensitivity

            scroll_amount = int(max(-scroll_max_per_frame, min(scroll_max_per_frame, scroll_accum)))
            if scroll_amount != 0:
                pyautogui.scroll(-scroll_amount)
                scroll_accum -= scroll_amount
        else:
            scroll_last_y = None
            scroll_dy_smooth = 0.0
            scroll_accum = 0.0

    else:
        hand_lost_frames += 1
        smoothed_cam_x = None
        smoothed_cam_y = None
        scroll_last_y = None
        scroll_dy_smooth = 0.0
        scroll_accum = 0.0
        right_click_frames = 0
        click_pinch_start_time = 0
        double_click_fired = False
        right_click_latched = False
        click_pinch_frames = 0
        prev_y_scroll = None
        cursor_speed = 0.0

        if hand_lost_frames >= hand_lost_filter_reset_frames:
            cursor_x_filter.reset()
            cursor_y_filter.reset()

        if dragging and hand_lost_frames >= hand_lost_release_frames:
            pyautogui.mouseUp(button="left")
            dragging = False
            print("Drag Stopped (hand lost)")

    # FPS display only
    cTime = time.time()
    fps = 1 / (cTime - pTime) if cTime != pTime else 0
    pTime = cTime
    cv2.putText(img, f"FPS: {int(fps)}", (20, 50), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)

    # Display a slightly larger preview window
    display_img = cv2.resize(img, (920, 690), interpolation=cv2.INTER_LINEAR)
    cv2.imshow(window_name, display_img)

    key = cv2.waitKey(1)
    if key == ord('q') or key == 27:
        break
    if key == ord('c'):
        auto_calibrating = True
        calibration_started_at = None
        calibration_samples = 0
        calib_min_x, calib_max_x = float("inf"), float("-inf")
        calib_min_y, calib_max_y = float("inf"), float("-inf")
        calibrated_bounds = None
    if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
        break

cap.release()
cv2.destroyAllWindows()
