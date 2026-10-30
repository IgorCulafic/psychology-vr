"""Export a consistent snapshot of one local session's readable and JSONL logs."""
import os
from pathlib import Path
import tempfile
import uuid
import zipfile


def export_session(root,bridge,session_id):
    root=Path(root)
    # Reset/replacement uses the bridge lock, and journal appends hold its lock
    # across both writes. Snapshot the pair before doing ZIP compression.
    with bridge.lock:
        session=bridge.sessions[session_id]
        journal=session.journal
        if journal is None:raise ValueError('This session has no saved log')
        with journal.lock:
            paths=(journal.path,journal.path.with_suffix('.txt'))
            entries=[(path.name,path.read_bytes()) for path in paths]
            stem=journal.path.stem if session.student_name else 'student-'+journal.path.stem
            stem=stem.encode('utf-16-le')[:192].decode('utf-16-le',errors='ignore').rstrip('-_')
    directory=root/'logs/exports'
    directory.mkdir(parents=True,exist_ok=True)
    filename=f'conversation-{stem}-{uuid.uuid4().hex}.zip'
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=directory,prefix='.session-export-',suffix='.tmp',delete=False) as handle:
            temporary=Path(handle.name)
            with zipfile.ZipFile(handle,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
                for name,content in entries:bundle.writestr(name,content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(directory/filename)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return {'ok':True,'filename':filename,'directory':'logs/exports'}
