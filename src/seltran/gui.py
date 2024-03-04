from collections import defaultdict
import random
from typing import Callable, Optional
import tkinter as tk
from tkinter import filedialog as tkfd
import customtkinter as ctk
import logging
from rich.logging import RichHandler
from seltran import SelectiveTranslator
from spacy.tokens import Doc, Token


TAG_TRANSLATABLE = "translatable"
TAG_SELECTED_UNIQUE = "selected"
_TAG_UNIQUE = "unique-"


def TAG_UNIQUE(id: str) -> str:
    return _TAG_UNIQUE + id


def is_unique_tag(tag: str) -> bool:
    return tag.startswith(_TAG_UNIQUE)


class EditorTextbox(ctk.CTkTextbox):
    """Textbox with wrappers for common editor operations"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def is_index_in_range(self, index: str, start: str, end: str) -> bool:
        return self.compare(start, "<=", index) and self.compare(index, "<", end)

    def is_range_in_range(
        self, small_range: tuple[str, str], large_range: tuple[str, str]
    ) -> bool:
        return self.is_index_in_range(
            small_range[0], large_range[0], large_range[1]
        ) and self.is_index_in_range(
            small_range[1], large_range[0], large_range[1] + "+1c"
        )

    def tag_ranges_(self, tag: str) -> list[tuple[str, str]]:
        """Thin wrapper around the regular `tag_ranges` with a more sane output format.

        :param str tag: Tag name to get ranges of
        :return list[tuple[str, str]]: [(start, end), ...]
        """
        tag_ranges = self.tag_ranges(tag)
        return [
            (str(tag_ranges[i]), str(tag_ranges[i + 1]))
            for i in range(0, len(tag_ranges), 2)
        ]

    def get_tags_of_exactly_range(self, tag_range: tuple[str, str]) -> list[str]:
        tags = []

        for tag in self.tag_names():
            tag_ranges = self.tag_ranges_(tag)
            if tag_range in tag_ranges:
                tags.append(tag)

        return tags

    def get_tags_containing_range(
        self, tag_range: tuple[str, str]
    ) -> dict[str, list[tuple[str, str]]]:
        tags = defaultdict(list)

        for tag in self.tag_names():
            tag_ranges = self.tag_ranges_(tag)
            for checked_range in tag_ranges:
                if self.is_range_in_range(tag_range, checked_range):
                    tags[tag].append(checked_range)

        return tags

    def get_tag_ranges_for_event(self, event, tag: str) -> list[tuple[str, str]]:
        """Find all index ranges of a specific tag matching an event's location

        :param event: Tk event
        :param str tag: Tag name to match the event's location against
        :return list[tuple[str, str]]: All matching index ranges which are tagged as `tag` and contain the event location
        """
        event_index = self.index(f"@{event.x},{event.y}")
        tag_ranges = self.tag_ranges_(tag)

        def in_range_filter(tag_range: tuple[str, str]) -> bool:
            return self.is_index_in_range(event_index, tag_range[0], tag_range[1])

        return list(filter(in_range_filter, tag_ranges))

    def remove_all_of_tag(self, tag: str):
        self.tag_remove(tag, "1.0", "end")

    def tag_names_filtered(self, filter_op: Callable[[str], bool]):
        for tag in self.tag_names():
            if filter_op(tag):
                yield tag

    def tags_unique(
        self, unique_filter: Callable[[str], bool]
    ) -> dict[str, tuple[str, str]]:
        tags = dict()
        for tag in self.tag_names_filtered(unique_filter):
            tag_ranges = self.tag_ranges_(tag)
            # ignore tags which don't have any real text assigned
            if not tag_ranges:
                continue
            tags[tag] = tag_ranges[0]
        return tags

    def replace_text(self, index_range: tuple[str, str], new_text: str):
        old_tags = self.get_tags_containing_range(index_range)

        # Deleting the selected range also removes all tags from the range
        self.delete(index_range[0], index_range[1])

        self.insert(index_range[0], new_text)
        index_range = (index_range[0], f"{index_range[0]}+{len(new_text)}c")
        for tag in old_tags:
            self.tag_add(tag, index_range[0], index_range[1])


class Editor(ctk.CTkFrame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.translator = SelectiveTranslator()
        self.tokens: Optional[Doc] = None
        self.unique_tags: dict[str, Token] = dict()

        self.textbox = EditorTextbox(master=self)
        self.textbox.tag_config(TAG_TRANSLATABLE, background="blue")
        self.textbox.tag_bind(
            TAG_TRANSLATABLE,
            "<Button-1>",
            self.select_clicked_translatable_tag,
        )
        self.textbox.tag_config(TAG_SELECTED_UNIQUE, background="red")

        self.select_translation_combo = ctk.CTkComboBox(
            master=self, command=self.apply_picked_translation_to_selected_unique
        )
        self.reset_possible_translations()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.select_translation_combo.grid(sticky="EW")
        self.textbox.grid(sticky="EWNS")

    def _get_free_unique_tag(self) -> str:
        while True:
            id = str(random.randint(0, 10000000000))
            tag = TAG_UNIQUE(id)
            if tag not in self.unique_tags:
                return tag

    def reset_content(self):
        self.textbox.delete("1.0", "end")

    def run_nlp(self):
        # Analyze the text
        text = self.textbox.get(0.0, "end-1c")
        self.tokens = self.translator.nlp(text)

        unique_tags = self.textbox.tags_unique(is_unique_tag)
        existing_unique_tags = set(unique_tags.keys())
        unique_tag_ranges = set(unique_tags.values())

        # Clean up unique tag data for tags which don't exist anymore
        for tag in list(self.unique_tags.keys()):
            if tag not in existing_unique_tags:
                del self.unique_tags[tag]
                self.textbox.tag_delete(tag)

        # Add tags from NLP results
        for token in self.tokens:
            if not self.translator.should_translate(token):
                continue

            token_start = f"1.0+{token.idx}c"
            token_end = f"1.0+{token.idx + len(token.text)}c"

            # Don't tag the token again if the text is already tagged with a unique tag
            # left from a previous translation
            if any(
                self.textbox.is_range_in_range(
                    (token_start, token_end), unique_tag_range
                )
                for unique_tag_range in unique_tag_ranges
            ):
                continue

            unique_tag = self._get_free_unique_tag()
            self.unique_tags[unique_tag] = token

            self.textbox.tag_add(TAG_TRANSLATABLE, token_start, token_end)
            self.textbox.tag_add(unique_tag, token_start, token_end)

    def get_unique_tag_for_event(self, event) -> Optional[tuple[str, tuple[str, str]]]:
        """Find the unique tag which contains an event's location, if there is one.

        :param event: Tk event
        :return Optional[tuple[str, tuple[str, str]]]: (tag_name, (start_index, end_index)) or None
        """
        for unique_tag in self.textbox.tag_names_filtered(is_unique_tag):
            tag_ranges = self.textbox.get_tag_ranges_for_event(event, unique_tag)
            if tag_ranges:
                # Return first tag range as unique tags are assumed to only appear once
                return (unique_tag, tag_ranges[0])
        return None

    def get_unique_tag_of_range(self, tag_range: tuple[str, str]) -> Optional[str]:
        for tag in self.textbox.get_tags_of_exactly_range(tag_range):
            if is_unique_tag(tag):
                return tag
        return None

    def get_selected_unique_tag(self) -> Optional[tuple[str, tuple[str, str]]]:
        selected_ranges = self.textbox.tag_ranges_(TAG_SELECTED_UNIQUE)
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

        self.textbox.tag_remove(TAG_SELECTED_UNIQUE, "1.0", "end")
        self.textbox.tag_add(TAG_SELECTED_UNIQUE, clicked_range[0], clicked_range[1])

    def update_possible_translations(self, token: Token):
        translations = self.translator.get_possible_translations(token)
        self.select_translation_combo.configure(values=[token.text] + translations)
        if translations:
            self.select_translation_combo.set("Select translation...")
        else:
            self.select_translation_combo.set("No available translation")

    def reset_possible_translations(self):
        self.select_translation_combo.configure(values=[])
        self.select_translation_combo.set("No word selected")

    def apply_picked_translation_to_selected_unique(self, translation: str):
        selected_unique_tag = self.get_selected_unique_tag()
        # if the selection was deleted and the translation menu wasn't reset,
        # do nothing as the translation target is no more
        if selected_unique_tag is None:
            return
        
        _, selected_range = selected_unique_tag

        self.textbox.replace_text(selected_range, translation)

    def insert_text(self, text: str):
        self.reset_content()
        self.textbox.insert("1.0", text)

    def get_text(self):
        return self.textbox.get("1.0", "end")


class App(ctk.CTk):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.editor = Editor(master=self)

        self.translate_button = ctk.CTkButton(
            master=self,
            text="Translate",
            command=self.editor.run_nlp,
        )

        self.import_text_file_button = ctk.CTkButton(
            master=self,
            text="Import Text File...",
            command=self.prompt_import_text_file,
        )
        self.save_as_text_button = ctk.CTkButton(
            master=self,
            text="Save as Text",
            command=self.prompt_save_as_text,
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.editor.grid(sticky="EWNS")
        self.translate_button.grid(sticky="EWNS")
        self.import_text_file_button.grid(sticky="EWNS")
        self.save_as_text_button.grid(sticky="EWNS")

    def prompt_import_text_file(self):
        path = tkfd.askopenfilename()
        with open(path, "r") as f:
            text = f.read()

        self.editor.insert_text(text)

    def prompt_save_as_text(self):
        path = tkfd.asksaveasfilename()
        with open(path, "w") as f:
            f.write(self.editor.get_text())


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
