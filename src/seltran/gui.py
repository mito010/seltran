import customtkinter


def main():
    customtkinter.set_appearance_mode("System")

    app = customtkinter.CTk()

    def button_function():
        print("button yay")

    button = customtkinter.CTkButton(
        master=app, text="CTkButton", command=button_function)
    button.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)

    app.mainloop()
