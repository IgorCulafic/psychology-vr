"""Sentence audio delivery with explicit, monotonic playback acknowledgements.

Generation is validated before publishing speech. Only client-confirmed complete
sentences enter patient history; partial audio is recorded without guessing words.
"""
from copy import deepcopy
import json
import math
import re
import threading
import time
import uuid

from conversation_memory import remember
from performance_contract import FIELDS


def sentence_segments(segments):
    result=[]
    for segment in segments:
        # Avoid decimals, initials and common regional abbreviations. Keep quotes
        # with their sentence; split only before an uppercase letter or digit.
        text=segment['text']
        parts=re.split(r'(?<=[.!?])\s+(?=[A-ZČĆŽŠĐА-Я0-9])',text)
        merged=[]
        for part in parts:
            if merged and re.search(r'(?:\b(?:dr|prof|mr|g|br|itd|npr)|\b[A-ZČĆŽŠĐ])\.$',merged[-1],re.I):
                merged[-1]+=' '+part
            else:merged.append(part)
        # A delivery beat retains one cue, rather than repeating it per sentence.
        cue=min(len(merged)-1,int(segment['gesture_at']*len(merged)))
        for index,part in enumerate(merged):
            item=dict(segment,text=part)
            if index: item.update(pause_before_seconds=0.,transition_seconds=max(.65,item['transition_seconds']))
            if index!=len(merged)-1:item['hold_after_seconds']=0.
            if index!=cue:item['gesture']='none'
            else:item['gesture_at']=0.
            result.append(item)
    return result


class StreamingTurns:
    def start_stream(self,key,text,opening=False,expected_generation=None):
        if not isinstance(text,str) or len(text)>2000 or (not opening and not text.strip()):
            raise ValueError('Enter 1–2000 characters')
        with self.lock:
            if getattr(self, 'models', None) and self.models.switching:
                raise ValueError('The dialogue model is loading. Please wait.')
            session=self.sessions[key]
            if expected_generation is not None and (isinstance(expected_generation,bool) or not isinstance(expected_generation,int) or expected_generation!=session.generation):
                raise ValueError('Playback generation expired; start a fresh turn')
            if session.busy or (session.stream and not session.stream['closed']):
                raise ValueError('A reply is already in progress')
            if session.relationship and session.relationship['status']=='ended':
                raise ValueError('This patient ended the session. Start a new conversation.')
            job=dict(turn_id=uuid.uuid4().hex,generation=session.generation,segments=[],
                     completed_count=0,partial_seconds=0.,done=False,closed=False,error=None,
                     text=text.strip(),opening=opening,relationship=deepcopy(session.relationship),
                     started=time.perf_counter(),first_audio_ms=None)
            session.stream=job
        def work():
            try:self.turn(key,text,opening,stream=job)
            except Exception as exc:
                with self.lock:
                    job['error']='Reply preparation stopped ('+type(exc).__name__+').'
            finally:
                with self.lock:job['done']=True
        threading.Thread(target=work,daemon=True).start()
        return {'turn_id':job['turn_id'],'session_id':key}

    def stream_job(self,key,turn_id):
        session=self.sessions[key]
        job=session.stream
        if not job or job['turn_id']!=turn_id:raise ValueError('Expired playback turn')
        return session,job

    def poll_stream(self,key,turn_id):
        with self.lock:
            session,job=self.stream_job(key,turn_id)
            return dict(turn_id=turn_id,session_id=key,segments=deepcopy(job['segments']),
                        done=job['done'],closed=job['closed'],error=job['error'],
                        relationship=deepcopy(job['relationship']),first_audio_ms=job['first_audio_ms'])

    def acknowledge(self,key,turn_id,count,partial_seconds=0.):
        with self.lock:
            session,job=self.stream_job(key,turn_id)
            if isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=len(job['segments']):
                raise ValueError('Invalid playback prefix')
            if isinstance(partial_seconds,bool) or not isinstance(partial_seconds,(int,float)) or not math.isfinite(partial_seconds) or not 0<=partial_seconds<=45:
                raise ValueError('Invalid playback progress')
            if job['closed']:return {'ok':True,'closed':True}
            if count<job['completed_count']:return {'ok':True}  # Late network update.
            partial_seconds=min(partial_seconds,job['segments'][count].get('audio_duration_seconds',45)) if count<len(job['segments']) else 0.
            if count==job['completed_count']:partial_seconds=max(partial_seconds,job['partial_seconds'])
            if count!=job['completed_count'] or partial_seconds!=job['partial_seconds']:
                session.journal.append('playback_progress',turn_id=turn_id,completed_count=count,
                                       partial_seconds=partial_seconds,source='client_audio_clock')
                job.update(completed_count=count,partial_seconds=partial_seconds)
            return {'ok':True}

    def finish_stream(self,key,turn_id,count,partial_seconds=0.,reason='completed'):
        with self.lock:
            session,job=self.stream_job(key,turn_id)
            self.acknowledge(key,turn_id,count,partial_seconds)
            if job['closed']:return {'ok':True,'relationship':session.relationship,'generation':session.generation}
            if reason=='completed' and (not job['done'] or job['error'] or job['completed_count']!=len(job['segments'])):
                raise ValueError('Speech is not complete; interrupt instead')
            heard=deepcopy(job['segments'][:job['completed_count']])
            session.journal.append('playback_finished',turn_id=turn_id,reason=reason,
                completed_count=len(heard),partial_seconds=job['partial_seconds'],
                confirmed_text=' '.join(s['text'] for s in heard),
                partial_sentence_words_unknown=job['partial_seconds']>0)
            # The student's accepted utterance survives even when no answer was heard.
            history_segments=[{k:s[k] for k in FIELDS} for s in heard]
            if job['partial_seconds']>0 or not heard:
                marker='[Reply interrupted during an unfinished sentence; do not assume its words were heard.]' if job['partial_seconds']>0 else '[No reply was played.]'
                history_segments.append({'text':marker})
            session.history += [{'role':'user','content':'[Start the session]' if job['opening'] else job['text']},
                                {'role':'assistant','content':json.dumps({'segments':history_segments})}]
            session.history=session.history[-12:]
            session.relationship=deepcopy(job['relationship'])
            session.memory=remember(session.memory,job['text'],heard,session.relationship,job['opening'])
            if heard:
                session.emotion=heard[-1]['emotion'];session.intensity=heard[-1]['intensity']
                session.recent_gestures=(session.recent_gestures+[s['gesture'] for s in heard])[-6:]
            job['closed']=True
            session.generation+=1  # Also invalidates a worker still synthesizing.
            session.busy=False
            return {'ok':True,'relationship':session.relationship,'generation':session.generation}
