"""
SF Legends .sff Unpacker — Desktop GUI
Run: python app.py
"""

import struct
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False


# ─────────────────────────────────────────────
#  Color palette & fonts
# ─────────────────────────────────────────────
BG         = "#0e1117"
BG2        = "#161b22"
BG3        = "#1c2330"
BORDER     = "#2a3444"
GREEN      = "#39ff86"
GREEN_DIM  = "#1e7a45"
TEXT       = "#c9d1d9"
TEXT_DIM   = "#586069"
DANGER     = "#ff4d4d"
WHITE      = "#ffffff"

FONT_MONO  = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)
FONT_HEAD  = ("Segoe UI", 13, "bold")
FONT_SMALL = ("Segoe UI", 8)


# ─────────────────────────────────────────────
#  Core unpacker logic
# ─────────────────────────────────────────────
def parse_sff(filepath):
    """Returns list of {filename, size} dicts + data_offset."""
    with open(filepath, "rb") as f:
        data = f.read()

    ENTRY_SIZE = 136
    entries = []
    offset = 0

    while offset + ENTRY_SIZE <= len(data):
        size = struct.unpack("<I", data[offset:offset + 4])[0]
        if size == 0 or size == 0xCCCCCCCC:
            break

        name_bytes = data[offset + 4:offset + 132]
        filename = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")
        if not filename:
            break

        entries.append({"filename": filename, "size": size})
        offset += ENTRY_SIZE

    return entries, offset  # data_offset = offset


def sanitize_filename(filename):
    """Remove or replace characters invalid on Windows."""
    # Remove non-printable / control characters
    cleaned = "".join(c for c in filename if c.isprintable() and c not in r'\/:*?"<>|')
    return cleaned.strip() or "_unnamed"


def extract_all(filepath, entries, data_offset, output_dir, progress_cb=None):
    """Extract all entries to output_dir. Calls progress_cb(i, total) each step."""
    total = len(entries)
    skipped = 0
    with open(filepath, "rb") as f:
        f.seek(data_offset)
        for i, entry in enumerate(entries):
            file_data = f.read(entry["size"])

            # Split path parts and sanitize each one
            parts = entry["filename"].replace("\\", "/").split("/")
            parts = [sanitize_filename(p) for p in parts]

            # Skip if the filename looks corrupted (too short or all underscores)
            if all(p in ("", "_unnamed") for p in parts):
                skipped += 1
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            out_path = Path(output_dir).joinpath(*parts)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as out:
                out.write(file_data)

            if progress_cb:
                progress_cb(i + 1, total)

    return skipped


# ─────────────────────────────────────────────
#  Main App
# ─────────────────────────────────────────────
class SFFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SFF Unpacker — SF Legends")
        self.root.configure(bg=BG)
        self.root.geometry("820x600")
        self.root.minsize(640, 480)
        self.root.resizable(True, True)

        self.current_file = None
        self.entries = []
        self.data_offset = 0

        self._build_ui()

    # ── UI Construction ─────────────────────────
    def _build_ui(self):
        self._style_ttk()
        self._build_header()
        self._build_drop_zone()
        self._build_file_list()
        self._build_bottom_bar()

    def _style_ttk(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
            background=BG2, foreground=TEXT,
            fieldbackground=BG2, borderwidth=0,
            font=FONT_MONO, rowheight=22)
        style.configure("Treeview.Heading",
            background=BG3, foreground=GREEN,
            font=("Segoe UI", 9, "bold"), borderwidth=0)
        style.map("Treeview",
            background=[("selected", GREEN_DIM)],
            foreground=[("selected", WHITE)])
        style.map("Treeview.Heading",
            background=[("active", BG3)])

        style.configure("Green.Horizontal.TProgressbar",
            troughcolor=BG3, background=GREEN,
            borderwidth=0, thickness=4)

        style.configure("Vertical.TScrollbar",
            background=BG3, troughcolor=BG2,
            arrowcolor=TEXT_DIM, borderwidth=0)
        style.configure("Horizontal.TScrollbar",
            background=BG3, troughcolor=BG2,
            arrowcolor=TEXT_DIM, borderwidth=0)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG, pady=0)
        hdr.pack(fill="x", padx=20, pady=(18, 0))

        tk.Label(hdr, text="⬡ SFF UNPACKER",
                 font=("Consolas", 15, "bold"),
                 fg=GREEN, bg=BG).pack(side="left")

        tk.Label(hdr, text="SF LEGENDS ARCHIVE TOOL",
                 font=FONT_SMALL, fg=TEXT_DIM, bg=BG).pack(side="left", padx=(10, 0), pady=(4, 0))

    def _build_drop_zone(self):
        self.drop_frame = tk.Frame(self.root, bg=BG, pady=0)
        self.drop_frame.pack(fill="x", padx=20, pady=(14, 0))

        self.drop_zone = tk.Frame(
            self.drop_frame, bg=BG2,
            bd=0, relief="flat",
            highlightbackground=BORDER,
            highlightthickness=2,
            cursor="hand2"
        )
        self.drop_zone.pack(fill="x")

        inner = tk.Frame(self.drop_zone, bg=BG2, pady=18)
        inner.pack(fill="x")

        self.drop_icon = tk.Label(inner, text="⬇", font=("Consolas", 22),
                                  fg=GREEN_DIM, bg=BG2)
        self.drop_icon.pack()

        self.drop_label = tk.Label(inner,
            text="Drag & drop a .sff file here",
            font=FONT_UI, fg=TEXT_DIM, bg=BG2)
        self.drop_label.pack(pady=(4, 0))

        self.browse_btn = tk.Label(inner,
            text="or click to browse",
            font=("Segoe UI", 9, "underline"),
            fg=GREEN_DIM, bg=BG2, cursor="hand2")
        self.browse_btn.pack(pady=(2, 0))

        # Bind click events
        for widget in [self.drop_zone, inner, self.drop_icon,
                        self.drop_label, self.browse_btn]:
            widget.bind("<Button-1>", lambda e: self._browse_file())
            widget.bind("<Enter>", lambda e: self._drop_hover(True))
            widget.bind("<Leave>", lambda e: self._drop_hover(False))

        # Register drag & drop if available
        if HAS_DND:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self.browse_btn.config(
                text="↑ tkinterdnd2 not installed — click to browse instead")

    def _build_file_list(self):
        list_frame = tk.Frame(self.root, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(14, 0))

        # Header row
        hrow = tk.Frame(list_frame, bg=BG)
        hrow.pack(fill="x", pady=(0, 6))

        self.list_title = tk.Label(hrow, text="No file loaded",
            font=FONT_HEAD, fg=TEXT, bg=BG)
        self.list_title.pack(side="left")

        self.count_label = tk.Label(hrow, text="",
            font=FONT_SMALL, fg=TEXT_DIM, bg=BG)
        self.count_label.pack(side="left", padx=(10, 0), pady=(4, 0))

        # Treeview + scrollbars
        tree_container = tk.Frame(list_frame, bg=BORDER, bd=1)
        tree_container.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal")

        self.tree = ttk.Treeview(
            tree_container,
            columns=("size", "type"),
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="extended"
        )
        self.tree.heading("size", text="SIZE", anchor="e")
        self.tree.heading("type", text="TYPE", anchor="w")
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("type", width=70, anchor="w", stretch=False)

        # Filename pseudo-column via tags on row text
        self.tree["displaycolumns"] = ("size", "type")
        self.tree["columns"] = ("filename", "size", "type")
        self.tree.heading("filename", text="FILENAME", anchor="w")
        self.tree.heading("size", text="SIZE", anchor="e")
        self.tree.heading("type", text="EXT", anchor="w")
        self.tree["displaycolumns"] = ("filename", "size", "type")
        self.tree.column("filename", width=480, anchor="w", stretch=True)
        self.tree.column("size", width=100, anchor="e", stretch=False)
        self.tree.column("type", width=60, anchor="w", stretch=False)

        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Alternating row colors
        self.tree.tag_configure("odd", background=BG2)
        self.tree.tag_configure("even", background=BG3)

    def _build_bottom_bar(self):
        bar = tk.Frame(self.root, bg=BG3, height=52)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=BG3)
        inner.pack(fill="both", expand=True, padx=20, pady=8)

        # Status label
        self.status_var = tk.StringVar(value="Ready — drop a .sff file to begin")
        self.status_label = tk.Label(inner,
            textvariable=self.status_var,
            font=FONT_MONO, fg=TEXT_DIM, bg=BG3, anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)

        # Progress bar (hidden until needed)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(inner,
            variable=self.progress_var,
            style="Green.Horizontal.TProgressbar",
            length=140, mode="determinate")

        # Extract button
        self.extract_btn = tk.Button(inner,
            text="EXTRACT ALL",
            font=("Consolas", 10, "bold"),
            fg=BG, bg=GREEN,
            activebackground=GREEN_DIM, activeforeground=WHITE,
            relief="flat", padx=18, pady=4,
            cursor="hand2",
            state="disabled",
            command=self._extract)
        self.extract_btn.pack(side="right", padx=(8, 0))

    # ── Interactions ─────────────────────────────
    def _drop_hover(self, entering):
        color = GREEN_DIM if entering else BORDER
        self.drop_zone.config(highlightbackground=color)

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")  # handle paths with spaces
        if path.lower().endswith(".sff"):
            self._load_file(path)
        else:
            self._set_status("⚠  Only .sff files are supported", error=True)

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Open .sff file",
            filetypes=[("SFF Archives", "*.sff"), ("All files", "*.*")]
        )
        if path:
            self._load_file(path)

    def _load_file(self, path):
        try:
            self._set_status(f"Parsing {Path(path).name}…")
            self.root.update()

            entries, data_offset = parse_sff(path)
            self.current_file = path
            self.entries = entries
            self.data_offset = data_offset

            self._populate_tree(entries)
            self._update_drop_zone_loaded(path)

            total_size = sum(e["size"] for e in entries)
            self.list_title.config(text=Path(path).name, fg=GREEN)
            self.count_label.config(
                text=f"{len(entries)} files  ·  {total_size / 1024:.1f} KB total")

            self.extract_btn.config(state="normal")
            self._set_status(f"✔  Loaded {len(entries)} files from {Path(path).name}")

        except Exception as e:
            self._set_status(f"Error: {e}", error=True)

    def _populate_tree(self, entries):
        self.tree.delete(*self.tree.get_children())
        for i, entry in enumerate(entries):
            ext = Path(entry["filename"]).suffix.lstrip(".").upper() or "—"
            size_str = self._fmt_size(entry["size"])
            tag = "odd" if i % 2 else "even"
            self.tree.insert("", "end",
                values=(entry["filename"].replace("\\", " / "), size_str, ext),
                tags=(tag,))

    def _update_drop_zone_loaded(self, path):
        name = Path(path).name
        self.drop_icon.config(text="✔", fg=GREEN)
        self.drop_label.config(text=name, fg=GREEN)
        self.browse_btn.config(text="click to load a different file", fg=TEXT_DIM)

    def _extract(self):
        if not self.current_file:
            return

        out_dir = filedialog.askdirectory(title="Choose output folder")
        if not out_dir:
            return

        self.extract_btn.config(state="disabled", text="EXTRACTING…")
        self.progress_bar.pack(side="right", padx=(0, 8))
        self.progress_var.set(0)
        self._set_status("Extracting…")

        def run():
            def on_progress(done, total):
                pct = (done / total) * 100
                self.progress_var.set(pct)
                self._set_status(f"Extracting… {done}/{total}")
                self.root.update_idletasks()

            try:
                extract_all(
                    self.current_file,
                    self.entries,
                    self.data_offset,
                    out_dir,
                    progress_cb=on_progress
                )
                self.root.after(0, self._extraction_done, out_dir)
            except Exception as e:
                self.root.after(0, self._extraction_error, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _extraction_done(self, out_dir):
        self.progress_var.set(100)
        self.extract_btn.config(state="normal", text="EXTRACT ALL")
        self._set_status(
            f"✔  Extracted {len(self.entries)} files → {out_dir}")
        self.root.after(1500, lambda: self.progress_bar.pack_forget())
        messagebox.showinfo(
            "Done!",
            f"Extracted {len(self.entries)} files to:\n{out_dir}")

    def _extraction_error(self, error):
        self.extract_btn.config(state="normal", text="EXTRACT ALL")
        self.progress_bar.pack_forget()
        self._set_status(f"Error: {error}", error=True)

    # ── Helpers ──────────────────────────────────
    def _set_status(self, msg, error=False):
        self.status_var.set(msg)
        self.status_label.config(fg=DANGER if error else TEXT_DIM)

    @staticmethod
    def _fmt_size(n):
        if n >= 1_048_576:
            return f"{n / 1_048_576:.1f} MB"
        if n >= 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n} B"


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    try:
        root.iconbitmap("icon.ico")
    except Exception:
        pass

    app = SFFApp(root)
    root.mainloop()


if __name__ == "__main__":

    main()
