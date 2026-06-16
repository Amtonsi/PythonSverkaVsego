from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from file_compare_app.analyzers.base import AnalyzerDependencyError
from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.orchestrator import compare_files
from file_compare_app.reports.html_report import render_html_report


class TkMainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.left_path: Path | None = None
        self.right_path: Path | None = None
        self.result: ComparisonResult | None = None
        self.root.title("Сравнение файлов")
        self.root.geometry("1320x820")
        self._configure_style()
        self._build()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#eef2f6")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#eef2f6", foreground="#111827", font=("Segoe UI", 18, "bold"))
        style.configure("Credit.TLabel", background="#ffffff", foreground="#8b95a7", font=("Segoe UI", 8, "bold"))
        style.configure("Mode.TLabel", background="#ecfdf8", foreground="#0f766e", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        outer = ttk.Frame(self.root, style="Root.TFrame", padding=14)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer, style="Root.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="СФ  Сравнение файлов  2026", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="  Строгий локальный режим  ", style="Mode.TLabel").pack(side=tk.RIGHT)

        actions = ttk.Frame(outer, style="Root.TFrame")
        actions.pack(fill=tk.X, pady=(12, 10))
        self.left_button = ttk.Button(actions, text="Файл 1", command=self._choose_left)
        self.right_button = ttk.Button(actions, text="Файл 2", command=self._choose_right)
        self.compare_button = ttk.Button(actions, text="Сравнить", style="Primary.TButton", command=self._compare)
        self.export_button = ttk.Button(actions, text="Экспорт отчета", command=self._export_report)
        for button in (self.left_button, self.right_button, self.compare_button, self.export_button):
            button.pack(side=tk.LEFT, padx=(0, 8))

        body = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        viewers = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        left_panel = self._text_panel(viewers, "Было")
        right_panel = self._text_panel(viewers, "Стало")
        viewers.add(left_panel[0], weight=1)
        viewers.add(right_panel[0], weight=1)
        self.left_view = left_panel[1]
        self.right_view = right_panel[1]

        side = ttk.Frame(body, style="Panel.TFrame", padding=(10, 0, 0, 0))
        self.summary = ttk.Label(side, text="Найдено 0 изменений", background="#ffffff", foreground="#111827", font=("Segoe UI", 14, "bold"))
        self.summary.pack(fill=tk.X, pady=(0, 8))
        self.changes_list = tk.Listbox(side, borderwidth=1, relief=tk.SOLID, activestyle="dotbox", font=("Segoe UI", 10))
        self.changes_list.pack(fill=tk.BOTH, expand=True)
        self.changes_list.bind("<<ListboxSelect>>", self._show_selected_change)

        body.add(viewers, weight=4)
        body.add(side, weight=1)

        footer = ttk.Frame(outer, style="Panel.TFrame", padding=(10, 7))
        footer.pack(fill=tk.X, pady=(10, 0))
        self.status = ttk.Label(footer, text="Готово", background="#ffffff", foreground="#0f766e", font=("Segoe UI", 9, "bold"))
        self.status.pack(side=tk.LEFT)
        ttk.Label(footer, text="Разработал: Абдрахманов Амаль Даулетович", style="Credit.TLabel").pack(side=tk.RIGHT)

    def _text_panel(self, parent: ttk.PanedWindow, title: str) -> tuple[ttk.Frame, tk.Text]:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        ttk.Label(frame, text=title, background="#ffffff", foreground="#667085", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        text = tk.Text(frame, wrap=tk.NONE, borderwidth=1, relief=tk.SOLID, font=("Consolas", 10), background="#ffffff")
        text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        text.configure(state=tk.DISABLED)
        return frame, text

    def _choose_left(self) -> None:
        path = filedialog.askopenfilename(title="Выберите исходный файл")
        if path:
            self.left_path = Path(path)
            self.left_button.configure(text=self.left_path.name)

    def _choose_right(self) -> None:
        path = filedialog.askopenfilename(title="Выберите измененный файл")
        if path:
            self.right_path = Path(path)
            self.right_button.configure(text=self.right_path.name)

    def _compare(self) -> None:
        if self.left_path is None or self.right_path is None:
            messagebox.showwarning("Не выбраны файлы", "Выберите два файла для сравнения.")
            return
        try:
            self.result = compare_files(self.left_path, self.right_path)
        except AnalyzerDependencyError as exc:
            messagebox.showwarning("Не хватает зависимости", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Ошибка сравнения", f"Не удалось сравнить файлы: {exc.__class__.__name__}")
            return
        self._render_result(self.result)

    def _render_result(self, result: ComparisonResult) -> None:
        self.summary.configure(text=f"Найдено {result.change_count} изменений")
        self.changes_list.delete(0, tk.END)
        for change in result.changes:
            place = change.target_location.display() if change.target_location else ""
            self.changes_list.insert(tk.END, f"{change.change_type}: {place}")
        if result.changes:
            self.changes_list.selection_set(0)
            self._show_change(0)
        else:
            self._set_text(self.left_view, "Изменений не найдено")
            self._set_text(self.right_view, "Изменений не найдено")
        self.status.configure(text="Сравнение выполнено локально")

    def _show_selected_change(self, _event: tk.Event[tk.Listbox]) -> None:
        selection = self.changes_list.curselection()
        if selection:
            self._show_change(selection[0])

    def _show_change(self, row: int) -> None:
        if self.result is None or row < 0 or row >= len(self.result.changes):
            return
        change = self.result.changes[row]
        self._set_text(self.left_view, change.before)
        self._set_text(self.right_view, change.after)

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state=tk.DISABLED)

    def _export_report(self) -> None:
        if self.result is None:
            messagebox.showinfo("Нет отчета", "Сначала выполните сравнение.")
            return
        path = filedialog.asksaveasfilename(title="Сохранить отчет", defaultextension=".html", filetypes=[("HTML", "*.html")])
        if not path:
            return
        Path(path).write_text(render_html_report(self.result), encoding="utf-8")
        self.status.configure(text=f"Отчет сохранен: {path}")


def run_tk_app() -> int:
    root = tk.Tk()
    TkMainWindow(root)
    root.mainloop()
    return 0
