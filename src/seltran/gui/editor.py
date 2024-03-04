from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional
import customtkinter as ctk
from spacy.tokens import Token, Doc
import random
from seltran.gui import Settings

TAG_TRANSLATABLE = "translatable"
TAG_SELECTED_TOKEN = "selected"
_TAG_TOKEN = "_token-"


def TAG_TOKEN(id: str) -> str:
    return _TAG_TOKEN + id


Tag = str


Index = str


@dataclass(frozen=True)
class IndexRange:
    start: Index
    end: Index


@dataclass(frozen=True)
class TagInfo:
    tag: Tag
    range: IndexRange


def is_token_tag(tag: Tag) -> bool:
    return tag.startswith(_TAG_TOKEN)


class EditorTextbox(ctk.CTkTextbox):
    """Textbox with wrappers for common editor operations"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def is_index_in_range(self, index: Index, start: Index, end: Index) -> bool:
        return self.compare(start, "<=", index) and self.compare(index, "<", end)

    def is_range_in_range(
        self, small_range: IndexRange, large_range: IndexRange
    ) -> bool:
        return self.is_index_in_range(
            small_range.start, large_range.start, large_range.end
        ) and self.is_index_in_range(
            small_range.end, large_range.start, large_range.end + "+1c"
        )

    def tag_ranges_(self, tag: Tag) -> list[IndexRange]:
        """Thin wrapper around the regular `tag_ranges` with a more sane output format.

        :param str tag: Tag name to get ranges of
        :return list[IndexRange]: [(start, end), ...]
        """
        tag_ranges = self.tag_ranges(tag)
        return [
            IndexRange(str(tag_ranges[i]), str(tag_ranges[i + 1]))
            for i in range(0, len(tag_ranges), 2)
        ]

    def get_tags_of_exactly_range(self, tag_range: IndexRange) -> list[Tag]:
        tags = []

        for tag in self.tag_names():
            tag_ranges = self.tag_ranges_(tag)
            if tag_range in tag_ranges:
                tags.append(tag)

        return tags

    def get_tags_containing_range(
        self, tag_range: IndexRange
    ) -> dict[Tag, list[IndexRange]]:
        tags = defaultdict(list)

        for tag in self.tag_names():
            tag_ranges = self.tag_ranges_(tag)
            for checked_range in tag_ranges:
                if self.is_range_in_range(tag_range, checked_range):
                    tags[tag].append(checked_range)

        return tags

    def get_tag_ranges_for_event(self, event, tag: Tag) -> list[IndexRange]:
        """Find all index ranges of a specific tag matching an event's location

        :param event: Tk event
        :param str tag: Tag name to match the event's location against
        :return list[IndexRange]: All matching index ranges which are tagged as `tag` and contain the event location
        """
        event_index = self.index(f"@{event.x},{event.y}")
        tag_ranges = self.tag_ranges_(tag)

        def in_range_filter(tag_range: IndexRange) -> bool:
            return self.is_index_in_range(event_index, tag_range.start, tag_range.end)

        return list(filter(in_range_filter, tag_ranges))

    def remove_all_of_tag(self, tag: Tag):
        self.tag_remove(tag, "1.0", "end")

    def tag_names_filtered(self, filter_op: Callable[[Tag], bool]):
        for tag in self.tag_names():
            if filter_op(tag):
                yield tag

    def tag_query(self, tag_filter: Callable[[str], bool]) -> dict[Tag, IndexRange]:
        tags = dict()
        for tag in self.tag_names_filtered(tag_filter):
            tag_ranges = self.tag_ranges_(tag)
            # ignore tags which don't have any real text assigned
            if not tag_ranges:
                continue
            tags[tag] = tag_ranges[0]
        return tags

    def replace_text(self, index_range: IndexRange, new_text: str) -> IndexRange:
        old_tags = self.get_tags_containing_range(index_range)

        # Deleting the selected range also removes all tags from the range
        self.delete(index_range.start, index_range.end)

        self.insert(index_range.start, new_text)
        new_range = IndexRange(
            index_range.start, f"{index_range.start}+{len(new_text)}c"
        )
        for tag in old_tags:
            self.tag_add(tag, new_range.start, new_range.end)
        
        return new_range


class Editor(ctk.CTkFrame):
    def __init__(self, settings: Settings, **kwargs):
        super().__init__(**kwargs)

        self.settings = settings
        self.tokens: Optional[Doc] = None
        self.token_tags: dict[str, Token] = dict()

        self.textbox = EditorTextbox(master=self)
        self.textbox.tag_config(TAG_TRANSLATABLE, background="blue")
        self.textbox.tag_bind(
            TAG_TRANSLATABLE,
            "<Button-1>",
            self.select_clicked_translatable_tag,
        )
        self.textbox.tag_config(TAG_SELECTED_TOKEN, background="red")

        self.select_translation_combo = ctk.CTkComboBox(
            master=self, command=self.apply_picked_translation_to_selected_token
        )
        self.reset_possible_translations()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.select_translation_combo.grid(sticky="EW")
        self.textbox.grid(sticky="EWNS")

    def _get_free_token_tag(self) -> Tag:
        while True:
            id = str(random.randint(0, 10000000000))
            tag = TAG_TOKEN(id)
            if tag not in self.token_tags:
                return tag

    def reset_content(self):
        self.textbox.delete("1.0", "end")

    def run_nlp(self):
        # Analyze the text
        text = self.textbox.get(0.0, "end-1c")
        self.tokens = self.settings.translator.nlp(text)

        existing_token_tags = self.textbox.tag_query(is_token_tag)
        token_tag_ranges = set(existing_token_tags.values())
        existing_token_tags = set(existing_token_tags.keys())

        # Clean up token tag data for tags which don't exist anymore
        for tag in list(self.token_tags.keys()):
            if tag not in existing_token_tags:
                del self.token_tags[tag]
                self.textbox.tag_delete(tag)

        # Add tags from NLP results
        for token in self.tokens:
            if not self.settings.filter_translatable(token):
                continue

            token_start = f"1.0+{token.idx}c"
            token_end = f"1.0+{token.idx + len(token.text)}c"

            # Don't tag the token again if the text is already tagged with a token tag
            # left from a previous translation
            if any(
                self.textbox.is_range_in_range(
                    IndexRange(token_start, token_end), token_tag_range
                )
                for token_tag_range in token_tag_ranges
            ):
                continue

            token_tag = self._get_free_token_tag()
            self.token_tags[token_tag] = token

            self.textbox.tag_add(TAG_TRANSLATABLE, token_start, token_end)
            self.textbox.tag_add(token_tag, token_start, token_end)

    def get_token_tag_for_event(self, event) -> Optional[TagInfo]:
        """Find the token tag which contains an event's location, if there is one.

        :param event: Tk event
        :return Optional[TagInfo]: (tag_name, (start_index, end_index)) or None
        """
        for token_tag in self.textbox.tag_names_filtered(is_token_tag):
            tag_ranges = self.textbox.get_tag_ranges_for_event(event, token_tag)
            if tag_ranges:
                # Return first tag range as token tags are assumed to only appear once
                return TagInfo(token_tag, tag_ranges[0])
        return None

    def get_token_tag_of_range(self, tag_range: IndexRange) -> Optional[Tag]:
        for tag in self.textbox.get_tags_of_exactly_range(tag_range):
            if is_token_tag(tag):
                return tag
        return None

    def get_selected_token_tag(self) -> Optional[TagInfo]:
        selected_ranges = self.textbox.tag_ranges_(TAG_SELECTED_TOKEN)
        if not selected_ranges:
            return None
        selected_range = selected_ranges[0]

        selected_token_tag = self.get_token_tag_of_range(selected_range)
        assert selected_token_tag is not None

        return TagInfo(selected_token_tag, selected_range)

    def select_clicked_translatable_tag(self, event):
        # A token tag is assured to be under the event since this callback is only
        # called for clicks on tagged text.
        _ = self.get_token_tag_for_event(event)
        assert _ is not None
        token_tag, clicked_range = _.tag, _.range

        token = self.token_tags[token_tag]
        self.update_possible_translations(token)

        self.textbox.tag_remove(TAG_SELECTED_TOKEN, "1.0", "end")
        self.textbox.tag_add(TAG_SELECTED_TOKEN, clicked_range.start, clicked_range.end)

    def update_possible_translations(self, token: Token):
        translations = self.settings.translator.get_dictionary_translations(token)
        self.select_translation_combo.configure(values=[token.text] + translations)
        if translations:
            self.select_translation_combo.set("Select translation...")
        else:
            self.select_translation_combo.set("No available translation")

    def reset_possible_translations(self):
        self.select_translation_combo.configure(values=[])
        self.select_translation_combo.set("No word selected")

    def apply_picked_translation_to_selected_token(self, translation: str):
        selected_token_tag = self.get_selected_token_tag()
        # if the selection was deleted and the translation menu wasn't reset,
        # do nothing as the translation target is no more
        if selected_token_tag is None:
            return

        selected_token = self.token_tags[selected_token_tag.tag]

        new_range = self.textbox.replace_text(selected_token_tag.range, translation)

        # Insert a fitting separator after the inserted translation
        char_after_selected = self.textbox.get(new_range.end)
        if selected_token.text != translation and char_after_selected not in (" ", "-"):
            if not self.settings.filter_start_of_new_word(selected_token.nbor(1)):
                separator = "-"
            else:
                separator = " "
            self.textbox.insert(new_range.end, separator)

        

    def insert_text(self, text: str):
        self.reset_content()
        self.textbox.insert("1.0", text)

    def get_text(self):
        return self.textbox.get("1.0", "end")
