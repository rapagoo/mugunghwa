"""Private full-inference-rate evidence, asynchronously written with bounded queues."""
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import shutil
import statistics
import threading
import time
import uuid

SCENARIOS = ('still','arms','turn','distance','crossing','mixed')


class TrialRecorder:
    def __init__(self, root, encoder=None, limit_s=120):
        self.root = Path(root)
        self.encoder = encoder or self.encode
        self.limit_s = limit_s
        self.lock = threading.RLock()
        self.state = dict(state='idle')
        self.accepting = False
        self.thread = None

    @staticmethod
    def encode(frame):
        import cv2
        ok, data = cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,85])
        if not ok:
            raise OSError('Frame encoding failed')
        return data.tobytes()

    def snapshot(self):
        with self.lock:
            state = dict(self.state)
        if state.get('started_wall') is not None:
            state['elapsed_s'] = round((state.get('stopped_wall') or time.monotonic())-state.pop('started_wall'),1)
        state.pop('stopped_wall',None)
        return state

    def start(self, scenario, metadata):
        if scenario not in SCENARIOS:
            raise ValueError('Invalid scenario')
        with self.lock:
            if self.state['state'] in ('recording','finalizing') or (self.thread and self.thread.is_alive()):
                raise ValueError('Recording already active')
            self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.root.chmod(0o700)
            if shutil.disk_usage(self.root).free < 1024**3:
                raise OSError('At least 1 GiB free disk required')
            name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
            self.folder=self.root/name
            self.folder.mkdir(mode=0o700)
            (self.folder/'frames').mkdir(mode=0o700)
            (self.folder/'metadata.json').write_text(json.dumps(dict(schema=1,scenario=scenario,
                started_at=datetime.now(timezone.utc).isoformat(),limit_s=self.limit_s,**metadata),ensure_ascii=False,indent=2))
            self.queue=queue.Queue(maxsize=16)
            self.state=dict(state='recording',session_id=name,scenario=scenario,started_wall=time.monotonic(),
                            accepted=0,written=0,dropped=0,image_dropped=0,bytes=0,error=None)
            self.accepting=True
            self.end = threading.Event()
            self.thread=threading.Thread(target=self.write,daemon=True)
            self.thread.start()
            threading.Thread(target=self.expire,args=(self.end,),daemon=True).start()
        return self.snapshot()

    def expire(self, event):
        if not event.wait(self.limit_s):
            with self.lock:
                if self.end is event: self.stop('time_limit')

    def stop(self, reason='user'):
        with self.lock:
            if self.accepting:
                self.accepting=False
                self.end.set()
                self.state.update(state='finalizing',stop_reason=reason,stopped_wall=time.monotonic())
        return self.snapshot()

    def submit(self, record, frame):
        with self.lock:
            if not self.accepting:
                return
            if self.state['accepted']+self.state['dropped']>=6000:
                self.stop('sample_limit')
                return
            try:
                seq=self.state['accepted']+self.state['dropped']+1
                self.queue.put_nowait((dict(record,seq=seq),frame.copy()))
                self.state['accepted']+=1
            except queue.Full:
                self.state['dropped']+=1

    def write(self):
        intervals, processing, people, visible = [], [], [], []
        try:
            with (self.folder/'samples.jsonl').open('w') as stream:
                while True:
                    try:
                        record, frame=self.queue.get(timeout=.1)
                    except queue.Empty:
                        with self.lock:
                            if not self.accepting: break
                        continue
                    data=self.encoder(frame)
                    if self.state['bytes']+len(data) <= 512*1024**2:
                        image='frames/{:06d}.jpg'.format(record['seq'])
                        (self.folder/image).write_bytes(data)
                        record['image']=image
                        with self.lock: self.state['bytes']+=len(data)
                    else:
                        record['image']=None
                        with self.lock: self.state['image_dropped']+=1
                        self.stop('size_limit')
                    stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
                    if record.get('interval_ms') is not None: intervals.append(record['interval_ms'])
                    processing.append(record['processing_ms'])
                    people.append(len(record['boxes']))
                    if record.get('keypoints'):
                        visible.extend(sum(k[2]>=.5 for k in person) for person in record['keypoints'])
                    with self.lock: self.state['written']+=1
        except Exception as error:
            with self.lock:
                self.accepting=False
                self.end.set()
                self.state.update(state='error',error=str(error),stopped_wall=time.monotonic())
        summary=self.snapshot()
        if summary['state']!='error': summary['state']='complete'
        summary.update(mean_interval_ms=round(statistics.mean(intervals),2) if intervals else None,
            mean_processing_ms=round(statistics.mean(processing),2) if processing else None,
            people_min=min(people) if people else None,people_max=max(people) if people else None,
            mean_visible_keypoints=round(statistics.mean(visible),2) if visible else None,
            note='Inference samples with original JPEG frames; no ground-truth accuracy or sensor-to-browser latency.')
        try:
            (self.folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
            for path in self.folder.rglob('*'):
                if path.is_file(): path.chmod(0o600)
        except OSError:
            with self.lock: self.state.update(state='error',error='Summary storage failed')
        else:
            with self.lock:
                if self.state['state']!='error': self.state['state']='complete'

    def close(self):
        self.stop('shutdown')
        if self.thread: self.thread.join(10)
