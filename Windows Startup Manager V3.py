import os
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog, ttk
import winreg

# Registry-Pfade für Autostart-Einträge
RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
]

DISABLED_PREFIX = "_DISABLED_"

def get_startup_entries():
    entries = []
    for hive, path, location in RUN_KEYS:
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        is_disabled = name.startswith(DISABLED_PREFIX)
                        real_name = name[len(DISABLED_PREFIX):] if is_disabled else name
                        exec_path = extract_executable_path(value)
                        file_exists = exec_path and os.path.isfile(exec_path)
                        status = "Deaktiviert ❌" if is_disabled else ("Aktiv ✅" if file_exists else "Fehler ⚠️")
                        entries.append((real_name, value, location, status, name))  # store true key name too
                        i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            continue
    return entries

def extract_executable_path(value):
    value = value.strip()
    if value.startswith('"'):
        end_quote = value.find('"', 1)
        if end_quote != -1:
            return value[1:end_quote]
    else:
        parts = value.split(" ")
        return parts[0]
    return None

def rename_entry(old_name, new_name, location):
    for hive, path, loc in RUN_KEYS:
        if loc == location:
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    value, val_type = winreg.QueryValueEx(key, old_name)
                    winreg.SetValueEx(key, new_name, 0, val_type, value)
                    winreg.DeleteValue(key, old_name)
                    return True
            except FileNotFoundError:
                pass
    return False

def remove_entry(name, location):
    for hive, path, loc in RUN_KEYS:
        if loc == location:
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    winreg.DeleteValue(key, name)
                    return True
            except FileNotFoundError:
                pass
    return False

def add_entry(name, path, location, disabled=False):
    real_name = f"{DISABLED_PREFIX}{name}" if disabled else name
    for hive, reg_path, loc in RUN_KEYS:
        if loc == location:
            try:
                with winreg.OpenKey(hive, reg_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, real_name, 0, winreg.REG_SZ, path)
                    return True
            except FileNotFoundError:
                pass
    return False

class StartupManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Windows Startup Manager")
        self.geometry("1000x500")
        self.resizable(False, False)
        self.create_widgets()
        self.refresh()

    def create_widgets(self):
        columns = ("Name", "Pfad", "Ort", "Status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.column("Name", width=150)
        self.tree.column("Pfad", width=500)
        self.tree.column("Ort", width=80)
        self.tree.column("Status", width=120)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frame = tk.Frame(self)
        frame.pack(pady=5)

        tk.Button(frame, text="➕ Hinzufügen", width=15, command=self.add_entry_ui).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="🗑️ Entfernen", width=15, command=self.remove_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="⛔ Deaktivieren", width=15, command=self.deactivate_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="✅ Aktivieren", width=15, command=self.activate_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="🔄 Aktualisieren", width=15, command=self.refresh).pack(side=tk.LEFT, padx=5)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.entries = get_startup_entries()
        for entry in self.entries:
            real_name, value, location, status, true_key_name = entry
            self.tree.insert("", tk.END, values=(real_name, value, location, status), tags=(true_key_name,))

    def get_selected_entries(self):
        selected = []
        for sel in self.tree.selection():
            values = self.tree.item(sel)["values"]
            tags = self.tree.item(sel)["tags"]
            selected.append((*values, tags[0]))  # (name, value, location, status, true_key_name)
        return selected

    def remove_selected(self):
        for name, _, location, _, true_name in self.get_selected_entries():
            if messagebox.askyesno("Entfernen", f"{name} ({location}) wirklich dauerhaft entfernen?"):
                remove_entry(true_name, location)
        self.refresh()

    def deactivate_selected(self):
        for name, value, location, status, true_name in self.get_selected_entries():
            if not true_name.startswith(DISABLED_PREFIX):
                rename_entry(true_name, f"{DISABLED_PREFIX}{name}", location)
        self.refresh()

    def activate_selected(self):
        for name, value, location, status, true_name in self.get_selected_entries():
            if true_name.startswith(DISABLED_PREFIX):
                rename_entry(true_name, name, location)
        self.refresh()

    def add_entry_ui(self):
        name = simpledialog.askstring("Eintragsname", "Gib einen Namen für den Autostart-Eintrag ein:")
        if not name:
            return
        path = filedialog.askopenfilename(title="Programmdatei auswählen")
        if not path:
            return
        location = simpledialog.askstring("Ort", "HKCU oder HKLM? (Standard: HKCU)")
        location = location.upper() if location else "HKCU"
        if location not in ["HKCU", "HKLM"]:
            messagebox.showerror("Fehler", "Ungültiger Ort! Nur 'HKCU' oder 'HKLM' erlaubt.")
            return
        disabled = not messagebox.askyesno("Sofort aktivieren?", "Soll der Eintrag sofort aktiv sein?")
        success = add_entry(name, f'"{path}"', location, disabled=disabled)
        if success:
            self.refresh()
        else:
            messagebox.showerror("Fehler", "Eintrag konnte nicht hinzugefügt werden.")

if __name__ == "__main__":
    app = StartupManagerApp()
    app.mainloop()
