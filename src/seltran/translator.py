from typing import Iterable, Union, Optional
import logging
import spacy
from spacy.tokens import Token
from jamdict import Jamdict
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

UNIVERSAL_TO_DICTIONARY_POS = {
    "NOUN": [
        "noun (common) (futsuumeishi)",
        "noun or participle which takes the aux. verb suru",
        "noun or verb acting prenominally",
        "noun, used as a prefix",
        "noun, used as a suffix",
        "nouns which may take the genitive case particle 'no'",
    ],
    "VERB": [
        "Godan verb - -aru special class",
        "Godan verb - Iku/Yuku special class",
        "Godan verb with 'bu' ending",
        "Godan verb with 'gu' ending",
        "Godan verb with 'ku' ending",
        "Godan verb with 'mu' ending",
        "Godan verb with 'nu' ending",
        "Godan verb with 'ru' ending",
        "Godan verb with 'ru' ending (irregular verb)",
        "Godan verb with 'su' ending",
        "Godan verb with 'tsu' ending",
        "Godan verb with 'u' ending",
        "Godan verb with 'u' ending (special class)",
        "Ichidan verb",
        "Ichidan verb - kureru special class",
        "Ichidan verb - zuru verb (alternative form of -jiru verbs)",
        "Kuru verb - special class",
        "Nidan verb (lower class) with 'dzu' ending (archaic)",
        "Nidan verb (lower class) with 'gu' ending (archaic)",
        "Nidan verb (lower class) with 'hu/fu' ending (archaic)",
        "Nidan verb (lower class) with 'ku' ending (archaic)",
        "Nidan verb (lower class) with 'mu' ending (archaic)",
        "Nidan verb (lower class) with 'nu' ending (archaic)",
        "Nidan verb (lower class) with 'ru' ending (archaic)",
        "Nidan verb (lower class) with 'su' ending (archaic)",
        "Nidan verb (lower class) with 'tsu' ending (archaic)",
        "Nidan verb (lower class) with 'u' ending and 'we' conjugation (archaic)",
        "Nidan verb (lower class) with 'yu' ending (archaic)",
        "Nidan verb (lower class) with 'zu' ending (archaic)",
        "Nidan verb (upper class) with 'bu' ending (archaic)",
        "Nidan verb (upper class) with 'gu' ending (archaic)",
        "Nidan verb (upper class) with 'hu/fu' ending (archaic)",
        "Nidan verb (upper class) with 'ku' ending (archaic)",
        "Nidan verb (upper class) with 'ru' ending (archaic)",
        "Nidan verb (upper class) with 'tsu' ending (archaic)",
        "Nidan verb (upper class) with 'yu' ending (archaic)",
        "Nidan verb with 'u' ending (archaic)",
        "Yodan verb with 'bu' ending (archaic)",
        "Yodan verb with 'gu' ending (archaic)",
        "Yodan verb with 'hu/fu' ending (archaic)",
        "Yodan verb with 'ku' ending (archaic)",
        "Yodan verb with 'mu' ending (archaic)",
        "Yodan verb with 'ru' ending (archaic)",
        "Yodan verb with 'su' ending (archaic)",
        "Yodan verb with 'tsu' ending (archaic)",
    ],
    "ADV": [
        "adverb (fukushi)",
        "adverb taking the 'to' particle",
    ],
}


def universal_to_dictionary_pos(pos: str) -> Optional[list[str]]:
    return UNIVERSAL_TO_DICTIONARY_POS.get(pos)


def is_text_japanese(text):
    # Unicode ranges for Japanese characters
    japanese_ranges = [
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x4E00, 0x9FFF),  # Common and Uncommon Kanji
        (0xF900, 0xFAFF),  # Compatibility Kanji
        (0xFF65, 0xFF9F),  # Halfwidth Katakana
        (0x31C0, 0x31EF),  # CJK Strokes
        (0x3200, 0x32FF),  # Enclosed CJK Letters and Months
        (0x3000, 0x303F),  # CJK Symbols and Punctuation
        (0x3130, 0x318F),  # Hangul Compatibility Jamo
        (0x3190, 0x319F),  # Kanbun
        (0x31A0, 0x31BF),  # Bopomofo Extended
        (0x31C0, 0x31EF),  # CJK Strokes
        (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
        (0x3200, 0x32FF),  # Enclosed CJK Letters and Months
        (0x3300, 0x33FF),  # CJK Compatibility
        (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
        (0xFE30, 0xFE4F),  # CJK Compatibility Forms
        (0xFF00, 0xFFEF),  # Halfwidth and Fullwidth Forms
        (0x20000, 0x2A6DF),  # Supplementary Ideographic Plane
        (0x2A700, 0x2B73F),  # Supplementary Ideographic Plane
        (0x2B740, 0x2B81F),  # Supplementary Ideographic Plane
        (0x2B820, 0x2CEAF),  # Supplementary Ideographic Plane
    ]

    for char in text:
        if not any(start <= ord(char) <= end for start, end in japanese_ranges):
            return False
    return True


class TokenFilter(object):
    def __init__(self, include_pos=[], exclude_lemmas=[], exclude_foreign=False):
        self.include_pos = include_pos
        self.exclude_lemmas = exclude_lemmas
        self.exclude_foreign = exclude_foreign

    def __call__(self, token: Token):
        return all(
            match(token)
            for match in [
                self._match_pos,
                self._match_lemma,
                self._match_foreign_chars,
            ]
        )

    def _match_foreign_chars(self, token: Token) -> bool:
        if self.exclude_foreign:
            return is_text_japanese(token.text)
        return True

    def _match_pos(self, token: Token) -> bool:
        return token.pos_ in self.include_pos

    def _match_lemma(self, token: Token) -> bool:
        return token.lemma_ not in self.exclude_lemmas


class SelectiveTranslator(object):
    def __init__(self):
        self.should_translate = TokenFilter(
            include_pos=[
                "NOUN",
                "VERB",
                "ADJ",
            ],
            exclude_foreign=True,
        )
        self.word_start_filter = TokenFilter(
            include_pos=[
                "VERB",
                "NOUN",
            ]
        )
        self.nlp = spacy.load("ja_ginza")
        self._jamdict = Jamdict()

    def _format_dictionary_gloss(self, text: str) -> str:
        text = self._format_english(text)

        match = re.search(r"^(TO-)?(?P<word>.+?)(-\(.*\))?$", text)
        if match is None:
            logger.error(f"Failed to parse dictionary gloss {text}")
            return "<ERROR_PARSING_DICTIONARY_GLOSS>"

        return match.group("word")

    def _format_english(self, text: str) -> str:
        return "-".join(text.strip().split()).upper()

    def get_dictionary_translations(self, token: Token) -> list[str]:
        dictionary_pos = universal_to_dictionary_pos(token.pos_)
        if dictionary_pos is None:
            logger.warning(
                f'Undefined dictionary POS for POS "{token.pos_}" (token "{token}")'
            )
            return []

        definitions = self._jamdict.lookup(
            token.lemma_, pos=dictionary_pos, strict_lookup=True
        ).entries

        return [
            self._format_dictionary_gloss(str(gloss))
            for t in definitions
            for sense in t.senses
            for gloss in sense.gloss
        ]

    def _split_to_words(self, tokens: Iterable[Token]) -> list[list[Token]]:
        words = []
        word: list[Token] = []
        for token in tokens:
            if self.word_start_filter(token):
                if word:
                    words.append(word)
                word = []
            word.append(token)

        # Append last remaining word to the collected words
        return words + [word]

    def _translate_dumb(self, tokens: list[Token]) -> str:
        """Selectively translate a sequence of tokens using a dumb selection algorithm for
        the best translation candidate for each token - simply take the first matching dictionary entry.

        :param list[Token] tokens: Token sequence to selectively translate
        :return str: Translated string containing all tokens
        """
        translated = []
        prepend_hyphen = False
        for token in tokens:
            if prepend_hyphen:
                translated.append("-")

            if not self.should_translate(token):
                translated.append(token.text_with_ws)
                prepend_hyphen = False
                logger.debug(f"Token {token.text.strip()} ({token.pos_}) kept as is")
                continue

            translations = self.get_dictionary_translations(token)
            if not translations:
                translated.append(token.text_with_ws)
                prepend_hyphen = False
                logger.warning(
                    f'No definitions found for token "{token.text.strip()}" ({token.pos_}, dict. form {token.lemma_}), token kept as is'
                )
                continue
            else:
                translated.append(translations[0])
                prepend_hyphen = True
                logger.debug(
                    f"Token {token.text.strip()} ({token.pos_}) translated to {translations[0]}"
                )
                continue

        return "".join(translated)

    def translate_dumb(self, text: str) -> str:
        tokens = self.nlp(text)
        words = self._split_to_words(tokens)
        translated_words = [self._translate_dumb(word) for word in words]
        return " ".join(translated_words)
