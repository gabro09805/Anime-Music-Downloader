import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from song_service import OUTPUT_FORMATS, SEARCH_FIELDS, anime_year, download_song, search_songs, validate_options


def natural_key(value):
    return [(1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"(\d+)", value)]


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anime Music Downloader")
        self.geometry("1050x600")
        self.minsize(720, 420)
        self.events = queue.Queue()
        self.songs = []
        self.sort_column = None
        self.sort_ascending = True
        self.column_titles = {}
        self.output_format = "originale"
        self.filename_template = "{Artista} - {Titolo}"
        self.directory = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.query = tk.StringVar()
        self.category = tk.StringVar(value="Anime")
        self.status = tk.StringVar(value="Cerca un anime, un brano o un artista.")
        self._build_ui()
        self.after(100, self._process_events)

    def _build_ui(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        search = ttk.Frame(frame)
        search.pack(fill="x")
        ttk.Label(search, text="Cerca:").pack(side="left")
        entry = ttk.Entry(search, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda event: self.start_search())
        ttk.Combobox(search, textvariable=self.category, values=["Tutti", *SEARCH_FIELDS],
                     state="readonly", width=14).pack(side="left")
        self.search_button = ttk.Button(search, text="Cerca", command=self.start_search)
        self.search_button.pack(side="left", padx=(8, 0))
        self.options_button = ttk.Button(search, text="Opzioni", command=self.show_options)
        self.options_button.pack(side="left", padx=(8, 0))
        entry.focus_set()

        columns = ("anime", "season", "anno", "tipo", "titolo", "artista", "disponibilita")
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True, pady=12)
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        for column, title, width in [
            ("anime", "Anime", 220), ("season", "Season", 110), ("anno", "Anno", 65),
            ("tipo", "Tipo", 90), ("titolo", "Titolo", 240),
            ("artista", "Artista", 220), ("disponibilita", "Sorgente", 110),
        ]:
            self.column_titles[column] = title
            self.table.heading(column, text=title, command=lambda name=column: self.sort_results(name))
            self.table.column(column, width=width, minwidth=60)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        destination = ttk.Frame(frame)
        destination.pack(fill="x")
        ttk.Label(destination, text="Cartella:").pack(side="left")
        ttk.Entry(destination, textvariable=self.directory).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(destination, text="Sfoglia...", command=self.choose_directory).pack(side="left")
        self.download_button = ttk.Button(destination, text="Scarica selezionati", command=self.start_download)
        self.download_button.pack(side="left", padx=(8, 0))
        ttk.Label(frame, textvariable=self.status, wraplength=950).pack(anchor="w", pady=(10, 0))

    def reset_sort(self):
        self.sort_column = None
        self.sort_ascending = True
        for column, title in self.column_titles.items():
            self.table.heading(column, text=title)

    def sort_results(self, column):
        self.sort_ascending = not self.sort_ascending if self.sort_column == column else True
        self.sort_column = column
        for name, title in self.column_titles.items():
            marker = (" ▲" if self.sort_ascending else " ▼") if name == column else ""
            self.table.heading(name, text=title + marker)
        rows = self.table.get_children()
        available = [item for item in rows if self.table.set(item, column) not in ("", "—")]
        missing = [item for item in rows if self.table.set(item, column) in ("", "—")]
        available.sort(key=lambda item: natural_key(self.table.set(item, column)), reverse=not self.sort_ascending)
        for index, item in enumerate(available + missing):
            self.table.move(item, "", index)

    def choose_directory(self):
        selected = filedialog.askdirectory(initialdir=self.directory.get(), parent=self)
        if selected:
            self.directory.set(selected)

    def show_options(self):
        dialog = tk.Toplevel(self)
        dialog.title("Opzioni di output")
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        output_format = tk.StringVar(value=self.output_format)
        template = tk.StringVar(value=self.filename_template)
        ttk.Label(frame, text="Formato audio").pack(anchor="w")
        ttk.Combobox(frame, textvariable=output_format, values=OUTPUT_FORMATS,
                     state="readonly").pack(fill="x", pady=(4, 12))
        ttk.Label(frame, text="Modello nome file (senza estensione)").pack(anchor="w")
        ttk.Entry(frame, textvariable=template, width=55).pack(fill="x", pady=(4, 8))
        ttk.Label(frame, text="Segnaposto: {Anime}, {Season}, {Anno}, {Tipo}, {Titolo}, {Artista}, {Sorgente}",
                  wraplength=430).pack(anchor="w")
        ttk.Label(frame, text="Esempio: {Anime} - {Titolo} - {Artista}\n"
                  "Le opzioni valgono fino alla chiusura dell'applicazione.",
                  wraplength=430).pack(anchor="w", pady=8)

        def save():
            try:
                validate_options(output_format.get(), template.get())
            except ValueError as exc:
                messagebox.showerror("Opzioni", str(exc), parent=dialog)
                return
            self.output_format = output_format.get()
            self.filename_template = template.get()
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(8, 0))
        ttk.Button(buttons, text="Annulla", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Salva", command=save).pack(side="left")

    def _busy(self, busy):
        state = "disabled" if busy else "normal"
        self.search_button.configure(state=state)
        self.download_button.configure(state=state)
        self.options_button.configure(state=state)

    def start_search(self):
        if str(self.search_button["state"]) == "disabled":
            return
        query, category = self.query.get().strip(), self.category.get()
        if not query:
            messagebox.showwarning("Ricerca", "Inserisci un termine di ricerca.", parent=self)
            return
        self._busy(True)
        self.status.set("Ricerca in corso...")

        def worker():
            try:
                self.events.put(("search", search_songs(query, category)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def start_download(self):
        selected = [self.songs[int(i)] for i in self.table.selection()]
        if not selected:
            messagebox.showwarning("Download", "Seleziona almeno una traccia.", parent=self)
            return
        directory = Path(self.directory.get()).expanduser()
        if not directory.is_dir():
            messagebox.showerror("Download", "Seleziona una cartella esistente.", parent=self)
            return
        self._busy(True)
        self.status.set("Download in corso...")
        output_format, template = self.output_format, self.filename_template

        def worker():
            errors = []
            completed = 0
            for index, song in enumerate(selected, 1):
                title = str(song.get("songName") or "Senza titolo")
                self.events.put(("status", f"Download {index}/{len(selected)}: {title}"))
                try:
                    download_song(song, directory, output_format, template)
                    completed += 1
                except Exception as exc:
                    errors.append(f"{title}: {exc}")
            self.events.put(("downloads", (completed, len(selected), errors)))
        threading.Thread(target=worker, daemon=True).start()

    def _process_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "status":
                    self.status.set(value)
                elif event == "search":
                    self.songs = value
                    self.table.delete(*self.table.get_children())
                    self.reset_sort()
                    for index, song in enumerate(self.songs):
                        source = "Audio" if song.get("audio") else "Video" if song.get("HQ") or song.get("MQ") else "Non disponibile"
                        self.table.insert("", "end", iid=str(index), values=(
                            song.get("animeENName") or song.get("animeJPName") or "",
                            song.get("animeVintage") or "—",
                            anime_year(song) or "—",
                            song.get("songType") or "", song.get("songName") or "",
                            song.get("songArtist") or "", source))
                    self.status.set(f"{len(self.songs)} risultati. Seleziona una o più tracce.")
                    self._busy(False)
                elif event == "error":
                    self._busy(False)
                    self.status.set("Operazione non riuscita.")
                    messagebox.showerror("Errore", value, parent=self)
                elif event == "downloads":
                    completed, total, errors = value
                    self._busy(False)
                    self.status.set(f"Download completati: {completed}/{total}.")
                    if errors:
                        messagebox.showerror("Download", f"Completati: {completed}/{total}\n\n" + "\n".join(errors), parent=self)
                    else:
                        messagebox.showinfo("Download", f"Scaricate {completed} tracce.", parent=self)
        except queue.Empty:
            pass
        self.after(100, self._process_events)


if __name__ == "__main__":
    Application().mainloop()
