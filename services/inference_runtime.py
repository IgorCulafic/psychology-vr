"""Shared, validated llama.cpp launch settings for launches and model switches."""
import json
import hashlib
from pathlib import Path

def config_signature(config):
    return hashlib.sha256(json.dumps({k:v for k,v in config.items() if not k.startswith('_')},
        sort_keys=True,ensure_ascii=True).encode()).hexdigest()

def bounded(config,key,default,low,high):
    value=config.get(key,default)
    if isinstance(value,bool) or not isinstance(value,int) or not low<=value<=high:
        raise ValueError(f'{key} must be an integer between {low} and {high}')
    return value

def server_arguments(root,config,model):
    root=Path(root).resolve()
    slots=2 if config.get('llm_cache_slots',False) else 1
    context=bounded(config,'llm_context_tokens',4096,2048,32768)
    batch=bounded(config,'llm_batch_size',256,32,2048)
    ubatch=bounded(config,'llm_ubatch_size',128,32,batch)
    threads=bounded(config,'llm_threads',8,1,32)
    # Catalog sets the portable model choice; explicit hardware settings can
    # deliberately lower the layer count for a BF16/memory comparison.
    layers=bounded(config,'llm_gpu_layers',model['gpu_layers'],0,999)
    result=['--model',str(root/model['model_path']),'--alias',config.get('llm_model','alex-qwen'),
        '--host','127.0.0.1','--port','8087','--ctx-size',str(context*slots),
        '--parallel',str(slots),'--n-gpu-layers',str(layers),
        '--batch-size',str(batch),'--ubatch-size',str(ubatch),
        '--threads',str(threads),'--threads-batch',str(threads),
        '--jinja','--reasoning','off']
    cache=config.get('llm_kv_cache_type','f16')
    if cache not in ('f16','q8_0','q4_0'):raise ValueError('Invalid llm_kv_cache_type')
    if config.get('llm_flash_attention',False):result+=['--flash-attn','on']
    if cache!='f16':
        if not config.get('llm_flash_attention',False):raise ValueError('Quantized KV requires Flash Attention')
        result+=['--cache-type-k',cache,'--cache-type-v',cache]
    if config.get('llm_mtp',False):
        draft=model.get('draft_path')
        if not draft or not (root/draft).is_file():raise ValueError('Install the matching MTP draft model first')
        result+=['--spec-type','draft-mtp','--model-draft',str(root/draft),
            '--spec-draft-ngl','99','--spec-draft-n-max',str(bounded(config,'llm_mtp_tokens',2,1,4))]
    else:result+=['--spec-type','none']
    return result

def launch_description(root,config):
    catalog=json.loads((Path(root)/'services/dialogue-models.json').read_text(encoding='utf-8'))['models']
    model=next((m for m in catalog if m['id']==config.get('dialogue_model')),None)
    if model is None:
        model=dict(model_path=config['llm_model_path'],server_path='.tools/llama/llama-server.exe',gpu_layers=99)
    return dict(executable=str(Path(root).resolve()/model['server_path']),
                arguments=server_arguments(root,config,model),config_signature=config_signature(config))

if __name__=='__main__':
    import sys
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    print(json.dumps(launch_description(Path(__file__).resolve().parents[1],config)))
