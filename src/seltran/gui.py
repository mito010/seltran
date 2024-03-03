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
            TAG_TRANSLATABLE, "<Button-1>", self.select_clicked_translatable_tag
        )
        self.textbox.tag_config(TAG_SELECTED, background="red")

        self.translate_button = ctk.CTkButton(
            master=self,
            text="Translate",
            command=self.run_nlp,
        )

        self.select_translation_combo = ctk.CTkComboBox(
            master=self, command=self.apply_picked_translation_to_selected
        )
        self.reset_possible_translations()

        self.textbox.grid(sticky="EWNS")
        self.select_translation_combo.grid(sticky="EWNS")
        self.translate_button.grid(sticky="EWNS")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def _get_free_unique_tag(self) -> str:
        while True:
            id = str(random.randint(0, 10000000000))
            tag = TAG_UNIQUE(id)
            if tag not in self.unique_tags:
                return tag

    def run_nlp(self):
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

        # Add tags from NLP results
        for token in self.text_doc:
            if not self.translator.should_translate(token):
                continue

            start = f"1.0+{token.idx}c"
            end = f"1.0+{token.idx + len(token.text)}c"

            unique_tag = self._get_free_unique_tag()
            self.unique_tags[unique_tag] = token

            self.textbox.tag_add(TAG_TRANSLATABLE, start, end)
            self.textbox.tag_add(unique_tag, start, end)
        
        # TODO: add whitespace after translatable tag to prevent merging tag ranges

    def get_unique_tag_for_event(self, event) -> Optional[tuple[str, tuple[str, str]]]:
        """Find the unique tag which contains an event's location, if there is one.

        :param event: Tk event
        :return Optional[tuple[str, tuple[str, str]]]: (tag_name, (start_index, end_index)) or None
        """
        for tag in self.textbox.tag_names():
            if not is_unique_tag(tag):
                continue
            tag_ranges = self.get_tag_ranges_for_event(event, tag)
            if tag_ranges:
                # Return first tag range as unique tags are assumed to only appear once
                return (tag, tag_ranges[0])
        return None

    def get_tag_ranges(self, tag: str) -> list[tuple[str, str]]:
        tag_ranges = self.textbox.tag_ranges(tag)
        return [
            (str(tag_ranges[i]), str(tag_ranges[i + 1]))
            for i in range(0, len(tag_ranges), 2)
        ]

    def get_tag_ranges_for_event(self, event, tag: str) -> list[tuple[str, str]]:
        """Find all index ranges of a specific tag matching an event's location

        :param event: Tk event
        :param str tag: Tag name to match the event's location against
        :return list[tuple[str, str]]: All matching index ranges which are tagged as `tag` and contain the event location
        """
        event_index = self.textbox.index(f"@{event.x},{event.y}")
        tag_ranges = self.get_tag_ranges(tag)

        def in_range_filter(tag_range: tuple[str, str]) -> bool:
            return is_index_in_range(
                self.textbox, event_index, tag_range[0], tag_range[1]
            )

        return list(filter(in_range_filter, tag_ranges))

    def get_tags_of_range(self, tag_range: tuple[str, str]) -> list[str]:
        tags = []

        for tag in self.textbox.tag_names():
            tag_ranges = self.get_tag_ranges(tag)
            if tag_range in tag_ranges:
                tags.append(tag)

        return tags

    def get_unique_tag_of_range(self, tag_range: tuple[str, str]) -> Optional[str]:
        for tag in self.get_tags_of_range(tag_range):
            if is_unique_tag(tag):
                return tag
        return None

    def get_selected(self) -> Optional[tuple[str, tuple[str, str]]]:
        selected_ranges = self.get_tag_ranges(TAG_SELECTED)
        if not selected_ranges:
            return None
        selected_range = selected_ranges[0]

        selected_unique_tag = self.get_unique_tag_of_range(selected_range)
        assert selected_unique_tag is not None

        return (selected_unique_tag, selected_range)

    def select_clicked_translatable_tag(self, event):
        # A unique tag is assured to be under the event since this callback is only
        # called for clicks on tagged text.
        _ = self.get_unique_tag_for_event(event)
        assert _ is not None
        unique_tag, clicked_range = _

        token = self.unique_tags[unique_tag]
        self.update_possible_translations(token)

        self.textbox.tag_remove(TAG_SELECTED, "1.0", "end")
        self.textbox.tag_add(TAG_SELECTED, clicked_range[0], clicked_range[1])

    def update_possible_translations(self, token: Token):
        translations = self.translator.get_possible_translations(token)
        self.select_translation_combo.configure(values=translations)
        self.select_translation_combo.set("Select translation...")

    def reset_possible_translations(self):
        self.select_translation_combo.configure(values=[])
        self.select_translation_combo.set("No word selected")

    def apply_picked_translation_to_selected(self, translation: str):
        _ = self.get_selected()
        assert _ is not None
        _, selected_range = _
        old_tags = self.get_tags_of_range(selected_range)

        # Deleting the selected range also removes the selected and unique tags
        self.textbox.delete(selected_range[0], selected_range[1])

        self.textbox.insert(selected_range[0], translation)
        selected_range = (selected_range[0], f"{selected_range[0]}+{len(translation)}c")
        print(old_tags)
        for tag in old_tags:
            self.textbox.tag_add(tag, selected_range[0], selected_range[1])


class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.editor = Editor(master=self)
        self.editor.grid(sticky="EWNS")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
