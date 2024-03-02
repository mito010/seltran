from typing import Union
import logging
import spacy
from spacy.tokens import Token
from jamdict import Jamdict
import pysubs2

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)

SPACY_TO_JAMDICT_POS = {
    'NOUN': [
        'noun (common) (futsuumeishi)',
        'noun or participle which takes the aux. verb suru',
        'noun or verb acting prenominally',
        'noun, used as a prefix',
        'noun, used as a suffix',
        "nouns which may take the genitive case particle 'no'",
    ],
    'VERB': [
        'Godan verb - -aru special class',
        'Godan verb - Iku/Yuku special class',
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
        'Ichidan verb',
        'Ichidan verb - kureru special class',
        'Ichidan verb - zuru verb (alternative form of -jiru verbs)',
        'Kuru verb - special class',
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
}


class SelectiveTranslator(object):
    def __init__(self):
        self.translate_specs = {
            'pos': [
                'NOUN',
                'VERB',
                'PROPN',
                'ADJ',
            ],
            # Dictionary forms excluded from being translated
            'lemma': [
                'くる',
                'いう',
                'いる',
            ]
        }
        self.word_start_specs = {
            'pos': [
                'VERB',
                'NOUN',
            ]
        }
        self._tokenize = spacy.load("ja_ginza")
        self._jamdict = Jamdict()

    def _split_to_words(self, tokens: list[Token]) -> list[list[Token]]:
        words = []
        word: list[Token] = []
        for token in tokens:
            if token.pos_ in self.word_start_specs['pos']:
                if word:
                    words.append(word)
                word = []
            word.append(token)

        # Append last remaining word to the collected words
        return words + [word]

    def _translate_word(self, word: list[Token], top_matches=1) -> list[Union[str, Token]]:
        translated = []
        for token in word:
            if token.pos_ not in self.translate_specs['pos'] or token.lemma_ in self.translate_specs['lemma']:
                translated.append(token)
                logger.debug(
                    f'Token {token.text} ({token.pos_}) kept as is in word')
            else:
                definitions = self._jamdict.lookup(
                    token.lemma_, pos=SPACY_TO_JAMDICT_POS[token.pos_]).entries
                # print([sense.pos for d in definitions for sense in d])
                translations = [
                    str(gloss)
                    for t in definitions
                    for sense in t.senses
                    for gloss in sense.gloss
                ][:top_matches]
                translated_token = '/'.join(map(self._format_english,
                                            translations))
                translated.append(translated_token)
                logger.debug(f'Token {token.text} ({token.pos_}) translated to '
                             f'{translated_token}')
        return translated

    def _format_english(self, text: str) -> str:
        return '-'.join(text.strip().split()).upper()

    def _bake_translation(self, word: list[Union[str, Token]]) -> str:
        return (
            ''.join(
                (token.text if isinstance(token, Token) else token + '-')
                for token in word)
            .strip('-')
        )

    def translate(self, text: str) -> str:
        tokens = self._tokenize(text)
        words = self._split_to_words(tokens)
        translated_words = [self._translate_word(word) for word in words]
        return ' '.join(map(self._bake_translation, translated_words))
