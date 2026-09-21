"""Whisper language selection and lossless regional script normalization.

Script conversion is not accent correction: preserve words, negations and diacritics.
"""
import re

CYRILLIC = dict(zip('абвгдђежзијклљмнњопрстћуфхцчџш',
                   ('a','b','v','g','d','đ','e','ž','z','i','j','k','l','lj','m','n',
                    'nj','o','p','r','s','t','ć','u','f','h','c','č','dž','š')))


def whisper_language(code):
    # Whisper has no cnr token; sr is the explicit regional approximation.
    return None if code == 'auto' else 'sr' if code in ('cnr', 'me') else code


def obvious_english_leak(text):
    """Conservative retry signal for English clauses, not a language classifier.

    Ignore a few loanwords/titles; require several common English function words
    or an unmistakable clause. Regional grammar/accent still needs human review.
    """
    words=re.findall(r"[a-z]+",text.lower())
    markers=set(words) & set('the that this with because still again your you have been would could myself scared'.split())
    return len(markers)>=3 and sum(w in markers for w in words)>=len(words)*.2


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
