# Conversation refinement and session memory

21 September 2026. Alex, Ivan, Nikola and Stefan share the patient conversation
policy and relationship state. Their original case facts remain unchanged. Alex
now has authored everyday tastes, gradual disclosure and boundaries; these are
marked as fictional additions in his instructor notes.

## Conversation behaviour

Ordinary conversation can use connected detail without high comfort. Sensitive
disclosure remains voluntary and gradual. Prompts distinguish accepting a useful
observation from accepting every interpretation, and accepting an apology from
instant forgiveness. Character-specific conversational styles help separate the
patients without making them always agreeable or always oppositional.

The typical target remains 20–60 spoken words, or 40–80 for elaboration within the
current ceiling. Narrow answers/refusals may be shorter. Pressure, attacks and
threats cannot unlock an elaboration budget even when the appraisal also labels
the utterance an open question. Profile writing instructions are excluded or
separated from speakable facts to reduce instruction echoing.

An obvious English-clause check can retry a Montenegrin draft before committing it
or synthesizing speech. It is conservative and does not detect every language
error, fix grammar or correct TTS accents. Generation has at most three attempts,
including language/length retries; repeated failure leaves session state unchanged.

## Memory design

`services/conversation_memory.py` implements **extractive retrieval**, not a model
generated biography or a second decision model. No extra inference call is needed.

- Keep the last 96 completed exchanges in this session, with at most 2,800
  characters from each speaker per exchange. Store text, turn number and authored
  appraisal categories; do not store audio or animation metadata in this archive.
- Retrieve up to eight exact excerpts (maximum 260 characters each), with a
  combined initial JSON budget of 1,800 characters. Ranking uses normalized lexical
  overlap, recent topic context, and limited name/correction, preference and apology
  signals. Weakly related candidates are omitted. This is not semantic embedding search.
- Keep speaker attribution and chronological turn IDs. Original case facts remain
  authoritative. Counsellor suggestions are not patient facts; an earlier generated
  mistake does not authorize a new symptom, relative or major event. New everyday
  preferences can persist without inventing a history to support them.
- Feed relevant excerpts into both appraisal and reply generation. When the real
  tokenizer reports a full context, remove older dialogue pairs and then lower-ranked
  excerpts, while reserving response space. Current input and authored instructions
  are retained. Retrieval itself can miss a relevant paraphrase or distant detail.
- Commit history, relationship and memory together only after the reply succeeds.
  Cancelled/failed turns cannot add facts. Reset, replacement and server shutdown
  clear live memory; it is not a cross-session patient record. Separate
  [automatic session logs](SESSION_LOGGING.md) preserve dialogue and response memory
  diagnostics on disk, but are not automatically loaded into later conversations.
- The browser export includes `memory.retained_turns`, `recalled` (retrieval
  candidates), and `in_reply_context` (the excerpts that survived the reply budget).
  This supports review without showing character instructions in the student flow.

The updated Unity player uses [sentence playback acknowledgements](SENTENCE_PLAYBACK.md):
only the confirmed complete sentences enter patient history/memory after an
interruption. Unfinished sentence words are unknown and marked as interrupted.
The text tester and legacy clients still commit the complete successful response.

## Validation

78 service tests pass. Coverage includes old-detail retrieval, corrected names,
attribution, exact-source excerpts, bounded memory, isolation/reset, cancellation,
failed synthesis, prompt budgets and mixed-language retry before committing state.

A live local-Qwen development run completed 37 non-opening replies across all four
characters (Ivan 16, Nikola 11, Stefan 5, Alex 5). Ordinary Ivan replies generally
expanded to 30–45 words, preferences were not automatically surrendered, and false
recovery claims were rejected. Stefan corrected a false injury/property-loss claim;
Alex corrected a false claim that his family died. These are inspected examples,
not universal behaviour guarantees or a blinded assessment.

The run exposed a context overflow in an earlier implementation, a speaker-confused
name recall, an embellished apology recollection and an English fragment. Context
budgeting, relevance filtering, attribution and language-retry changes followed.
Focused checks reconstructed prior sessions with the relevant original utterances
outside the four-turn dialogue window. They returned the corrected name Mirko in
two Montenegrin phrasings and English, remembered the disliked ingredient separately
from Ivan's taste, and rejected Alex's instant recovery in Montenegrin. A further
Nikola recheck recalled the actual taste insult and apology without adding the earlier
invented wording. See `services/.runtime/conversation-recall-probes*.json`.

The long run precedes the final attribution/language refinements; the focused
rechecks and unit tests cover those changes. Some awkward regional grammar,
metaphorical wording and incidental-detail drift still need human review.
The tests used text-only full-GPU Qwen; their timings are not BF16 speech/VR latency.
The normal 48-layer, BF16-compatible launch configuration is restored afterward.

Reproduce:

```powershell
./.venv/Scripts/python.exe -m unittest discover -s services
./.venv/Scripts/python.exe tools/evaluate_conversation_memory.py
./.venv/Scripts/python.exe tools/probe_conversation_recall.py
./.venv/Scripts/python.exe tools/probe_conversation_recall.py --scenario nikola-bereavement
```

Use a fresh conversation in the text tester. Introduce and correct a harmless
detail, discuss several other topics, then return to it. Review the response and
exported evidence separately: retrieving the right quote does not guarantee that
the dialogue model will interpret it correctly every time.
