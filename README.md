# Selective Japanese Translator!

 ![seltran-demo-import](https://github.com/sacred-serpent/seltran/assets/56104753/bfdcfde9-d61a-43ed-8588-fe308f2b8ccb) ![seltran-demo-translate](https://github.com/sacred-serpent/seltran/assets/56104753/ce0bc460-bae0-47b5-b126-79dca4c2a030)

## What this is

Inspired by Goken's idea presented in this [YouTube video](https://www.youtube.com/watch?v=3wF91iArEp0&t=333s),
this is an interactive tool for translating Japanese subtitles (and text in general) selectively with ease, using
automation based on natural language processing engines.

At this stage, this is only a proof of concept for the value such a tool can be of for those wanting to learn Japanese (or other languages possibly)
using Goken's subtitle format.
If you like the idea or have any suggestions, please (!) open an issue or contact me!

## Try it out!

Clone the repository and then:

```sh
pip install -e ./seltran
```

The `seltran-editor` executable will be installed in your python scripts directory.

## How?

- All tokenization, translation and phonetization operations are performed offline, using the `spacy` and `pykakasi` NLP libraries
  for token generation and phonetization, and a simple offline Japanese dictionary using `jamdict`.

- An easy to configure filtration mechanism exists for determining which types of tokens (e.g. nouns, verbs, or any other token quality)
  get translation suggestions and which only get phonetized. Currently this filtration cannot be configured through the UI though, see the roadmap.

## Roadmap

- [x] Interactive text translation for individual tokens with suggestions based on part of speech.
- [ ] Configure suggestion filters through UI
- [ ] Apply actions to all tokens according to rules - e.g. phonetize all particles, translate all nouns using first dictionary entry
- [ ] Use actual tranlation engine select the best fitting translation for a word based on context.
