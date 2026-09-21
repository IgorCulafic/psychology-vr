"""Append-only local session journals. Every accepted event is flushed to disk.

One JSON object per line allows recovery of earlier events after a crash. Journals
record generated responses, not a claim that playback was heard in full.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import uuid


class SessionLogError(ValueError):
    pass


def readable(record):
    header=f"\n[{record['timestamp']}] {record['event']}"
    if record.get('request_id'):header+=' · '+record['request_id'][:8]
    if record['event']=='session_started':
        return header+f"\n{record['character']} · {record['language']} · {record['source']}\n{record['playback_tracking']}\n"
    if record['event']=='turn_started':
        return header+('\nOpening requested\n' if record['opening'] else '\nStudent: '+record['text']+'\n')
    if record['event']=='turn_completed':
        response=record['response']
        lines=[header]
        for segment in response['segments']:
            lines += ['Patient: '+segment['text'],
                      f"  Emotion: {segment['emotion']} ({segment['intensity']:.2f}); gesture: {segment['gesture']}; voice: {segment['voice_style']}"]
        state=response.get('relationship')
        if state:lines.append(f"  Comfort: {state['comfort']}; trust: {state['trust']}; distress: {state['distress']}; state: {state['status']}")
        lines.append(f"  Response prepared in {response['total_ms']} ms. Playback not confirmed.")
        if record.get('session_ended'):lines.append('  Patient ended the session.')
        return '\n'.join(lines)+'\n'
    if record['event']=='segment_ready':
        segment=record['segment']
        return header+f"\nSentence {record['index']+1} prepared at {record['ready_ms']} ms (not yet confirmed played).\n{segment['text']}\n"
    if record['event']=='playback_finished':
        return header+f"\nPlayback: {record['reason']}; {record['completed_count']} complete sentences.\nConfirmed played: {record['confirmed_text']}\nUnfinished sentence playback: {record['partial_seconds']:.2f}s; its exact words are not inferred.\n"
    return header+'\n'+json.dumps({k:v for k,v in record.items() if k not in ('schema_version','timestamp','archive_id','session_id','event')},ensure_ascii=False)+'\n'


class SessionLog:
    def __init__(self, root, config, session_id, scenario_id, character):
        now=datetime.now(timezone.utc)
        directory=Path(config.get('session_log_dir', 'logs/sessions'))
        if not directory.is_absolute(): directory=Path(root)/directory
        self.archive_id=uuid.uuid4().hex
        self.session_id=session_id
        self.lock=threading.Lock()
        self.path=directory/now.strftime('%Y-%m-%d')/f'{now:%H%M%S}-{scenario_id}-{self.archive_id}.jsonl'
        self.append('session_started', scenario_id=scenario_id, character=character,
                    language=config.get('conversation_language','en'),
                    source=config.get('session_source','vr_bridge'),
                    dialogue_provider=config.get('dialogue_provider'),
                    model=config.get('llm_model'), tts_provider=config.get('tts_provider'),
                    playback_tracking='Generated replies are recorded; actual playback/hearing is not confirmed.')

    def append(self, event, **fields):
        record=dict(schema_version=1, timestamp=datetime.now(timezone.utc).isoformat(),
                    archive_id=self.archive_id, session_id=self.session_id, event=event, **fields)
        line=(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
        try:
            with self.lock:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                # Open/close each append: nothing depends on an end-of-session save.
                with self.path.open('ab') as handle:
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Readable companion for instructors; JSONL remains the full record.
                with self.path.with_suffix('.txt').open('ab') as handle:
                    handle.write(readable(record).encode('utf-8'))
                    handle.flush()
                    os.fsync(handle.fileno())
        except OSError as exc:
            raise SessionLogError('Could not save the session log. Check available disk space and folder permissions before continuing.') from exc


def read_records(path):
    """Recover complete records; a crash may leave only the last line incomplete."""
    lines=Path(path).read_bytes().splitlines()
    result=[]
    for index,line in enumerate(lines):
        if not line.strip():continue
        try:result.append(json.loads(line))
        except (ValueError,UnicodeDecodeError):
            if index!=len(lines)-1:raise ValueError('Damaged session log before its last record')
    return result
