from dataclasses import dataclass
from enum import Enum
import random
from typing import Optional
import tkinter as tk
import customtkinter as ctk
import logging
from rich.logging import RichHandler
from seltran import SelectiveTranslator
from spacy.tokens import Doc, Token


TAG_TRANSLATABLE = "translatable"
TAG_SELECTED = "selected"
_TAG_UNIQUE = "unique-"


def TAG_UNIQUE(id: str) -> str:
    return _TAG_UNIQUE + id


# @dataclass
# class TranslatedToken:
#     token: Token
#     tag: str


def is_index_in_range(
    textbox: ctk.CTkTextbox, index: str, start: str, end: str
) -> bool:
    return textbox.compare(start, "<=", index) and textbox.compare(index, "<", end)


def is_unique_tag(tag: str) -> bool:
    return tag.startswith(_TAG_UNIQUE)


class Editor(ctk.CTkFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.translator = SelectiveTranslator()

        self.text_doc: Optional[Doc] = None

        self.unique_tags: dict[str, Token] = dict()

        self.textbox = ctk.CTkTextbox(master=self)
        self.textbox.tag_config(TAG_TRANSLATABLE, background="blue")
        self.textbox.tag_bind(
            TAG_TRANSLATABLE, "<Button-1>", self.select_clicked_translatable
        )
        self.textbox.tag_config(TAG_SELECTED, background="yellow")

        self.translate_button = ctk.CTkButton(
            master=self,
            text="Translate",
            command=self.refresh_nlp,
        )

        self.select_translation_combo = ctk.CTkComboBox(master=self)
        self.reset_possible_translations()

        self.textbox.pack()
        self.select_translation_combo.pack()
        self.translate_button.pack()

    def _get_free_unique_tag(self) -> str:
        while True:
            id = str(random.randint(0, 10000000000))
            tag = TAG_UNIQUE(id)
            if tag not in self.unique_tags:
                return tag

    def refresh_nlp(self):
        # Clean up previous analysis
        self.unique_tags = dict()
        self.textbox.tag_remove(TAG_SELECTED, "1.0", "end")
        self.textbox.tag_remove(TAG_TRANSLATABLE, "1.0", "end")
        for tag in self.textbox.tag_names():
            if is_unique_tag(tag):
                self.textbox.tag_remove(tag, "1.0", "end")
        self.reset_possible_translations()

        # Analyze the text
        text = self.textbox.get(0.0, "end-1c")
        self.text_doc = self.translator.nlp(text)

        for token in self.text_doc:
            if not self.translator.should_translate(token):
                continue

            start = f"1.0+{token.idx}c"
            end = f"1.0+{token.idx + len(token.text)}c"

            unique_tag = self._get_free_unique_tag()
            self.unique_tags[unique_tag] = token

            self.textbox.tag_add(TAG_TRANSLATABLE, start, end)
            self.textbox.tag_add(unique_tag, start, end)

    def get_event_unique_tag(self, event) -> Optional[tuple[str, tuple[str, str]]]:
        for tag in self.textbox.tag_names():
            if not is_unique_tag(tag):
                continue
            tag_ranges = self.get_event_ranges_of_tag(event, tag)
            if tag_ranges:
                # Return first tag range as unique tags are assumed to only appear once
                return (tag, tag_ranges[0])
        return None

    def get_event_ranges_of_tag(self, event, tag: str) -> list[tuple[str, str]]:
        """Find all index ranges of a specific tag matching an event's location

        :param event: e.g. click event
        :param str tag: Tag name to match the event's location against
        :return list[tuple[str, str]]: All matching index ranges which are tagged as `tag` and contain the event location
        """
        event_index = self.textbox.index(f"@{event.x},{event.y}")

        tag_ranges = self.textbox.tag_ranges(tag)
        tag_ranges = [
            (str(tag_ranges[i]), str(tag_ranges[i + 1]))
            for i in range(0, len(tag_ranges), 2)
        ]

        def in_range_filter(tag_range: tuple[str, str]) -> bool:
            return is_index_in_range(
                self.textbox, event_index, tag_range[0], tag_range[1]
            )

        return list(filter(in_range_filter, tag_ranges))

    def get_tags_of_range(self, tag_range: tuple[str, str]) -> list[str]:
        tags = []

        for tag in self.textbox.tag_names():
            tag_ranges = self.textbox.tag_ranges(tag)
            tag_ranges = [
                (str(tag_ranges[i]), str(tag_ranges[i + 1]))
                for i in range(0, len(tag_ranges), 2)
            ]

            if tag_range in tag_ranges:
                tags.append(tag)

        return tags

    def get_unique_tag_of_range(self, tag_range: tuple[str, str]) -> Optional[str]:
        unique_tags = list(filter(is_unique_tag, self.get_tags_of_range(tag_range)))
        return unique_tags[0] if unique_tags else None

    def select_clicked_translatable(self, event):
        # A unique tag is assured to be under the event since this callback is only
        # called for clicks on tagged text.
        _ = self.get_event_unique_tag(event)
        assert _ is not None
        unique_tag, clicked_range = _

        token = self.unique_tags[unique_tag]
        self.update_possible_translations(token)

        self.textbox.tag_remove(TAG_SELECTED, "1.0", "end")
        self.textbox.tag_add(TAG_SELECTED, clicked_range[0], clicked_range[1])

    def update_possible_translations(self, token: Token):
        translations = self.translator.get_possible_translations(token)
        self.select_translation_combo.configure(values=translations)
        self.select_translation_combo.set('Select translation...')
    
    def reset_possible_translations(self):
        self.select_translation_combo.configure(values=[])
        self.select_translation_combo.set('No word selected')


class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.editor = Editor(master=self)
        self.editor.grid(sticky=tk.E + tk.W + tk.N + tk.S)

        self.editor.pack()


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
