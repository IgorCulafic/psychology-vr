import array
import hashlib
import io
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import wave

from alex_service import Bridge, ROOT, StaleTurn, validate_reply
from speech_reuse import SpeechReuse, wav_duration
from voice_cast import VoiceCast
from higgs_service import HiggsVoice


def audio(seconds=1):
    data = io.BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        wav.writeframes(array.array('h', [int(math.sin(i*.1)*3000) for i in range(round(seconds*8000))]).tobytes())
    return data.getvalue()


class SpeechReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'services/.runtime')
        self.root = Path(self.temp.name)
        assert self.root.resolve().is_relative_to((ROOT/'services/.runtime').resolve())
        self.addCleanup(self.temp.cleanup)
        self.cast = VoiceCast(ROOT)
        self.config = dict(tts_provider='higgs', higgs_quantization='bf16',
            speech_cache_enabled=True, recorded_speech_enabled=True, lip_sync_provider='rhubarb')
        self.segment = validate_reply({'segments':[dict(text='Prva rečenica. Druga rečenica.', emotion='angry', intensity=.5)]})[0]
        self.segment['scenario_id'] = 'alex-earthquake'

    def library(self, **changes):
        directory = self.root/'voices/recorded'
        directory.mkdir(parents=True, exist_ok=True)
        wav = directory/'alex.wav'
        wav.write_bytes(audio())
        clip = dict(scenario_id='alex-earthquake', speaker='person_03', emotion='angry',
            text=self.segment['text'], audio='voices/recorded/alex.wav',
            sha256=hashlib.sha256(wav.read_bytes()).hexdigest(), approved=True)
        clip.update(changes)
        (directory/'manifest.json').write_text(json.dumps(dict(version=1, clips=[clip])))
        return SpeechReuse(self.root, self.config, self.cast)

    def bridge(self, reuse):
        config = json.loads((ROOT/'services/config.example.json').read_text())
        config.update(tts_provider=reuse.config['tts_provider'], lip_sync_provider='rhubarb')
        bridge = Bridge(config)
        bridge.runtime = self.root
        bridge.speech_reuse = reuse
        bridge.synthesize = Mock(side_effect=self.synthesize(bridge))
        bridge.align_mouth = Mock(return_value=([dict(start=0.,end=.8,value='A')], 'rhubarb'))
        return bridge

    def synthesize(self, bridge):
        def write(segment, audio_id):
            path=bridge.runtime/(audio_id+'.wav');path.write_bytes(audio())
            return '/audio/'+path.name
        return write

    def kokoro(self, **changes):
        folder=self.root/'.cache/kokoro';folder.mkdir(parents=True,exist_ok=True)
        for name,content in (('kokoro-v1.0.onnx',b'model-v1'),('voices-v1.0.bin',b'voices-v1')):
            path=folder/name
            if not path.exists():path.write_bytes(content)
        config=dict(self.config,tts_provider='kokoro',tts_model='kokoro',tts_voice='am_michael')
        config.update(changes)
        return SpeechReuse(self.root,config,None)

    def test_kokoro_repeated_exact_speech_and_cues_survive_restart_without_higgs_reference(self):
        reuse=self.kokoro();bridge=self.bridge(reuse)
        first=dict(self.segment);bridge.prepare_audio_segment(first,'kokoro-first')
        bridge.speech_reuse=self.kokoro()
        second=dict(self.segment);bridge.prepare_audio_segment(second,'kokoro-second')
        self.assertEqual(first['speech_source'],'generated')
        self.assertEqual(second['speech_source'],'cache')
        self.assertEqual(second['mouth_cues'],first['mouth_cues'])
        self.assertEqual((self.root/'kokoro-first.wav').read_bytes(),(self.root/'kokoro-second.wav').read_bytes())
        self.assertEqual(bridge.synthesize.call_count,1)
        self.assertEqual(bridge.align_mouth.call_count,1)
        self.assertEqual(bridge.config['tts_provider'],'kokoro')
        self.assertFalse((self.root/'voices/reference.wav').exists())

    def test_kokoro_voice_model_bank_and_implementation_settings_invalidate_cache_identity(self):
        reuse=self.kokoro();old=reuse.key(self.segment)
        reuse.put(old,audio(),[],'audio_envelope',reuse.alignment_key())
        self.assertIsNotNone(reuse.lookup(self.segment)[1])
        for setting in (dict(tts_voice='bm_george'),dict(tts_model='different-model')):
            changed=self.kokoro(**setting)
            self.assertNotEqual(old,changed.key(self.segment))
            self.assertIsNone(changed.lookup(self.segment)[1])
        for field in (dict(text=self.segment['text']+' More words.'),dict(emotion='sad'),dict(voice_style='gentle'),dict(intensity=.7)):
            self.assertNotEqual(old,reuse.key(dict(self.segment,**field)))
            self.assertIsNone(reuse.lookup(dict(self.segment,**field))[1])
        for name in ('kokoro-v1.0.onnx','voices-v1.0.bin'):
            previous=self.kokoro().key(self.segment)
            path=self.root/'.cache/kokoro'/name
            path.write_bytes(path.read_bytes()+b' changed')
            # Fingerprints are captured for each service lifetime, matching the
            # resident model. Restarting after an asset update cannot reuse it.
            self.assertNotEqual(previous,self.kokoro().key(self.segment))
            self.assertIsNone(self.kokoro().lookup(self.segment)[1])

    def test_kokoro_aligner_change_keeps_audio_but_recomputes_mouth_cues(self):
        reuse=self.kokoro();bridge=self.bridge(reuse)
        executable=self.root/'.tools/rhubarb/Rhubarb-Lip-Sync-1.14.0-Windows/rhubarb.exe'
        executable.parent.mkdir(parents=True);executable.write_bytes(b'aligner-v1')
        bridge.prepare_audio_segment(dict(self.segment),'kokoro-before-aligner')
        executable.write_bytes(b'changed alignment implementation')
        second=dict(self.segment);bridge.prepare_audio_segment(second,'kokoro-after-aligner')
        self.assertEqual(second['speech_source'],'cache')
        self.assertEqual(bridge.synthesize.call_count,1)
        self.assertEqual(bridge.align_mouth.call_count,2)

    def test_kokoro_never_uses_a_matching_cloned_voice_recording(self):
        higgs=self.library();higgs_bridge=self.bridge(higgs)
        higgs_bridge.prepare_audio_segment(dict(self.segment),'recorded-higgs')
        reuse=self.kokoro();bridge=self.bridge(reuse)
        self.assertEqual(reuse.recordings,{})
        self.assertIsNone(reuse.recording(self.segment))
        segment=dict(self.segment);bridge.prepare_audio_segment(segment,'generated-kokoro')
        self.assertEqual(segment['speech_source'],'generated')
        bridge.synthesize.assert_called_once()
        self.assertNotEqual(higgs.key(self.segment),reuse.key(self.segment))

    def test_kokoro_disabled_cache_does_not_read_existing_hits_or_publish_new_ones(self):
        reuse=self.kokoro();bridge=self.bridge(reuse)
        bridge.prepare_audio_segment(dict(self.segment),'cached-kokoro')
        disabled=self.kokoro(speech_cache_enabled=False)
        bridge.speech_reuse=disabled
        segment=dict(self.segment);bridge.prepare_audio_segment(segment,'uncached-kokoro')
        self.assertFalse(disabled.enabled);self.assertFalse(disabled.cache_enabled)
        self.assertIsNone(disabled.get(disabled.key(self.segment)))
        self.assertEqual(segment['speech_source'],'generated')
        self.assertEqual(bridge.synthesize.call_count,2)
        self.assertEqual(bridge.align_mouth.call_count,2)

    def test_recorded_clip_and_cues_skip_generation_and_second_alignment(self):
        reuse=self.library();bridge=self.bridge(reuse)
        bridge.prepare_audio_segment(dict(self.segment), 'first')
        bridge.synthesize.assert_not_called()
        self.assertEqual(bridge.align_mouth.call_count, 1)
        self.assertEqual((self.root/'first.wav').read_bytes(), audio())
        # Survive service restart; no resident model or reference encoding required.
        bridge.speech_reuse=SpeechReuse(self.root,self.config,self.cast)
        segment=dict(self.segment);bridge.prepare_audio_segment(segment, 'second')
        self.assertEqual(segment['speech_source'],'cache')
        bridge.synthesize.assert_not_called()
        self.assertEqual(bridge.align_mouth.call_count,1)

    def test_new_words_emotion_and_other_speaker_never_use_recording(self):
        reuse=self.library()
        for changed in (dict(text='Ne, nijesam to rekao.'),dict(emotion='sad'),dict(scenario_id='stefan-fire-witness')):
            self.assertIsNone(reuse.recording(dict(self.segment,**changed)))
        self.assertIsNotNone(reuse.recording(dict(self.segment,text='Prva rečenica.  Druga rečenica.')))

    def test_wrong_speaker_unapproved_clip_and_path_escape_rejected(self):
        for change in (dict(speaker='person_01'),dict(approved=False),dict(audio='../outside.wav')):
            with self.assertRaises(ValueError):self.library(**change)

    def test_generated_audio_reused_and_precision_recipe_changes_invalidate(self):
        reuse=SpeechReuse(self.root,self.config,self.cast);bridge=self.bridge(reuse)
        bridge.prepare_audio_segment(dict(self.segment),'first')
        bridge.prepare_audio_segment(dict(self.segment),'second')
        self.assertEqual(bridge.synthesize.call_count,1)
        self.assertEqual(bridge.align_mouth.call_count,1)
        old=reuse.key(self.segment)
        reuse.config=dict(self.config,higgs_quantization='nf4',higgs_allow_quantized_cast=True)
        self.assertNotEqual(old,reuse.key(self.segment))
        reuse.config['higgs_allow_quantized_cast']=False
        denied=reuse.key(self.segment)
        reuse.config['higgs_allow_quantized_cast']=True
        self.assertNotEqual(denied,reuse.key(self.segment))
        self.cast.speakers['person_03']['anger']['seed']=100
        self.assertNotEqual(old,reuse.key(self.segment))

    def test_bad_recording_falls_back_without_poisoning_recorded_cache(self):
        reuse=self.library();bridge=self.bridge(reuse)
        original=reuse.recorded_audio(self.segment)['audio']
        (self.root/'voices/recorded/alex.wav').write_bytes(b'broken')
        bridge.prepare_audio_segment(dict(self.segment),'fallback')
        self.assertEqual(bridge.synthesize.call_count,1)
        (self.root/'voices/recorded/alex.wav').write_bytes(original)
        segment=dict(self.segment);bridge.prepare_audio_segment(segment,'restored')
        self.assertEqual(segment['speech_source'],'recorded')
        self.assertEqual(bridge.synthesize.call_count,1)

    def test_corrupt_cached_wave_is_a_miss_and_aligner_changes_reuse_audio(self):
        reuse=SpeechReuse(self.root,self.config,self.cast);bridge=self.bridge(reuse)
        bridge.prepare_audio_segment(dict(self.segment),'first')
        path=reuse.directory/(reuse.key(self.segment)+'.wav')
        path.write_bytes(audio(2))
        bridge.prepare_audio_segment(dict(self.segment),'second')
        self.assertEqual(bridge.synthesize.call_count,2)
        bridge.config['conversation_language']='cnr'
        reuse.config['conversation_language']='cnr'
        bridge.prepare_audio_segment(dict(self.segment),'third')
        self.assertEqual(bridge.synthesize.call_count,2)
        self.assertEqual(bridge.align_mouth.call_count,3)

    def test_envelope_after_transient_rhubarb_failure_is_retried(self):
        reuse=SpeechReuse(self.root,self.config,self.cast);bridge=self.bridge(reuse)
        bridge.align_mouth.return_value=([], 'audio_envelope')
        bridge.prepare_audio_segment(dict(self.segment),'first')
        bridge.align_mouth.return_value=([dict(start=0,end=.8,value='A')], 'rhubarb')
        bridge.prepare_audio_segment(dict(self.segment),'second')
        self.assertEqual(bridge.synthesize.call_count,1)
        self.assertEqual(bridge.align_mouth.call_count,2)

    def test_cache_is_bounded_and_has_no_transcript_metadata(self):
        reuse=SpeechReuse(self.root,self.config,self.cast);reuse.limit=0
        key=reuse.key(self.segment)
        reuse.put(key,audio(),[],'audio_envelope','x')
        self.assertIsNone(reuse.get(key))
        reuse.limit=8;reuse.put(key,audio(),[],'audio_envelope','x')
        metadata=(reuse.directory/(key+'.json')).read_text()
        self.assertNotIn(self.segment['text'],metadata)
        self.assertNotIn('scenario_id',metadata)

    def test_wav_validation_rejects_truncation_and_long_recordings(self):
        for data in (audio()[:-200],audio(46),b'not a wav'):
            with self.assertRaises((ValueError,wave.Error,EOFError)):wav_duration(data)

    def test_startup_openings_survive_worker_restart_without_regeneration(self):
        config=dict(self.config,conversation_language='cnr',recorded_speech_enabled=False)
        first=SimpleNamespace(config=config,voice_cast=self.cast,prepared_openings={},
            speech_reuse=SpeechReuse(self.root,config,self.cast),synthesize=Mock(return_value=audio()))
        HiggsVoice.prepare_openings(first)
        self.assertGreaterEqual(first.synthesize.call_count,4)
        second=SimpleNamespace(config=config,voice_cast=self.cast,prepared_openings={},
            speech_reuse=SpeechReuse(self.root,config,self.cast),
            synthesize=Mock(side_effect=AssertionError('Cached opening regenerated')))
        HiggsVoice.prepare_openings(second)
        second.synthesize.assert_not_called()
        self.assertEqual(first.prepared_openings,second.prepared_openings)

    def test_stream_keeps_ready_recorded_beat_and_still_appraises_and_generates(self):
        reuse=self.library();bridge=self.bridge(reuse)
        bridge.config['session_log_dir']=str(self.root/'sessions')
        self.cast.speakers['person_03']['anger']['mode']='sentences'
        bridge.voice_cast=self.cast
        bridge.appraise=Mock(return_value=dict(event='neutral',invites_detail=False,topic='difficulty'))
        bridge.generate=Mock(return_value=[dict(self.segment)])
        key=bridge.new_session('alex-earthquake')['session_id']
        turn=bridge.start_stream(key,'Pustite me da završim.')['turn_id']
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            status=bridge.poll_stream(key,turn)
            if status['done']:break
            time.sleep(.01)
        self.assertTrue(status['done']);self.assertFalse(status.get('error'))
        self.assertEqual(len(status['segments']),1)
        self.assertEqual(status['segments'][0]['text'],self.segment['text'])
        bridge.appraise.assert_called_once();bridge.generate.assert_called_once()
        bridge.synthesize.assert_not_called()
        bridge.finish_stream(key,turn,0,0,'test_without_playback')

    def test_enable_preserves_current_model_gpu_voice_and_language_settings(self):
        self.library()
        path=self.root/'services/config.local.json';path.parent.mkdir(parents=True,exist_ok=True)
        before=dict(tts_provider='higgs',dialogue_model='gemma-q8',llm_gpu_layers=36,
            higgs_quantization='bf16',conversation_language='cnr',llm_mtp=False)
        path.write_text(json.dumps(before),encoding='utf-8')
        spec=importlib.util.spec_from_file_location('enable_recorded',ROOT/'tools/enable-recorded-speech.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.enable(self.root),1)
        after=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual({k:after[k] for k in before},before)
        self.assertTrue(after['speech_cache_enabled']);self.assertTrue(after['recorded_speech_enabled'])
        backups=list((path.parent/'.runtime/config-backups').glob('*.json'))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text(encoding='utf-8')),before)

    def test_cancelled_turn_stops_before_alignment_or_cache_publication(self):
        reuse=SpeechReuse(self.root,self.config,self.cast);bridge=self.bridge(reuse)
        current=Mock(side_effect=StaleTurn())
        with self.assertRaises(StaleTurn):
            bridge.prepare_audio_segment(dict(self.segment),'cancelled',current)
        bridge.align_mouth.assert_not_called()
        self.assertIsNone(reuse.get(reuse.key(self.segment)))


if __name__=='__main__':unittest.main()
