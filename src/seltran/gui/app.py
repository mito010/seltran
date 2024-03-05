import tkinter as tk
from tkinter import filedialog as tkfd
import customtkinter as ctk

from . import Settings
from .editor import Editor


class App(ctk.CTk):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.settings = Settings()

        self.title("Japanese Selective Translator!")
        self.geometry("400x600")

        self.file_menu = tk.Menu(master=self, tearoff=0)
        self.file_menu.add_command(label="save as text", command=self.prompt_save_as_text)
        self.file_menu.add_command(label="import text file", command=self.prompt_import_text_file)
        self.menubar = tk.Menu(master=self)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.configure(menu=self.menubar)

        self.editor = Editor(master=self, settings=self.settings)

        self.translate_button = ctk.CTkButton(
            master=self,
            text="Detect Tokens",
            command=self.editor.run_nlp,
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.editor.grid(sticky="EWNS")
        self.translate_button.grid(sticky="EWNS")

    def prompt_import_text_file(self):
        path = tkfd.askopenfilename()
        if not path:
            return

        with open(path, "r") as f:
            text = f.read()

        self.editor.insert_text(text)
        self.editor.run_nlp()

    def prompt_save_as_text(self):
        path = tkfd.asksaveasfilename()
        if not path:
            return

        with open(path, "w") as f:
            f.write(self.editor.get_text())
