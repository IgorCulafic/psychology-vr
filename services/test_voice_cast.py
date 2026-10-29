import io
import json
import tempfile
import threading
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
import soundfile as sf

from alex_service import Bridge, ROOT, validate_reply
from higgs_service import HiggsVoice
from voice_cast import VoiceCast


def beat(emotion='angry', text='Prva rečenica. Druga rečenica.'):
    return validate_reply({'segments':[dict(text=text,emotion=emotion,intensity=.8)]})[0]


class VoiceCastTests(unittest.TestCase):
    def setUp(self):
        self.cast=VoiceCast(ROOT)

    def test_exact_assignments_and_presets(self):
        for scenario,speaker,temp in [('ivan-work-exhaustion','igor_2026-10-03',.6),
                ('stefan-fire-witness','person_01',.6),('nikola-bereavement','person_02',.45),
                ('alex-earthquake','person_03',.55)]:
            r=self.cast.resolve(scenario,beat())
            self.assertEqual((r['speaker'],r['temperature']),(speaker,temp))
        sad=self.cast.resolve('ivan-work-exhaustion',beat('sad'))
        self.assertEqual((sad['mode'],sad['sentence_gap_seconds'],sad['tag']),('sentences',.38,'<|prosody:expressive_low|>'))

    def test_unmapped_emotion_keeps_identity_and_unknown_scenario_rejected(self):
        r=self.cast.resolve('stefan-fire-witness',beat('neutral'))
        fallback=self.cast.resolve('stefan-fire-witness',{'emotion':'unmapped'})
        self.assertEqual(r,fallback)
        for scenario in ('../../voice.wav','stranger',{},42):
            with self.assertRaises(ValueError):self.cast.resolve(scenario,beat())

    def test_stream_pause_preserves_model_pause(self):
        segments=[beat('sad'),dict(beat('sad'),pause_before_seconds=.8),beat('sad')]
        self.cast.apply_stream_pauses('ivan-work-exhaustion',segments)
        self.assertEqual([s['pause_before_seconds'] for s in segments],[0,.8,.38])

    def test_delivery_preserves_whole_approved_performance_and_emotion_changes(self):
        opening=beat('despondent','Stalno sam umoran. Imao sam slobodan vikend, a kao da nisam odmorio.')
        angry=beat('angry')
        self.assertEqual(self.cast.delivery_segments('ivan-work-exhaustion',[opening,angry]),[opening,angry])
        split=self.cast.delivery_segments('ivan-work-exhaustion',[beat('sad')])
        self.assertEqual([s['text'] for s in split],['Prva rečenica.','Druga rečenica.'])

    def test_bridge_sends_trusted_session_scenario(self):
        config=json.loads((ROOT/'services/config.example.json').read_text())
        with tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime') as tmp:
            config.update(tts_provider='higgs',session_log_dir=tmp,lip_sync_provider='none')
            bridge=Bridge(config);bridge.runtime=Path(tmp)
            bridge.generate=lambda *args:[dict(beat(),scenario_id='attacker')]
            data=io.BytesIO();sf.write(data,np.sin(np.arange(1000)*.1)*.1,1000,format='WAV',subtype='PCM_16')
            sent=[]
            def response(request,**kwargs):
                sent.append(json.loads(request.data));value=Mock();value.read.return_value=data.getvalue()
                context=Mock();context.__enter__=Mock(return_value=value);context.__exit__=Mock(return_value=False)
                return context
            with patch('alex_service.urllib.request.urlopen',side_effect=response):
                for scenario in self.cast.scenarios:
                    key=bridge.new_session(scenario)['session_id']
                    bridge.turn(key,'Hello')
                    self.assertEqual(sent[-1]['scenario_id'],scenario)
                    self.assertNotIn('scenario_id',sent[-1]['segment'])

    def worker(self):
        voice=HiggsVoice.__new__(HiggsVoice)
        voice.lock=threading.Lock();voice.config={'higgs_quantization':'bf16'}
        voice.voice_cast=self.cast;voice.reference_cache={};voice.rate=1000
        voice.reference_codes='legacy';voice.reference_text='legacy';voice.tokenizer=object()
        voice.torch=Mock();voice.torch.inference_mode.side_effect=nullcontext
        voice.model=Mock()
        voice.model._encode_reference.side_effect=lambda *args:Mock(cpu=Mock(return_value=object()))
        wave=np.sin(np.arange(1000)*.1).astype('float32')*.1
        voice.model.generate_speech.side_effect=lambda *a,**k:Mock(numpy=Mock(return_value=wave.copy()))
        return voice

    def test_worker_switches_reference_without_leaking_or_reloading_model(self):
        v=self.worker()
        for scenario in ('stefan-fire-witness','nikola-bereavement','stefan-fire-witness'):
            v.synthesize(beat(),scenario)
        calls=v.model.generate_speech.call_args_list
        self.assertIs(calls[0].kwargs['reference_codes'],calls[2].kwargs['reference_codes'])
        self.assertIsNot(calls[0].kwargs['reference_codes'],calls[1].kwargs['reference_codes'])
        self.assertEqual(v.model._encode_reference.call_count,2)
        self.assertEqual([c.kwargs['temperature'] for c in calls],[.6,.45,.6])
        self.assertTrue(calls[0].args[0].startswith('<|emotion:anger|>'))
        self.assertTrue(calls[1].args[0].startswith('<|emotion:bitterness|>'))
        self.assertEqual(v.reference_codes,'legacy')
        self.assertFalse(v.lock.locked())

    def test_worker_sadness_splits_with_approved_gap(self):
        v=self.worker()
        audio,rate=sf.read(io.BytesIO(v.synthesize(beat('sad'),'ivan-work-exhaustion')))
        self.assertEqual(len(audio),2380)
        self.assertEqual(v.model.generate_speech.call_count,2)
        self.assertTrue(all(c.kwargs['temperature']==.5 for c in v.model.generate_speech.call_args_list))

    def test_prepared_opening_is_exact_and_never_reused_for_new_dialogue(self):
        v=self.worker();v.prepared_openings={('ivan-work-exhaustion','angry',beat()['text']):b'approved opening'}
        self.assertEqual(v.synthesize(beat(),'ivan-work-exhaustion'),b'approved opening')
        v.model.generate_speech.assert_not_called()
        v.synthesize(beat(text='Novi razgovor.'),'ivan-work-exhaustion')
        self.assertEqual(v.model.generate_speech.call_count,1)
        self.assertFalse(v.lock.locked())

    def test_quantization_cannot_silently_degrade_assigned_voices(self):
        v=self.worker();v.config['higgs_quantization']='nf4'
        with self.assertRaisesRegex(ValueError,'BF16'):v.synthesize(beat(),'alex-earthquake')
        self.assertFalse(v.lock.locked())
        v.model.generate_speech.assert_not_called()


if __name__=='__main__':unittest.main()
