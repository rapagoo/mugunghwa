import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jetson'))
from game.realtime import LatestFrame, ReplayClock


class RealtimeTests(unittest.TestCase):
    def test_slow_consumer_gets_latest_without_backlog(self):
        slot = LatestFrame()
        slot.publish(('epoch0', 1))
        serial, item = slot.next(0)
        self.assertEqual(item, ('epoch0', 1))
        for i in range(2, 60):
            slot.publish(('epoch0', i))
        serial, item = slot.next(serial)
        self.assertEqual(item, ('epoch0', 59))
        slot.publish(('epoch1', 0))
        self.assertEqual(slot.next(serial)[1], ('epoch1', 0))

    def test_close_wakes_blocked_worker(self):
        slot = LatestFrame()
        results = []
        worker = threading.Thread(target=lambda: results.append(slot.next(0)))
        worker.start()
        slot.close()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [None])

    def test_pause_preserves_media_clock(self):
        clock = ReplayClock(100)
        self.assertEqual(clock.media(102), 2)
        clock.toggle(102)
        self.assertEqual(clock.media(110), 2)
        clock.toggle(110)
        self.assertEqual(clock.media(111), 3)


if __name__ == '__main__':
    unittest.main()
