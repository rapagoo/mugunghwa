"""Speaker queue semantics without requiring audio hardware or ffplay."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.audio import Audio


class Player:
    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        return self.code

    def terminate(self):
        self.code = -15


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.audio = Audio('.')
        self.audio.play = Mock(side_effect=lambda name: Player())

    def test_simultaneous_failures_play_once_each_in_sequence(self):
        keys=[('game','FAIL',str(i)) for i in range(3)]
        for key in keys + keys:
            self.audio.fail(key)
        self.assertEqual(self.audio.play.call_count,1)
        self.assertEqual(list(self.audio.shot_queue),keys[1:])
        for expected in (2,3):
            self.audio.shot.code=0
            self.audio.poll()
            self.assertEqual(self.audio.play.call_count,expected)
        self.audio.shot.code=0
        self.audio.poll()
        self.assertIsNone(self.audio.shot)
        self.assertEqual(self.audio.play.call_count,3)

    def test_game_end_chant_cancel_preserves_pending_shots(self):
        self.audio.start(('game','phase'))
        self.audio.fail(('game','FAIL','1'))
        self.audio.fail(('game','FAIL','2'))
        self.audio.cancel()
        self.assertIsNone(self.audio.chant)
        self.audio.shot.code=0
        self.audio.poll()
        self.assertEqual(self.audio.play.call_count,3)
        self.assertEqual(len(self.audio.shot_queue),0)

    def test_failed_shot_does_not_block_next_or_chant_completion(self):
        self.audio.start(('game','phase'))
        self.audio.fail(('game','FAIL','1'))
        self.audio.fail(('game','FAIL','2'))
        self.audio.shot.code=1
        self.audio.chant.code=0
        self.assertEqual(self.audio.poll(),(('game','phase'),True))
        self.assertEqual(self.audio.play.call_count,3)
        self.audio.close()
        self.assertFalse(self.audio.shot_queue)


if __name__=='__main__':
    unittest.main()
