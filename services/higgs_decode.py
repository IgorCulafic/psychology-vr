"""Optional transfer reduction for the pinned Transformers Higgs port.

The sampling algorithm, reference, precision and stopping rules stay upstream's.
Derived from generate_speech in multimodalart/higgs-audio-v3-tts-4b-transformers,
revision 30f01593ee6a12efa586c92455afe4b76e45095d. No model-cache files are edited.
The upstream Higgs license is retained in services/licenses/HIGGS-AUDIO-V3.txt.
"""
import importlib
import time


class HiggsDecoder:
    def __init__(self, model):
        self.model = model
        self.port = importlib.import_module(type(model).__module__)
        required = ('apply_delay_pattern', 'reverse_delay_pattern', '_SamplerState', '_sampler_step')
        if not all(hasattr(self.port, name) for name in required):
            raise ValueError('The optimized decoder requires the pinned Higgs Transformers port')
        self.last_metrics = {}

    def generate(self, text, tokenizer, *, reference_codes=None, reference_text=None,
                 max_new_tokens=900, temperature=1., top_p=None, top_k=None):
        import torch
        model = self.model
        port = self.port
        start = time.perf_counter()
        with torch.inference_mode():
            delayed_ref = (None if reference_codes is None else
                           port.apply_delay_pattern(reference_codes.to(torch.long)))
            prompt = model._build_prompt_ids(tokenizer, text,
                num_ref_tokens=0 if delayed_ref is None else delayed_ref.shape[0],
                reference_text=reference_text)
            embeds = model._prefill_embeds(prompt, delayed_ref)
            out = model.model(inputs_embeds=embeds, use_cache=True)
            past = out.past_key_values
            hidden = out.last_hidden_state[:, -1, :]
            # Allocate positions once, rather than constructing a GPU tensor for
            # every frame. Rows remain on the GPU until the existing codec needs
            # them; the upstream loop copies every eight-codebook row to the CPU.
            positions = torch.arange(len(prompt), len(prompt) + max_new_tokens, device=model.device)
            state = port._SamplerState(num_codebooks=model.num_codebooks)
            rows = []
            if model.device.type == 'cuda':
                torch.cuda.synchronize(model.device)
            prefill_end = time.perf_counter()
            for index in range(max_new_tokens):
                logits = model.audio_head(hidden).to(torch.float32)[0]
                codes = port._sampler_step(logits, state,
                    temperature=temperature, top_p=top_p, top_k=top_k)
                if state.generation_done:
                    break
                rows.append(codes)
                step = model.audio_embedding(codes.unsqueeze(0)).unsqueeze(1)
                out = model.model(inputs_embeds=step.to(embeds.dtype), past_key_values=past,
                                  use_cache=True, cache_position=positions[index:index+1])
                past = out.past_key_values
                hidden = out.last_hidden_state[:, -1, :]
            if model.device.type == 'cuda':
                torch.cuda.synchronize(model.device)
            decode_end = time.perf_counter()
            if len(rows) < model.num_codebooks:
                audio = torch.zeros(0, dtype=torch.float32)
            else:
                audio = model._decode_codes(port.reverse_delay_pattern(torch.stack(rows)))
            self.last_metrics = dict(frames=len(rows), stopped=bool(state.generation_done),
                prefill_seconds=round(prefill_end-start, 4),
                decode_seconds=round(decode_end-prefill_end, 4),
                codec_seconds=round(time.perf_counter()-decode_end, 4))
            return audio
