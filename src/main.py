import tkinter as tk
from tkinter import ttk, filedialog

from endpoints import (
    fetch_cookies,
    fetch_story_content_zip,
    fetch_story_from_partId,
    fetch_story,
)
from epub_generator import EPUBGenerator
from parser import fetch_image, fetch_tree_images, clean_tree
from asyncio import run
from pathlib import Path
from os import remove
from zipfile import ZipFile
from re import sub


def ascii_only(string: str):
    string = string.replace(" ", "_")
    return sub(
        r"[^qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM1234567890\-\_)(`~.><\[\]{}]",
        "",
        string,
    )


# global tk widgets
widgets = {}

images_var = None


def reload_widgets():
    for name, widget in widgets.items():
        widget["widget"].pack(
            anchor=widget["anchor"], fill="x", expand=True, padx=5, pady=1
        )


def button_click():
    run(handle_download())


async def handle_download():
    URL = widgets["URL_input"]["widget"].get()
    username = widgets["username_input"]["widget"].get()
    password = widgets["password_input"]["widget"].get()
    download_images = images_var.get()

    if not URL:
        widgets["info_label"]["widget"].config(
            text="You must provide a story URL", fg="red"
        )
        return

    if "wattpad.com/" not in URL:
        widgets["info_label"]["widget"].config(
            text="You must provide a Wattpad URL", fg="red"
        )
        return

    if "/story/" in URL:  # https://wattpad.com/story/237369078-wattpad-books-presents
        ID = URL[URL.index("/story/") + 7 : URL.index("-")]
        mode = "story"
    else:
        try:  # https://www.wattpad.com/939051741-wattpad-books-presents-the-qb-bad-boy-and-me
            ID = URL[URL.index("com/") + 4 : URL.index("-")]
            mode = "part"
        except ValueError:
            widgets["info_label"]["widget"].config(
                text="You must provide a valid Story or Part URL", fg="red"
            )
            return

    if username and not password or password and not username:
        widgets["info_label"]["widget"].config(
            text="You must provide your username AND password", fg="red"
        )
        return

    # Fetch cookies
    if username and password:
        widgets["info_label"]["widget"].config(text="Logging in", fg="black")
        cookies = await fetch_cookies(username, password)
    else:
        cookies = None

    # Fetch metadata
    widgets["info_label"]["widget"].config(text="Fetching story info", fg="black")
    match (mode):
        case "story":
            metadata = await fetch_story(ID, cookies)
        case "part":
            metadata = await fetch_story_from_partId(ID, cookies)

    # Fetch cover
    widgets["info_label"]["widget"].config(text="Fetching cover", fg="black")
    cover_data = await fetch_image(metadata["cover"].replace("-256-", "-512-"))
    if not cover_data:
        print(f"Warning: Could not fetch cover for {metadata['title']}")
        return

    # Fetch part content
    widgets["info_label"]["widget"].config(text="Fetching part content", fg="black")
    story_zip = await fetch_story_content_zip(metadata["id"], cookies)
    archive = ZipFile(story_zip, "r")
    part_trees = []

    for part in metadata["parts"]:
        if part.get("deleted", False):
            continue

        part_trees.append(
            clean_tree(
                part["title"],
                part["id"],
                archive.read(str(part["id"])).decode("utf-8"),
            )
        )

    # Fetch images
    widgets["info_label"]["widget"].config(text="Fetching images", fg="black")
    images = (
        [await fetch_tree_images(tree) for tree in part_trees]
        if download_images
        else []
    )

    # Compile book
    widgets["info_label"]["widget"].config(text="Compiling book", fg="black")
    book = EPUBGenerator(metadata, part_trees, cover_data, images)
    book.compile()

    filepath = filedialog.asksaveasfilename(
        title="Save As",
        initialfile=f"{metadata['title']}.epub",
        defaultextension=".epub",
        filetypes=[("EPUB Files", "*.epub"), ("All Files", "*.*")],
    )

    output_path = Path(filepath)
    if output_path.exists():
        remove(output_path)
    with open(output_path, "xb") as output:
        output.write(book.dump().getvalue())

    widgets["info_label"]["widget"].config(text="Download complete", fg="black")


# Build tk window
root = tk.Tk()
root.geometry("350x300")
root.title("Wattpad Downloader")
images_var = tk.BooleanVar()

widgets["info_label"] = {
    "widget": tk.Label(root, text='Input a Story URL and click "Download"'),
    "anchor": tk.N,
}

widgets["URL_label"] = {"widget": ttk.Label(root, text="Story URL:"), "anchor": tk.W}

widgets["URL_input"] = {"widget": ttk.Entry(root), "anchor": tk.N}
widgets["URL_input"]["widget"].focus()

widgets["username_label"] = {
    "widget": ttk.Label(root, text="Username (Optional):"),
    "anchor": tk.W,
}

widgets["username_input"] = {"widget": ttk.Entry(root), "anchor": tk.N}

widgets["password_label"] = {
    "widget": ttk.Label(root, text="Password (Optional):"),
    "anchor": tk.W,
}

widgets["password_input"] = {"widget": ttk.Entry(root), "anchor": tk.N}

widgets["images_checkbox"] = {
    "widget": tk.Checkbutton(root, text="Download Images:", variable=images_var),
    "anchor": tk.W,
}

download_icon = tk.PhotoImage(file="./src/download.png")
widgets["download_button"] = {
    "widget": ttk.Button(
        root,
        text="Download",
        image=download_icon,
        compound=tk.LEFT,
        command=button_click,
    ),
    "anchor": tk.N,
}

widgets["spacer"] = {"widget": tk.Frame(root, height=5), "anchor": tk.N}

widgets["exit_button"] = {
    "widget": ttk.Button(
        root,
        text="Exit",
        command=lambda: root.quit(),
    ),
    "anchor": tk.N,
}

if __name__ == "__main__":
    reload_widgets()
    try:
        # Windows compatibility
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except ImportError:
        ...
    finally:
        root.mainloop()
