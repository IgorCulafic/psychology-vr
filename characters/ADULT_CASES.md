# Adult patient cases

Adapted on 21 September 2026 from the supplied `Simulacija_ENG.docx`. Section A already corresponds to Alex and was left alone. Sections B, C and D are implemented below; the child option in B is excluded. The document's cooperative demonstration dialogue is not used as a script or an answer key. In particular, its psychologist explanations, promises and proposed techniques are not patient knowledge.

Names, adult ages, occupations and timeline anchors below are **fictional authoring choices**, not facts supplied by the colleague. They make ordinary questions answerable consistently. All three currently use the existing male jumper model and shared configured BF16 voice. Distinct appearances and voice references can be assigned separately.

| Character | Source | Fixed starting situation | Conversational tendency |
|---|---|---|---|
| Nikola, 42 | B: loss of a close family member | Electrician; his father Milan died after an unspecified illness six weeks ago | Quiet, guarded, sometimes blunt. Sadness does not imply constant crying. Anger at his father and guilt about that anger are harder to disclose. |
| Stefan, 31 | C: witness of a fire | Shop worker; witnessed a nearby building fire from outside five days ago; his own home and body were unharmed | Alert and concrete; unsure he deserves help. Gradually reveals reminders, avoidance and helplessness. Corrects claims that he was burned or lost his own home. |
| Ivan, 39 | D: work-related exhaustion | Administrative worker; increasing workload over eight months, fatigue, mistakes and difficulty resting | Terse, practical and sometimes defensive. Wants to function, worries about letting others down, and does not automatically accept quitting or a holiday as an answer. |

## Openings

- Nikola: “Skoro da nijesam došao. Ne znam odakle da počnem.”
- Stefan: “Nijesam ni bio povrijeđen. Ne znam zašto još ne mogu da se smirim.”
- Ivan: “Stalno sam umoran. Imao sam slobodan vikend, a kao da nijesam odmorio.”

English openings and facts are also authored; the active configuration uses Montenegrin. The opening deliberately avoids a complete symptom list or personal history. A direct, relevant question can uncover an ordinary fact without a long trust-building sequence. More sensitive feelings emerge through relevant, respectful follow-up; pressure can make the character pull back. This is prompt-guided, not a deterministic disclosure state machine.

## Shared behavior

The new `patient_v1` policy asks for one or two short sentences, usually 10–35 words, with a 45-word target ceiling across the reply. It discourages long biography dumps even if requested, automatic agreement, clinical self-diagnosis, therapy instructions, grading students, and adopting the psychologist role. Characters can reject a wrong premise, doubt advice, accept a modest suggestion, or ask a question. They are not instructed to be hostile or refuse everything.

They know how they feel and what happened to them; they do not know a clinical formulation or a cure. Small relief is compatible with an ongoing problem. They must not invent new trauma, symptoms or relationships to justify an emotional cue. Existing validated emotion, gaze, gesture, pause and voice controls apply to these characters as they do to Alex.

Instructor provenance and formulation live in `author_notes` and are omitted from the model prompt. This is separate from the existing **Hide descriptions** menu option, which conceals the picker/session summary for students. The source document is not copied into the repository.

## Verification and limits

- 49 backend tests pass, including adult ages, matching catalog/profile identities, private-note omission, character isolation, localized openings, switching and resets.
- The Unity Windows build synchronizes all four entries. The description-hiding preview passes and its rendered picker shows Alex, Nikola, Stefan and Ivan.
- Local Qwen tests cover a five-turn conversation per new character plus diagnosis/cure requests, role-switch attempts and instant-recovery assertions: 24 replies per pass. The second full pass contained 9–21 words per reply and no English switch, after an earlier mixed-language Ivan response prompted stronger language guidance.
- Twelve additional probes checked obedience, a narrow everyday question, a reasonable suggestion, and recovery. The characters were able to decline blanket obedience while accepting a slower conversation.
- Nikola initially produced a contradictory recovery reply. A character-specific example about ongoing loss fixed that prompt and a differently worded recovery claim on targeted recheck. These inspected cases are development tests, not an independent guarantee.

Occasional awkward grammar, unnatural wording, and invented incidental details remain. Brevity, disclosure and resistance are prompt instructions, not hard semantic guarantees. Clinical insight/diagnosis requests were declined in the tested examples; this is not a claim that the model can never slip. Review fresh conversations with the colleague before relying on these as teaching cases. No new per-character voice or physical headset acceptance test was done. The text-only evaluation ran Qwen fully on GPU with speech disabled; its speed is not the normal BF16 pipeline's latency.

Re-run `tools/evaluate_patient_characters.py` with Qwen available on port 8087. Detailed local transcripts are under `services/.runtime/adult-patients*.json`; the nonprivate summary is `docs/generated/adult-patients-validation.json`. Restart the bridge to load profile changes. Normal launches retain the saved BF16 voice and 48-layer Qwen setting.
