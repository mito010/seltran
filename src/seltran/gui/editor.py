from collections import defaultdict
from dataclasses import dataclass
import threading
from typing import Callable, Optional
import tkinter as tk
import customtkinter as ctk
from spacy.tokens import Token, Doc
import random
from seltran.gui import Settings
from seltran.gui.app import TkCallQueue

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

    def overlapping_tag_names(self, index_range: IndexRange) -> set[str]:
        range_size = self._textbox.count(index_range.start, index_range.end, "chars")[0]
        return set(
            tag_name
            for i in range(range_size)
            for tag_name in self.tag_names(index_range.start + f"+{i}c")
        )

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
    def __init__(self, settings: Settings, call_queue: TkCallQueue, **kwargs):
        super().__init__(**kwargs)

        self.settings = settings
        self.tokens: Optional[Doc] = None
        self.token_tags: dict[str, Token] = dict()
        self._ui_call_queue = call_queue

        self.textbox = EditorTextbox(master=self)
        # self.textbox.tag_config(TAG_TRANSLATABLE, background="blue")
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

        self.status = tk.StringVar()
        self.status_bar = ctk.CTkLabel(
            master=self, text="", justify="left", anchor="w", textvariable=self.status
        )

        self.grid_columnconfigure(0, weight=1)
        self.select_translation_combo.grid(row=0, column=0, sticky="EW")
        self.textbox.grid(row=1, column=0, sticky="EWNS")
        self.grid_rowconfigure(1, weight=1)
        self.status_bar.grid(row=2, column=0, sticky="EW")

    def _get_free_token_tag(self) -> Tag:
        while True:
            id = str(random.randint(0, 10000000000))
            tag = TAG_TOKEN(id)
            if tag not in self.token_tags:
                return tag

    def reset_content(self):
        self.textbox.delete("1.0", "end")

    # TODO: Push and pop status?
    def set_status(self, text: str):
        self.status.set(text)

    def reset_status(self):
        self.status.set("")

    def clean_stale_tokens(self):
        existing_token_tags = self.textbox.tag_query(is_token_tag)
        existing_token_tag_names = set(existing_token_tags.keys())

        # Clean up token tags which were deleted from the text
        for tag in list(self.token_tags.keys()):
            if tag not in existing_token_tag_names:
                del self.token_tags[tag]
                self.textbox.tag_delete(tag)

    def add_tokens(self, tokens: Doc):
        for token in tokens:
            token_range = IndexRange(
                f"1.0+{token.idx}c", f"1.0+{token.idx + len(token.text)}c"
            )

            # Don't tag the token again if the text is already tagged with a token tag
            # left from a previous translation
            overlapping_tags = self.textbox.overlapping_tag_names(token_range)
            overlapping_token_tags_iter = filter(is_token_tag, overlapping_tags)
            if any(overlapping_token_tags_iter):
                continue

            new_token_tag = self._get_free_token_tag()
            self.token_tags[new_token_tag] = token
            self.textbox.tag_add(new_token_tag, token_range.start, token_range.end)
            self.textbox.tag_add(TAG_TRANSLATABLE, token_range.start, token_range.end)

    def _threaded_nlp_task(self):
        """Analyze tokens in text box and update the editor accordingly. Meant to be run in a different thread
        as processing time can be high - therefore all ui calls should be done using the call queue API.
        """
        _, text_future = self._ui_call_queue.queue_ui_calls(
            (
                (self.set_status, ("Detecting tokens...",), None),
                (self.get_and_lock_text, None, None),
            )
        )
        self._ui_call_queue.signal_process_ui_calls()
        text = text_future.wait()

        self.tokens = self.settings.translator.nlp(text)

        self._ui_call_queue.queue_ui_calls(
            (
                (self.clean_stale_tokens, None, None),
                (self.set_status, ("Marking detected tokens...",), None),
                (self.add_tokens, (self.tokens,), None),
                (self.unlock_text, None, None),
                (self.reset_status, None, None),
            )
        )
        self._ui_call_queue.signal_process_ui_calls()

    def detect_tokens(self):
        nlp_thread = threading.Thread(target=self._threaded_nlp_task)
        nlp_thread.start()

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
        # In cases of long translatable tag ranges which include multiple token tags,
        # text inserted between those token tags becomes tagged as translatable but not as
        # part of any token.
        token_tag = self.get_token_tag_for_event(event)
        if token_tag is None:
            return
        token_tag, clicked_range = token_tag.tag, token_tag.range

        token = self.token_tags[token_tag]
        self.update_possible_translations(token)

        self.textbox.tag_remove(TAG_SELECTED_TOKEN, "1.0", "end")
        self.textbox.tag_add(TAG_SELECTED_TOKEN, clicked_range.start, clicked_range.end)

    def update_possible_translations(self, token: Token):
        translations = (
            self.settings.translator.get_dictionary_translations(token)
            if self.settings.filter_should_translate(token)
            else []
        )
        phonemes = (
            [phonemes]
            if (phonemes := self.settings.translator.get_phonemes(token))
            else []
        )
        self.select_translation_combo.configure(
            values=[token.text] + phonemes + translations
        )

        if phonemes or translations:
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

        # Insert fitting separators before and after the inserted translation
        if (
            selected_token.text != translation
            and selected_token.i + 1 < len(selected_token.doc)
            and (next_token := selected_token.nbor(1)).pos_ != "PUNCT"
        ):
            if not self.settings.filter_start_of_new_word(next_token):
                translation += "-"
            else:
                translation += " "

        self.textbox.replace_text(selected_token_tag.range, translation)

    def set_text(self, text: str):
        self.set_status("Importing text...")
        self.reset_content()
        self.textbox.insert("1.0", text)
        self.reset_status()

    def get_text(self):
        return self.textbox.get("1.0", "end")

    def get_and_lock_text(self):
        text = self.textbox.get("1.0", "end-1c")
        self.textbox.configure(state=ctk.DISABLED)
        return text

    def unlock_text(self):
        self.textbox.configure(state=ctk.NORMAL)
