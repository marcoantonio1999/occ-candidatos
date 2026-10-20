"""Native Windows UI: user chooses a local folder, no browser or server."""
import multiprocessing
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from converter import VERSION, convert_folder


class App:
    def __init__(self, root):
        self.root, self.events = root, queue.Queue()
        self.busy, self.cancelled, self.result = False, threading.Event(), None
        root.title('Indeed JSON a Excel · BPower')
        root.geometry('760x600')
        root.minsize(620, 580)
        root.configure(bg='#f3f6f3')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#f3f6f3')
        style.configure('TLabel', background='#f3f6f3', foreground='#22362e', font=('Segoe UI', 11))
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('TButton', padding=(16, 12), font=('Segoe UI', 11))
        style.configure('Primary.TButton', background='#315546', foreground='white')
        style.map('Primary.TButton', background=[('active', '#244235'), ('disabled', '#d6ded8')])
        style.configure('TProgressbar', background='#315546')
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='BPOWER  ·  RECURSOS HUMANOS', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='De Indeed a Excel', style='Title.TLabel').pack(anchor='w', pady=(10, 6))
        ttk.Label(frame, text='Reúne los JSON de las postulaciones en una carpeta.\nElige esa carpeta y el Excel se genera automáticamente.', justify='left').pack(anchor='w')
        self.choose = ttk.Button(frame, text='Seleccionar carpeta y generar Excel', style='Primary.TButton', command=self.select)
        self.choose.pack(fill='x', pady=(18, 8))
        self.path = ttk.Label(frame, text='No has seleccionado una carpeta.', wraplength=680)
        self.path.pack(anchor='w', fill='x', pady=(0, 8))
        self.bar = ttk.Progressbar(frame, mode='determinate')
        self.bar.pack(fill='x')
        self.status = ttk.Label(frame, text='Listo para comenzar.', wraplength=680, justify='left')
        self.status.pack(anchor='w', fill='x', pady=10)
        actions = ttk.Frame(frame)
        actions.pack(fill='x')
        self.open_excel = ttk.Button(actions, text='Abrir Excel', command=self.open_workbook, state='disabled')
        self.open_excel.pack(side='left', padx=(0, 8))
        self.open_folder = ttk.Button(actions, text='Ver resultados', command=self.open_results, state='disabled')
        self.open_folder.pack(side='left')
        self.stop = ttk.Button(actions, text='Pausar', command=self.cancelled.set, state='disabled')
        self.stop.pack(side='right')
        ttk.Separator(frame).pack(fill='x', pady=14)
        ttk.Label(frame, text='100 % local · Sin iniciar sesión · No cambia las postulaciones', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Incluye correo, teléfono y CV PDF si vienen en el JSON.\nLos CV escaneados quedan señalados para revisión.\nNo modifica tus archivos originales ni sobrescribe otro Excel.', font=('Segoe UI', 10)).pack(anchor='w', pady=4)
        ttk.Label(frame, text=f'Aplicación independiente para Windows · v{VERSION}', font=('Segoe UI', 9)).pack(anchor='w')
        root.bind('<Configure>', self.resize)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.poll)

    def resize(self, event):
        if event.widget == self.root:
            for widget in (self.status, self.path):
                widget.configure(wraplength=max(400, event.width - 65))

    def select(self):
        folder = filedialog.askdirectory(parent=self.root, title='Selecciona la carpeta con los JSON de Indeed', mustexist=True)
        if not folder:
            return
        self.path.configure(text=folder)
        self.busy, self.result = True, None
        self.cancelled.clear()
        self.choose.configure(state='disabled')
        self.open_excel.configure(state='disabled')
        self.open_folder.configure(state='disabled')
        self.stop.configure(state='normal')
        self.status.configure(text='Leyendo JSON y recuperando CV…')
        def work():
            try:
                result = convert_folder(folder, lambda i, total: self.events.put(('progress', (i, total))), self.cancelled.is_set)
                self.events.put(('done', result))
            except ValueError as error:
                self.events.put(('error', str(error)))
            except Exception:
                self.events.put(('error', 'No se pudo generar el resultado. Revisa los permisos y el espacio disponible de la carpeta. Tus JSON siguen intactos.'))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'progress':
                    i, total = value
                    self.bar.configure(maximum=total, value=i - 1)
                    self.status.configure(text=f'Procesando JSON {i} de {total}…')
                else:
                    self.busy = False
                    self.choose.configure(state='normal')
                    self.stop.configure(state='disabled')
                    if kind == 'error':
                        self.status.configure(text=value, foreground='#a3313c')
                    else:
                        self.result = value
                        self.bar.configure(value=value['total'])
                        self.status.configure(text=f"{'Proceso pausado.' if self.cancelled.is_set() else 'Terminado.'} {value['count']} postulaciones en Excel.\n{value['duplicates']} duplicados omitidos · {value['errors']} incidencias.\nRevisa LEEME-resultado.txt si hay incidencias.", foreground='#22362e')
                        self.open_folder.configure(state='normal')
                        if value['excel']:
                            self.open_excel.configure(state='normal')
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def open_workbook(self):
        self.open_path(self.result['excel'])

    def open_results(self):
        self.open_path(self.result['output'])

    def open_path(self, path):
        try:
            os.startfile(path)
        except OSError:
            messagebox.showerror('No se pudo abrir', 'Abre el resultado desde la carpeta seleccionada. Para ver .xlsx necesitas Excel u otra aplicación compatible.', parent=self.root)

    def close(self):
        if self.busy:
            messagebox.showinfo('Procesando', 'Pulsa Pausar y espera a que termine el archivo actual antes de cerrar.', parent=self.root)
        else:
            self.root.destroy()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from pathlib import Path
        import pypdf
        Path(sys.argv[2]).write_text('OK ' + VERSION, encoding='utf-8')
    else:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        App(tk.Tk()).root.mainloop()
