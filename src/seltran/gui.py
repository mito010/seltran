import customtkinter as ctk
import logging
from rich.logging import RichHandler
from seltran import SelectiveTranslator


class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.translator = SelectiveTranslator()

        self.user_textbox = ctk.CTkTextbox(master=self)
        self.user_input = ""

        self.set_translate = ctk.BooleanVar(value=False)

        def trigger_set_translate():
            self.set_translate.set(not self.set_translate.get())
            if self.set_translate.get():
                return enable_translate_input()
            else:
                return disable_translate_input()

        def enable_translate_input():
            self.translate_button.configure(text="Stop Translation")
            self.user_input = self.user_textbox.get(0.0, "end-1c")
            self.user_textbox.delete(0.0, "end")
            self.user_textbox.insert(
                0.0, self.translator.translate_dumb(self.user_input)
            )
            self.user_textbox.configure(state=ctk.DISABLED)

        def disable_translate_input():
            self.translate_button.configure(text="Translate!")
            self.user_textbox.configure(state=ctk.NORMAL)
            self.user_textbox.delete(0.0, "end")
            self.user_textbox.insert(0.0, self.user_input)

        self.translate_button = ctk.CTkButton(
            master=self,
            text="Translate!",
            command=trigger_set_translate,
        )

        self.user_textbox.pack()
        self.translate_button.pack()


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
