import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jetson'))
from game.volume import SpeakerVolume, VolumeUnavailable, SINK

class VolumeTests(unittest.TestCase):
    def fake(self, state):
        def run(*args):
            if args==('list','sinks'):
                return 'Sink #0\n Name: '+SINK+'\n Mute: '+('yes' if state['muted'] else 'no')+'\n Volume: left: 100 / '+str(state['volume'])+'% / 0 dB, right: 100 / '+str(state['volume'])+'% / 0 dB\n'
            self.assertEqual(args[1],SINK)
            if args[0]=='set-sink-volume':state['volume']=int(args[2][:-1])
            elif args[0]=='set-sink-mute':state['muted']=args[2]=='1'
            else:self.fail('Unexpected audio command')
            return ''
        return run
    def test_apply_persist_and_restore_without_changing_other_setting(self):
        base=Path(__file__).resolve().parents[1]/'.runtime'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(base)) as folder:
            store=Path(folder)/'volume.json'
            state=dict(volume=100,muted=False)
            volume=SpeakerVolume(store)
            with patch.object(volume,'_run',side_effect=self.fake(state)):
                self.assertEqual(volume.snapshot(),state)
                self.assertFalse(store.exists())
                self.assertEqual(volume.update({'volume':35}),dict(volume=35,muted=False))
                self.assertEqual(volume.update({'muted':True}),dict(volume=35,muted=True))
            restored=SpeakerVolume(store)
            state.update(volume=100,muted=False)
            with patch.object(restored,'_run',side_effect=self.fake(state)):
                self.assertEqual(restored.snapshot(),dict(volume=35,muted=True))
            self.assertEqual(json.loads(store.read_text()),dict(volume=35,muted=True))
    def test_reject_invalid_input_before_audio_commands(self):
        volume=SpeakerVolume('missing-volume-settings.json')
        with patch.object(volume,'_run') as run:
            for body in ({},{'volume':True},{'volume':101},{'volume':-1},{'muted':1},{'sink':'other'}):
                with self.assertRaises(ValueError):volume.update(body)
            run.assert_not_called()
    def test_missing_usb_is_unavailable_not_default_speaker(self):
        volume=SpeakerVolume('missing-volume-settings.json')
        with patch.object(volume,'_run',return_value='Sink #1\n Name: analog-other\n Mute: no\n Volume: left: 100 / 100% / 0 dB\n'):
            with self.assertRaises(VolumeUnavailable):volume.snapshot()

if __name__=='__main__':unittest.main()
