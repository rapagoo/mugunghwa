"""Headless webcam/video detector with a read-only LAN dashboard."""
import argparse
import os
from pathlib import Path
import threading
import time

os.environ['YOLO_AUTOINSTALL'] = 'false'
from game.web import Monitor, GameDatabase, create_server
from game.realtime import LatestFrame
from game.calibration_store import CalibrationStore


def run_vision(args, monitor, stop, calibration, recorder):
    # Heavy dependencies stay outside HTTP threads and database tests.
    import cv2
    import torch
    from game.source import FrameSource
    from game.detector import load_detector, pose_keypoints
    from game import geometry
    from game.finish import FinishDetector
    from game.validation import VisionValidation
    from game.motion import MotionTrial
    from game.pose_motion import PoseMotionTrial
    slot = LatestFrame()
    capture = None
    reader = None
    reader_stop = threading.Event()
    try:
        settings = calibration.snapshot()
        config = settings['config']
        capture = FrameSource(camera=args.camera, video=args.video)
        first = capture.read()
        if first is None:
            raise ValueError('Empty source')
        height, width = first[0].shape[:2]
        ok, initial = cv2.imencode('.jpg',first[0],[cv2.IMWRITE_JPEG_QUALITY,75])
        monitor.update(dict(width=width,height=height), initial.tobytes() if ok else None,
                       initial.tobytes() if ok else None)
        if config:
            geometry.check_size(config, width, height)
        model, size = load_detector(args.model, args.imgsz)
        options = dict(imgsz=size, conf=.35, classes=[0], persist=True,
                       tracker='bytetrack.yaml', verbose=False,
                       device=0 if torch.cuda.is_available() else 'cpu')
        for _ in range(5):
            model.track(first[0], **options)

        def read_frames():
            try:
                # Webcam warmup can take seconds; do not submit its old first frame.
                packet = first if args.video else capture.read()
                anchor = time.monotonic()
                while not stop.is_set() and not reader_stop.is_set():
                    if packet is None:
                        if not args.loop or not args.video:
                            slot.close()
                            break
                        capture.restart()
                        packet = capture.read()
                        anchor = time.monotonic()
                        if packet is None:
                            raise ValueError('Cannot restart source')
                    frame, media, epoch = packet
                    if args.video and stop.wait(max(0, anchor + media - time.monotonic())):
                        break
                    slot.publish((frame, media, epoch, time.monotonic()))
                    packet = capture.read()
            except Exception as error:
                monitor.update(dict(state='error', error=str(error)))
                slot.close()

        reader = threading.Thread(target=read_frames, daemon=True, name='capture')
        reader.start()
        serial, epoch, previous, last_jpeg = 0, None, None, 0
        revision = None
        finish = None
        validation = None
        motion = None
        reset_version = None
        session_number = 0
        while not stop.is_set():
            packet = slot.next(serial)
            if packet is None:
                if monitor.snapshot()['state'] != 'error':
                    monitor.update(dict(state='ended'))
                break
            serial, (frame, media, current_epoch, source_wall) = packet
            settings = calibration.snapshot()
            changed = settings['revision'] != revision
            requested_reset = monitor.reset_version()
            if current_epoch != epoch or changed:
                for tracker in model.predictor.trackers:
                    tracker.reset()
                epoch, previous = current_epoch, None
                config = settings['config']
                revision = settings['revision']
                finish = FinishDetector(config) if config else None
            if validation is None or changed or validation.session['epoch'] != current_epoch or requested_reset != reset_version:
                session_number += 1
                reset_version = requested_reset
                finish = FinishDetector(config) if config else None
                validation = VisionValidation(config,dict(number=session_number,epoch=current_epoch,
                    calibration_revision=revision,reset_generation=reset_version))
                motion = MotionTrial()
                pose_motion = PoseMotionTrial()
            start = time.monotonic()
            result = model.track(frame, **options)[0]
            boxes = result.boxes.xyxy.cpu().tolist()
            ids = [] if result.boxes.id is None else result.boxes.id.int().cpu().tolist()
            confidence = result.boxes.conf.cpu().tolist()
            keypoints = pose_keypoints(result,boxes)
            height, width = frame.shape[:2]
            observed = time.monotonic()
            trial_command = monitor.get_trial()
            diagnostics = validation.update(boxes,ids,confidence,width,height,media,finish,
                None if previous is None else (observed-previous)*1000)
            if finish:
                for candidate in finish.completed.values():
                    if "phase_version" not in candidate:
                        candidate.update(phase=trial_command["phase"],phase_version=trial_command["version"])
            motion_result = motion.update(boxes,ids,diagnostics['observations'],width,height,
                                          source_wall,trial_command)
            pose_result = pose_motion.update(boxes,ids,diagnostics['observations'],keypoints,
                                             source_wall,trial_command)
            completed = time.monotonic()
            data = dict(state='running', epoch=epoch, media_s=media, people=len(boxes),
                        track_ids=ids, candidates=list(finish.completed.values()) if finish else [],
                        processing_ms=round((completed-start)*1000, 1),
                        interval_ms=None if previous is None else round((completed-previous)*1000,1),
                        result_latency_ms=round((completed-source_wall)*1000,1),
                        completed_wall=completed, preview_hz=args.preview_hz,
                        width=width, height=height, source_fps=capture.fps)
            data['calibration_revision'] = revision
            data['calibrated'] = config is not None
            data['roi_people'] = sum(geometry.inside([(x1+x2)/2/width,y2/height],config['roi'])
                                     for x1,y1,x2,y2 in boxes) if config else None
            data['validation'] = diagnostics
            data['motion_trial'] = motion_result
            data['pose_trial'] = pose_result
            data['pose'] = dict(enabled=keypoints is not None,
                visible_keypoints=[sum(k[2]>=.5 for k in person) for person in keypoints] if keypoints is not None else [],
                motion_method='pose_fixed_baseline' if keypoints is not None else 'box_center')
            data['candidates'] = list(finish.completed.values()) if finish else []
            data['outside_people'] = len(boxes)-data['roi_people'] if config else None
            recorder.submit(dict(media_s=media,source_wall=source_wall,completed_wall=completed,
                boxes=boxes,ids=ids,confidence=confidence,keypoints=keypoints,
                interval_ms=data['interval_ms'],processing_ms=data['processing_ms'],
                result_latency_ms=data['result_latency_ms'],calibration_revision=revision,
                epoch=epoch,trial=motion_result,pose_trial=pose_result,source_size=[width,height]),frame)
            jpeg = None
            camera_jpeg = None
            if completed-last_jpeg >= 1/args.preview_hz:
                preview = frame.copy()
                if config:
                    geometry.overlay(preview, config)
                if keypoints is not None:
                    bones = [(5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),
                             (11,12),(11,13),(13,15),(12,14),(14,16)]
                    for person in keypoints:
                        for a,b in bones:
                            if person[a][2]>=.5 and person[b][2]>=.5:
                                cv2.line(preview,tuple(round(v) for v in person[a][:2]),
                                         tuple(round(v) for v in person[b][:2]),(255,180,60),2)
                        for x,y,c in person:
                            if c>=.5:
                                cv2.circle(preview,(round(x),round(y)),3,(255,180,60),-1)
                for i, (x1,y1,x2,y2) in enumerate(boxes):
                    observation = data['validation']['observations'][i]
                    color = (50,210,90) if observation['in_roi'] else (150,150,150) if config else (0,220,255)
                    if observation['candidate']:
                        color = (0,190,255)
                    cv2.rectangle(preview,(round(x1),round(y1)),(round(x2),round(y2)),color,2)
                    cv2.circle(preview,(round((x1+x2)/2),min(height-1,round(y2))),5,color,-1)
                    label = 'ID {} {}'.format(observation['track_id'] if observation['track_id'] is not None else '?',
                        'CANDIDATE' if observation['candidate'] else 'IN' if observation['in_roi'] else 'OUT' if config else '')
                    m = motion_result['observations'][i]
                    label += ' ' + ('STOP-MOVE' if m['stop_candidate'] else m['status'].upper())
                    if m['stop_candidate']:
                        color = (60,60,255)
                    p = pose_result['observations'][i]
                    if keypoints is not None:
                        label += ' POSE ' + ('CANDIDATE' if p['stop_candidate'] else p['status'].upper())
                        if p['stop_candidate']:
                            color = (60,60,255)
                    cv2.putText(preview,label,(round(x1),max(20,round(y1)-5)),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
                if width > 960:
                    preview = cv2.resize(preview,(960,round(height*960/width)))
                ok, encoded = cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,75])
                if not ok:
                    raise RuntimeError('JPEG encoding failed')
                jpeg = encoded.tobytes()
                ok, raw = cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,75])
                if ok:
                    camera_jpeg = raw.tobytes()
                last_jpeg = completed
            monitor.update(data, jpeg, camera_jpeg)
            previous = completed
    except Exception as error:
        monitor.update(dict(state='error', error=str(error)))
    finally:
        reader_stop.set()
        slot.close()
        if reader:
            reader.join(3)
        if capture and (reader is None or not reader.is_alive()):
            capture.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--video')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--config')
    parser.add_argument('--calibration-store', default='.runtime/web/calibration-camera.json')
    parser.add_argument('--loop', action='store_true')
    parser.add_argument('--model', default=str(Path(__file__).parent/'examples/yolov8n.pt'))
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--preview-hz', type=float, default=5)
    parser.add_argument('--database', default='.runtime/web/game.db')
    parser.add_argument('--db-config', help='private MariaDB JSON config; overrides SQLite')
    args = parser.parse_args()
    if not 0 < args.preview_hz <= 15 or args.imgsz <= 0:
        parser.error('preview-hz must be >0 and <=15; imgsz must be positive')
    monitor = Monitor('video' if args.video else 'camera')
    calibration = CalibrationStore(args.calibration_store)
    if args.config:
        from game import geometry
        config = geometry.load(args.config)
        calibration.save(config, calibration.snapshot()['revision'], *config['reference_size'])
    if args.db_config:
        from game.mariadb_store import MariaGameDatabase
        database = MariaGameDatabase(args.db_config)
    else:
        database = GameDatabase(args.database)
    from game.recording import TrialRecorder
    recorder=TrialRecorder('.runtime/pose-recordings')
    server = create_server(args.host,args.port,monitor,database,calibration,recorder,
        dict(model=args.model,imgsz=args.imgsz,confidence=.35,preview_hz=args.preview_hz))
    stop = threading.Event()
    def supervise():
        while not stop.is_set():
            monitor.update(dict(state='preparing',error=None))
            run_vision(args,monitor,stop,calibration,recorder)
            if args.video and monitor.snapshot()['state'] == 'ended':
                return
            if stop.wait(3):
                return
    worker = threading.Thread(target=supervise,daemon=True)
    worker.start()
    print('Monitor listening on {}:{}'.format(*server.server_address),flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        monitor.close()
        server.server_close()
        worker.join(5)
        recorder.close()


if __name__ == '__main__':
    main()
