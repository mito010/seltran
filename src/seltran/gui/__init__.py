import logging
from rich.logging import RichHandler
import customtkinter as ctk

from .app import App


def main():
    logging.getLogger().addHandler(RichHandler())
    ctk.set_appearance_mode("system")
    app = App()
    app.mainloop()
