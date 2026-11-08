"""Select reversible hardware profiles without editing the voice recordings."""
import argparse
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
PROFILES={
    'quality':dict(higgs_quantization='bf16',higgs_allow_quantized_cast=False,llm_gpu_layers=32,
                   llm_batch_size=256,llm_ubatch_size=128,llm_mtp=False,
                   llm_ordinary_word_limit=None,stt_beam_size=5,higgs_fast_decode=False,higgs_sentence_streaming=False,
                   higgs_release_unused_vram=False,llm_cache_slots=True),
    'fast-clone':dict(higgs_quantization='nf4',higgs_allow_quantized_cast=True,llm_gpu_layers=99,
                     llm_batch_size=512,llm_ubatch_size=256,llm_mtp=False),
    'int8-clone':dict(higgs_quantization='int8',higgs_allow_quantized_cast=True,llm_gpu_layers=99,
                     llm_batch_size=256,llm_ubatch_size=128,llm_mtp=False),
    'vr-friendly':dict(llm_batch_size=256,llm_ubatch_size=128,llm_threads=8),
    'throughput':dict(llm_batch_size=512,llm_ubatch_size=256,llm_threads=8),
    'mtp-on':dict(llm_mtp=True,llm_mtp_tokens=2),
    'mtp-off':dict(llm_mtp=False),
    'latency-bf16':dict(higgs_quantization='bf16',higgs_allow_quantized_cast=False,llm_gpu_layers=99,
        llm_batch_size=256,llm_ubatch_size=128,llm_threads=8,llm_mtp=False,
        llm_cache_slots=True,llm_stable_prefix=True,llm_compact_delivery=True,
        llm_short_replies=True,llm_ordinary_word_limit=18,llm_max_tokens=384,
        llm_flash_attention=True,llm_kv_cache_type='q8_0',
        higgs_fast_decode=True,higgs_sentence_streaming=True,stt_beam_size=1,
        speech_cache_enabled=True,recorded_speech_enabled=True,
        tts_provider='higgs',conversation_language='cnr',
        stt_provider='faster-whisper',stt_model='.cache/whisper/large-v3-turbo',
        stt_language='sr',stt_output_script='latin',
        stt_initial_prompt='Razgovor na crnogorskom jeziku, latinicom.',
        stt_condition_on_previous_text=False),
    'audio-envelope':dict(lip_sync_provider='audio_envelope'),
    'rhubarb':dict(lip_sync_provider='rhubarb'),
    'sentence-start':dict(higgs_sentence_streaming=True),
    'approved-phrasing':dict(higgs_sentence_streaming=False),
}
PROFILES['q8-gpu-bf16']=dict(PROFILES['latency-bf16'],llm_batch_size=128,llm_ubatch_size=64,
    llm_cache_slots=False,higgs_release_unused_vram=True,llm_context_tokens=4096)
MODEL_PROFILES={'quality':'gemma-q8','fast-clone':'gemma-q8','int8-clone':'gemma-q8',
                'latency-bf16':'gemma','q8-gpu-bf16':'gemma-q8'}

def update(path, profile):
    original=path.read_bytes()
    config=json.loads(original.decode('utf-8-sig'))
    config.update(PROFILES[profile])
    catalog=json.loads((ROOT/'services/dialogue-models.json').read_text(encoding='utf-8'))
    if profile in MODEL_PROFILES:
        model=next(m for m in catalog['models'] if m['id']==MODEL_PROFILES[profile])
        if profile=='latency-bf16' and not (ROOT/model['model_path']).is_file():
            raise ValueError('Gemma QAT Q4 is not installed. Choose 6 in PC Settings.cmd to download it, then apply latency-bf16.')
        config.update(dialogue_model=model['id'],hardware_preset='',llm_model_path=model['model_path'])
    model=next((m for m in catalog['models'] if m['id']==config.get('dialogue_model')),None)
    if config.get('llm_mtp') and (not model or not model.get('draft_path') or not (ROOT/model['draft_path']).is_file()):
        raise ValueError('Matching MTP weights are unavailable for the selected model. Keep MTP off or install its matching draft.')
    backup=ROOT/'services/.runtime/config-backups'/f'optimization-{time.time_ns()}.json'
    backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(original)
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
    return config

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile',choices=PROFILES)
    parser.add_argument('--config',type=Path,default=ROOT/'services/config.local.json')
    args=parser.parse_args()
    config=update(args.config,args.profile)
    speech=config.get('tts_provider','unknown')
    if speech=='higgs':speech+=' '+config.get('higgs_quantization','bf16')
    print('Selected',args.profile,'; dialogue:',config.get('dialogue_model'),'; speech:',speech,
          '; GPU layers:',config.get('llm_gpu_layers','catalog default'),'; MTP:',config.get('llm_mtp',False))
    if config.get('tts_provider')=='higgs' and config.get('higgs_quantization','bf16')!='bf16':print('Precision comparison: listen to all four voices before using this profile for training.')
    if args.profile=='latency-bf16':print('Optional QAT Q4 dialogue, BF16 voices, sentence delivery and greedy STT. Listen for phrasing/recognition changes and validate <=14s on the 4090; latency is not guaranteed.')
    if args.profile=='q8-gpu-bf16':print('Experimental full-GPU Q8 + BF16: tight on 24 GB. Test with the game open, inspect shared GPU memory and later gaps. Revert if it spills or fails to load.')

if __name__=='__main__':main()
