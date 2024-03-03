import logging
from rich.logging import RichHandler
from . import SelectiveTranslator


def main():
    # logging.getLogger().addHandler(RichHandler())
    # translator = SelectiveTranslator()
    # translated_subs = [
    #     (line.plaintext, translator.translate(line.plaintext)) for line in pysubs2.load('./subs/timedS1E01.srt')
    # ]
    # print('\n\n'.join('\n'.join([original, translated])
    #       for original, translated in translated_subs))
    logging.getLogger().addHandler(RichHandler())
    translator = SelectiveTranslator()
    text = '魔王を倒したからといって'
    print(translator.translate_dumb(text))


if __name__ == '__main__':
    main()
