from dataclasses import dataclass
import logging
from rich.logging import RichHandler
import customtkinter as ctk

from seltran.translator import SelectiveTranslator, TokenFilter


@dataclass(frozen=False)
class Settings:
    translator: SelectiveTranslator = SelectiveTranslator()
    filter_should_translate: TokenFilter = TokenFilter(
        include_pos=[
            "NOUN",
            "VERB",
            "ADJ",
        ],
        exclude_foreign=True,
    )
    filter_start_of_new_word: TokenFilter = TokenFilter(
        include_pos=[
            "VERB",
            "NOUN",
        ]
    )


from .app import App


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
