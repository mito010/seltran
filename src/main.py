from typing import Union
import spacy
from jamdict import Jamdict
from spacy.tokens import Token


class Translator(object):
    def __init__(self):
        self.translate_specs = {
            'pos': [
                'NOUN',
                'VERB',
                'PROPN',
            ],
            # Dictionary forms excluded from being translated
            'lemma': [
                'くる',
                'いう',
            ]
        }
        self.word_start_specs = {
            'pos': [
                'VERB',
                'NOUN',
            ]
        }
        self._tokenize = spacy.load("ja_core_news_sm")
        self._jamdict = Jamdict()

    def _split_to_words(self, tokens: list) -> list[list[Token]]:
        words = []
        word = []
        for token in tokens:
            # print(f'{token.text}, {token.lemma_}, {token.pos_}')
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
                continue
            definitions = self._jamdict.lookup(token.lemma_).entries
            translations = [str(
                gloss) for t in definitions for sense in t.senses for gloss in sense.gloss][:top_matches]
            translated_token = '/'.join(map(self._format_english,
                                        translations))
            translated.append(translated_token)
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
        # print(words)
        translated_words = [self._translate_word(word) for word in words]
        # print(translated_words)
        return ' '.join(map(self._bake_translation, translated_words))


def main():
    text = '王都が見えてきたね'
    text = '勇者一行の凱旋(がいせん)です'
    text = '''魔王を倒したからといって終わりじゃない'''
    translator = Translator()
    output = translator.translate(text)
    print(output)


if __name__ == '__main__':
    main()
