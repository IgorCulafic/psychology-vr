"""Whisper language selection and lossless regional script normalization.

Script conversion is not accent correction: preserve words, negations and diacritics.
"""
import re
import unicodedata


def preferred_dialogue_wording(text):
    """Apply the project's spoken-word preference only to generated dialogue.

    Callers must not apply this to STT input or recorded reference transcripts.
    Keep all other dialect forms and the distinct č/ć characters intact.
    """
    def replace(match):
        source = match.group()
        target = 'нисам' if source[0].lower() == 'н' else 'nisam'
        return target.upper() if source.isupper() else target.capitalize() if source[0].isupper() else target
    return re.sub(r'(?<!\w)(?:nijesam|нијесам)(?!\w)', replace, text, flags=re.I)

CYRILLIC = dict(zip('абвгдђежзијклљмнњопрстћуфхцчџш',
                   ('a','b','v','g','d','đ','e','ž','z','i','j','k','l','lj','m','n',
                    'nj','o','p','r','s','t','ć','u','f','h','c','č','dž','š')))


def whisper_language(code):
    # Whisper has no cnr token; Bosnian (bs) is the closest supported regional language.
    return None if code == 'auto' else 'bs' if code in ('cnr', 'me') else code


def obvious_english_leak(text):
    """Conservative retry signal for English clauses, not a language classifier.

    Ignore a few loanwords/titles; require several common English function words
    or an unmistakable clause. Regional grammar/accent still needs human review.
    """
    words=re.findall(r"[a-z]+",text.lower())
    markers=set(words) & set('the that this with because still again your you have been would could myself scared'.split())
    return len(markers)>=3 and sum(w in markers for w in words)>=len(words)*.2


LATIN_SCRIPT_LANGUAGES = ('cnr', 'me', 'bs', 'hr', 'en')


def _foreign_letter(char):
    # Letters only: punctuation, digits and Latin diacritics (č, ć, đ, š, ž) are allowed.
    return unicodedata.category(char).startswith('L') and 'LATIN' not in unicodedata.name(char, '')


def foreign_script_leak(text):
    """True when a Latin-script reply contains letters from another script (e.g. a stray 量)."""
    return any(_foreign_letter(char) for char in text)


def strip_foreign_script(text):
    """Last-resort cleanup after retries: drop non-Latin letters, keep every Latin word intact."""
    cleaned = ''.join(char for char in text if not _foreign_letter(char))
    return re.sub(r'[ \t]{2,}', ' ', re.sub(r'\s+([,.!?;:])', r'\1', cleaned)).strip()


def latin_script(text):
    def word(match):
        value = match.group()
        all_caps = value.isupper()
        result = []
        for char in value:
            replacement = CYRILLIC.get(char.lower())
            if replacement is None:
                result.append(char)
            elif char.isupper():
                result.append(replacement.upper() if all_caps else replacement.capitalize())
            else:
                result.append(replacement)
        return ''.join(result)
    return re.sub(r'[^\W\d_]+', word, text)
