import customtkinter
import logging
from rich.logging import RichHandler
from seltran import SelectiveTranslator

def main():
    logging.getLogger().addHandler(RichHandler())
    
    translator = SelectiveTranslator()

    customtkinter.set_appearance_mode("System")

    app = customtkinter.CTk()

    textbox = customtkinter.CTkTextbox(master=app)
    textbox.pack()
    out_text = customtkinter.CTkTextbox(master=app)

    def button_function():
        text = textbox.get(0.0, 'end-1c')
        out_text.delete(0.0, "end")
        out_text.insert(0.0, translator.translate_dumb(text))

    button = customtkinter.CTkButton(
        master=app, text="Translate!", command=button_function
    )
    button.pack()

    out_text.pack()

    app.mainloop()
