from tkinter import *
from tkinter import messagebox, filedialog, ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import os
import time
from datetime import datetime
import json
import serial
import serial.tools.list_ports
import sys
import threading
import queue
from collections import deque
import platform

config = {}
with open("config.json", 'r') as file:
    config = json.load(file)

def get_available_serial_ports():
    """Zwraca listę dostępnych portów szeregowych według systemu"""
    ports = []
    try:
        # Automatyczne wykrywanie portów
        available_ports = serial.tools.list_ports.comports()
        for port in available_ports:
            ports.append(port.device)
    except:
        pass
    
    if not ports:
        # Domyślne porty według systemu
        system = platform.system().lower()
        if 'windows' in system:
            ports = ['COM1', 'COM2', 'COM3', 'COM4', 'COM5']
        elif 'linux' in system:
            ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyS0', '/dev/ttyS1']
        elif 'darwin' in system:  # macOS
            ports = ['/dev/tty.usbserial', '/dev/tty.usbmodem', '/dev/cu.usbserial', '/dev/cu.usbmodem']
        else:
            ports = ['/dev/ttyUSB0', '/dev/ttyACM0']  # Domyślnie Linux
    
    return ports if ports else ['brak_portów']

def get_default_serial_port():
    """Zwraca domyślny port szeregowy według systemu"""
    system = platform.system().lower()
    if 'windows' in system:
        return 'COM4'
    elif 'linux' in system:
        # Sprawdź które porty faktycznie istnieją
        common_linux_ports = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1', '/dev/ttyACM1']
        for port in common_linux_ports:
            if os.path.exists(port):
                return port
        return '/dev/ttyUSB0'  # Domyślny jeśli nic nie znaleziono
    elif 'darwin' in system:  # macOS
        return '/dev/cu.usbserial'
    else:
        return '/dev/ttyUSB0'

class SerialCommunicator:
    """Klasa odpowiedzialna za komunikację z urządzeniem w osobnym wątku"""
    
    def __init__(self, port=None, baud_rate=9600, console_func=None):
        self.port = port or get_default_serial_port()
        self.baud_rate = baud_rate
        self.console_func = console_func or (lambda x: None)
        self.connection = None
        self.connected = False
        self.running = False
        self.thread = None
        self.gui_update_thread = None
        self.gui_running = False
        
        # Kolejki do komunikacji między wątkami
        self.data_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        # Bufory danych
        self.temperature_buffer = deque(maxlen=10000)
        self.current_buffer = deque(maxlen=10000)
        self.time_buffer = deque(maxlen=10000)
        
        # Ostatnie odczytane wartości
        self.last_temperature = 0.0
        self.last_current = 0.0
        self.set_temperature = 20.0
        
        self.start_time = time.time()
        
    def connect(self):
        """Nawiązuje połączenie z urządzeniem"""
        try:
            # Sprawdź czy port istnieje (ważne na Linuxie)
            if not platform.system().lower().startswith('win') and not os.path.exists(self.port):
                self.console_func(f"Port {self.port} nie istnieje")
                return False
                
            self.connection = serial.Serial(self.port, self.baud_rate, timeout=0.5)
            self.connected = True
            self.console_func(f"Połączono z urządzeniem na porcie {self.port}")
            return True
        except serial.SerialException as e:
            self.connected = False
            self.console_func(f"Błąd połączenia szeregowego z portem {self.port}: {e}")
            return False
        except PermissionError as e:
            self.connected = False
            self.console_func(f"Brak uprawnień do portu {self.port}: {e}")
            self.console_func("Na Linuxie spróbuj: sudo usermod -a -G dialout $USER")
            return False
        except Exception as e:
            self.connected = False
            self.console_func(f"Błąd połączenia z portem {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Rozłącza z urządzeniem i zatrzymuje wątki"""
        self.running = False
        self.gui_running = False
        
        if self.thread:
            self.thread.join(timeout=2)
        if self.gui_update_thread:
            self.gui_update_thread.join(timeout=1)
            
        if self.connection:
            self.connection.close()
        self.connected = False
        self.console_func("Rozłączono z urządzeniem")
    
    def start_communication(self):
        """Rozpoczyna komunikację w osobnym wątku"""
        if not self.connected:
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self._communication_loop, daemon=True)
        self.thread.start()
        self.console_func("Rozpoczęto komunikację w tle")
        return True
    
    def start_gui_updates(self, update_callback, interval=0.2):
        """Rozpoczyna aktualizacje GUI w osobnym wątku"""
        if self.gui_running:
            return
            
        self.gui_running = True
        self.update_callback = update_callback
        self.update_interval = interval
        self.gui_update_thread = threading.Thread(target=self._gui_update_loop, daemon=True)
        self.gui_update_thread.start()
        self.console_func("Rozpoczęto aktualizacje GUI w tle")
    
    def stop_gui_updates(self):
        """Zatrzymuje aktualizacje GUI"""
        self.gui_running = False
        if self.gui_update_thread:
            self.gui_update_thread.join(timeout=1)
    
    def _gui_update_loop(self):
        """Pętla aktualizacji GUI działająca w tle"""
        while self.gui_running and self.connected:
            try:
                if hasattr(self, 'update_callback') and self.update_callback:
                    self.update_callback()
                time.sleep(self.update_interval)
            except Exception as e:
                self.console_func(f"Błąd aktualizacji GUI: {e}")
                break
    
    def _communication_loop(self):
        """Główna pętla komunikacji działająca w tle"""
        commands = ['*GETTPRS;', '*GETTACT;', '*GETIOUT;']
        command_index = 0
        error_count = 0
        max_errors = 10
        
        while self.running and self.connected and error_count < max_errors:
            try:
                # Sprawdź czy są komendy do wysłania
                try:
                    command = self.command_queue.get_nowait()
                    self.connection.write(str.encode(command))
                    self.connection.flush()  # Wymusza wysłanie
                except queue.Empty:
                    pass
                except Exception as e:
                    self.console_func(f"Błąd wysyłania komendy: {e}")
                    error_count += 1
                    continue
                
                # Wysyłaj standardowe zapytania cyklicznie
                try:
                    if not self.connection.in_waiting:
                        command = commands[command_index]
                        self.connection.write(str.encode(command))
                        self.connection.flush()
                        command_index = (command_index + 1) % len(commands)
                        
                except Exception as e:
                    self.console_func(f"Błąd wysyłania standardowego zapytania: {e}")
                    error_count += 1
                    continue
                
                # Odbierz dane
                try:
                    if self.connection.in_waiting:
                        response = self.connection.readline().decode('Latin-1').strip()
                        if response:
                            self._process_response(response)
                            error_count = 0  # Reset licznika błędów po udanej komunikacji
                            
                except Exception as e:
                    self.console_func(f"Błąd odbioru danych: {e}")
                    error_count += 1
                    continue
                
                time.sleep(0.1)  # Krótka pauza
                
            except Exception as e:
                self.console_func(f"Nieoczekiwany błąd komunikacji: {e}")
                error_count += 1
                
        if error_count >= max_errors:
            self.console_func(f"Zbyt wiele błędów komunikacji ({error_count}), zatrzymywanie...")
            self.connected = False
        
        self.console_func("Zakończono pętlę komunikacji")
    
    def _process_response(self, response):
        """Przetwarza odpowiedzi z urządzenia"""
        current_time = time.time() - self.start_time
        
        try:
            if '*TPRS ' in response:
                self.set_temperature = float(response[5:12])
                
            elif '*TACT ' in response:
                self.last_temperature = float(response[5:12])
                self.temperature_buffer.append(self.last_temperature)
                self.time_buffer.append(current_time)
                
                # Wyślij dane do GUI
                self.data_queue.put({
                    'type': 'temperature',
                    'value': self.last_temperature,
                    'time': current_time
                })
                
            elif '*IOUT ' in response:
                current_str = response[9:15].replace('A', '')
                self.last_current = float(current_str)
                self.current_buffer.append(self.last_current)
                
                # Wyślij dane do GUI
                self.data_queue.put({
                    'type': 'current',
                    'value': self.last_current,
                    'time': current_time
                })
                
        except (ValueError, IndexError) as e:
            self.console_func(f"Błąd parsowania odpowiedzi '{response}': {e}")
    
    def send_command(self, command):
        """Dodaje komendę do kolejki wysyłania"""
        if self.connected:
            self.command_queue.put(command)
            self.console_func(f"Dodano komendę do kolejki: {command}")
        else:
            self.console_func("Brak połączenia - komenda nie została wysłana")
    
    def get_latest_data(self):
        """Pobiera najnowsze dane z kolejki"""
        data = []
        try:
            while True:
                data.append(self.data_queue.get_nowait())
        except queue.Empty:
            pass
        return data
    
    def get_all_data(self):
        """Zwraca wszystkie zebrane dane"""
        return {
            'temperature': list(self.temperature_buffer),
            'current': list(self.current_buffer),
            'time': list(self.time_buffer)
        }

class App(Tk):
    def __init__(self, *args, **kwargs):
        Tk.__init__(self, *args, **kwargs)
        
        self.container = Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        # Konfiguracja
        self.port_choice = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
        self.port = StringVar(self)
        self.port.set(config['port'])
        
        # Wykryj dostępne porty szeregowe
        self.available_ports = get_available_serial_ports()
        self.serial_port = StringVar(self)
        current_serial_port = config.get('serial_port', get_default_serial_port())
        self.serial_port.set(current_serial_port)
        
        self.tempRange_choice = ['-10 /+50', '-10 /+100', '-100 /+10', '-50 /+50', '+15 /+30', '+30 /+45', '+45 /+60', '-100 /+250']
        self.temp = StringVar(self)
        self.temp.set(config['temp_range'])
        self.v = config['pid']
        self.graphFold = config['fold']
        
        # GUI
        self.frame = StartPage(self.container, self)
        self.frame.grid(row=0, column=0, sticky="nsew")
        self.frame.tkraise()
        
        # Inicjalizacja komunikacji (po utworzeniu GUI)
        selected_port = self.serial_port.get()
        self.communicator = SerialCommunicator(port=selected_port, baud_rate=int(self.port.get()), 
                                             console_func=self.frame.console_data)
        self.connected = self.communicator.connect()
        
        # Rozpocznij komunikację w tle
        if self.connected:
            self.communicator.start_communication()
            # Rozpocznij aktualizacje GUI w osobnym wątku
            self.communicator.start_gui_updates(self._threaded_gui_update, interval=0.15)
            self.console_data("Połączono z urządzeniem - komunikacja i GUI działają w osobnych wątkach")
        else:
            self.console_data('Brak połączenia z urządzeniem')
    
    def _threaded_gui_update(self):
        """Aktualizacja GUI wywoływana z osobnego wątku"""
        try:
            # Pobierz nowe dane z komunikatora
            new_data = self.communicator.get_latest_data()
            
            # Przekaż dane do GUI w bezpieczny sposób (thread-safe)
            if new_data:
                # Użyj after() do bezpiecznego wywołania w głównym wątku GUI
                self.after_idle(lambda: self.frame.process_new_data(new_data))
                self.after_idle(lambda: self.frame.update_graph())
            
        except Exception as e:
            self.console_data(f"Błąd aktualizacji GUI z wątku: {e}")

    def update_graph(self):
        """Uproszczona metoda - główna logika jest teraz w _threaded_gui_update"""
        pass  # Ta metoda jest teraz nieaktywna - GUI aktualizuje się przez wątek
        
    def on_closing(self, c=True):
        """Zamknięcie aplikacji z opcją zapisania danych"""
        answer = messagebox.askquestion("Ostrzeżenie", "Czy chcesz zapisać dane?", icon="warning")
        if answer == "yes":
            try:
                # Pobierz wszystkie dane z komunikatora
                all_data = self.communicator.get_all_data()
                
                if self.frame.start != 0 and len(all_data['time']) > 0:
                    self.frame.stop = len(all_data['time']) - 1
                    self.console_data(f'Test Stop: {all_data["time"][self.frame.stop]:.2f}s')
                
                # Zatrzymaj urządzenie
                if self.connected:
                    self.communicator.send_command('a')
                
                # Wybierz katalog do zapisania
                dir = filedialog.askdirectory()
                if dir is None:
                    return
                
                # Utwórz unikalną nazwę katalogu
                name = 'pomiar-{}'.format(datetime.today().strftime('%Y-%m-%d'))
                existing_folders = [f for f in os.listdir(dir) if os.path.isdir(os.path.join(dir, f))]
                
                if name not in existing_folders:
                    save_dir = os.path.join(dir, name)
                    os.makedirs(save_dir)
                else:
                    matching_folders = [f for f in existing_folders if f.startswith(name) and f[-2:].replace('(', '').replace(')', '').isdigit()]
                    save_dir = os.path.join(dir, f'{name} ({len(matching_folders) + 1})')
                    os.makedirs(save_dir)
                
                # Zapisz wykres
                plot_path = os.path.join(save_dir, "plot.png")
                self.frame.fig.savefig(plot_path, dpi=300, bbox_inches='tight')
                self.console_data(f"Wykres zapisany: {plot_path}")
                
                # Przygotuj dane do zapisu
                start_idx = self.frame.start if self.frame.start != 0 else 0
                stop_idx = self.frame.stop if self.frame.stop != 0 else len(all_data['time'])
                
                save_data = {
                    "metadata": {
                        "start_time": datetime.now().isoformat(),
                        "measurement_duration": all_data['time'][stop_idx-1] - all_data['time'][start_idx] if stop_idx > start_idx else 0,
                        "total_samples": stop_idx - start_idx,
                        "config": config.copy()
                    },
                    "temperature": all_data['temperature'][start_idx:stop_idx],
                    "current": all_data['current'][start_idx:stop_idx], 
                    "time": all_data['time'][start_idx:stop_idx]
                }
                
                # Zapisz dane JSON
                json_path = os.path.join(save_dir, "data.json")
                with open(json_path, "w") as json_file:
                    json.dump(save_data, json_file, indent=4)
                self.console_data(f"Dane zapisane: {json_path}")
                
                # Zapisz log tekstowy
                log_path = os.path.join(save_dir, "measurement_log.txt")
                with open(log_path, "w") as log_file:
                    log_file.write(f"Pomiar temperatury - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    log_file.write(f"Czas pomiaru: {save_data['metadata']['measurement_duration']:.2f}s\n")
                    log_file.write(f"Liczba próbek: {save_data['metadata']['total_samples']}\n")
                    log_file.write(f"Konfiguracja: {save_data['metadata']['config']}\n")
                
                messagebox.showinfo("Sukces", f"Dane zapisane w: {save_dir}")
                
            except Exception as e:
                self.console_data(f"Błąd zapisywania danych: {e}")
                messagebox.showerror("Błąd", f"Nie udało się zapisać danych: {e}")
        
        if c:
            # Zatrzymaj wątki i zamknij komunikację
            self.communicator.stop_gui_updates()
            self.communicator.disconnect()
            self.destroy()
        else:
            self.frame.start = 0
        
    def import_config(self):
        """Importuje konfigurację z pliku JSON"""
        try:
            file_path = filedialog.askopenfilename(
                title="Wybierz plik konfiguracji",
                filetypes=[("Pliki JSON", "*.json")],
            )
            
            if not file_path:
                return
                
            with open(file_path, 'r') as config_file:
                new_config = json.load(config_file)
                
            # Walidacja konfiguracji
            required_keys = ['port', 'temp_range', 'fold', 'pid', 'current_off']
            missing_keys = [key for key in required_keys if key not in new_config]
            
            if missing_keys:
                messagebox.showerror("Błąd", f"Brakuje kluczy w konfiguracji: {missing_keys}")
                return
            
            # Aktualizuj globalną konfigurację
            global config
            config.update(new_config)
            
            # Aktualizuj GUI
            self.port.set(config['port'])
            self.temp.set(config['temp_range'])
            self.v = config['pid']
            self.graphFold = config['fold']
            
            # Zapisz nową konfigurację
            with open('config.json', 'w') as config_file:
                json.dump(config, config_file, indent=4)
            
            self.console_data(f"Zaimportowano konfigurację z: {file_path}")
            messagebox.showinfo("Sukces", "Konfiguracja została zaimportowana")
            
        except Exception as e:
            self.console_data(f"Błąd importu konfiguracji: {e}")
            messagebox.showerror("Błąd", f"Nie udało się zaimportować konfiguracji:\n{e}")

    def export_config(self):
        """Eksportuje konfigurację do pliku JSON"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Zapisz konfigurację jako",
                defaultextension=".json",
                filetypes=[("Pliki JSON", "*.json")],
            )
            
            if not file_path:
                return
                
            # Dodaj metadane do eksportu
            export_data = {
                "metadata": {
                    "export_date": datetime.now().isoformat(),
                    "app_version": "2.0",
                    "description": "Konfiguracja kontrolera temperatury"
                },
                "config": config.copy()
            }
            
            with open(file_path, "w") as config_file:
                json.dump(export_data, config_file, indent=4)
            
            self.console_data(f"Wyeksportowano konfigurację do: {file_path}")
            messagebox.showinfo("Sukces", f"Konfiguracja została wyeksportowana do:\n{file_path}")
            
        except Exception as e:
            self.console_data(f"Błąd eksportu konfiguracji: {e}")
            messagebox.showerror("Błąd", f"Nie udało się wyeksportować konfiguracji:\n{e}")

class StartPage(LabelFrame):
    def __init__(self, parent, controller):
        LabelFrame.__init__(self, parent)
        self.controller = controller
        
        # Bufory danych do wyświetlania
        self.data = [0]
        self.current = [0]
        self.time = [0]
        self.sent_data_value = 20.0
        
        # Konsola do wyświetlania komunikatów (bez przekierowania stdout)
        
        self.time_start = time.time()
        self.time_change = time.time()
        self.start = 0
        self.stop = 0
        self.r = 1
        
        self.setup_ui()
        self.setup_graph()
        
    def setup_ui(self):
        """Konfiguruje elementy interfejsu"""
        self.entry = Entry(self, validate="key", validatecommand=(self.controller.register(self.validate_entry), '%P'))
        self.entry.bind("<Return>", lambda e: self.send_serial_data())
        self.entry.grid(row=0, column=1)

        self.send_button = Button(self, text="Wyślij dane", command=self.send_serial_data)
        self.send_button.grid(row=1, column=1)
        
        self.start_button = Button(self, text="Start", command=self.start_collect)
        self.start_button.grid(row=1, column=2, sticky='e')
        
        self.stop_button = Button(self, text="Stop", command=lambda: self.controller.on_closing(False))
        self.stop_button.grid(row=1, column=3, sticky='w')

        self.last_data_label = Label(self)
        self.last_data_label.grid(row=1, column=2, sticky='w')

        self.set_data_label = Label(self, text=f"Temp. zadana: {self.sent_data_value}°C")
        self.set_data_label.grid(row=0, column=2, sticky='w')
        
        self.current_off_v = IntVar()
        self.current_off_v.set(config['current_off'])
        self.current_off = Checkbutton(self, variable=self.current_off_v, onvalue=True, offvalue=False, command=self.change_current)
        self.current_off.grid(row=0, column=2, sticky='e')
        
        self.current_off_text = Label(self, text=f"Prąd płynie: {bool(self.current_off_v.get())}")
        self.current_off_text.grid(row=0, column=3, sticky='w')

        self.measure_time = Label(self)
        self.measure_time.grid(row=0, column=4)

        self.changed_time = Label(self)
        self.changed_time.grid(row=1, column=4)
        
        self.console = Text(self, height=8)
        self.console.grid(row=2, column=1, columnspan=3)
        
        # Dodaj scrollbar do konsoli
        scrollbar = Scrollbar(self)
        scrollbar.grid(row=2, column=4, sticky='ns')
        self.console.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.console.yview)
        
        for widget in self.winfo_children():
            widget.grid_configure(padx=5, pady=5, rowspan=1)
    
    def setup_graph(self):
        """Konfiguruje wykres"""
        self.fig = Figure(figsize=(5, 5), dpi=100)
        self.fig.patch.set_facecolor('#F0F0F0')
        self.ax1 = self.fig.add_subplot(1, 1, 1)
        self.ax2 = self.ax1.twinx()
        self.ax1.grid()
        self.line, = self.ax1.plot(self.time, self.data, 'g', label='Temperatura')
        self.current_data_line, = self.ax2.plot(self.time, self.current, 'orange', label='Prąd')
        
        maxv = float(self.controller.temp.get().split(' /')[1])
        minv = float(self.controller.temp.get().split(' /')[0])
        
        self.last_data_text = self.ax1.text(0, 0, "0", ha='right', va='bottom', fontsize=8, color='red')
        self.last_current_text = self.ax2.text(0, 0, "0", ha='right', va='bottom', fontsize=8, color='orange')
        self.up_range_text = self.ax1.text(self.time[-1]*0.8, maxv, f"max: {maxv:.3f}°C", ha='right', va='top', fontsize=8, color='grey')
        self.down_range_text = self.ax1.text(self.time[-1]*0.8, minv, f"min: {minv:.3f}°C", ha='right', va='bottom', fontsize=8, color='grey')
        
        self.up_range = self.ax1.axhline(y=maxv, color='grey', linestyle='--')
        self.down_range = self.ax1.axhline(y=minv, color='grey', linestyle='--')
        self.sent_data_line = self.ax1.axhline(y=self.sent_data_value, color='r', linestyle='--', label='Zadana')
        
        self.ax1.set_ylabel('Temperatura (°C)')
        self.ax2.set_ylabel('Prąd (A)')
        self.ax1.set_xlabel('Czas (s)')
        self.ax1.legend(loc='upper left')
        self.ax2.legend(loc='upper right')
        
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", rowspan=20)
    
    def setup_graph_ranges(self):
        """Aktualizuje zakresy wykresu według aktualnych ustawień temperatury"""
        try:
            temp_range = self.controller.temp.get().split(' /')
            maxv = float(temp_range[1])
            minv = float(temp_range[0])
            
            # Aktualizuj linie zakresów
            self.up_range.set_ydata([maxv])
            self.down_range.set_ydata([minv])
            
            # Aktualizuj teksty
            if len(self.time) > 0:
                self.up_range_text.set_position((self.time[-1]*0.8, maxv))
                self.up_range_text.set_text(f"max: {maxv:.1f}°C")
                self.down_range_text.set_position((self.time[-1]*0.8, minv))
                self.down_range_text.set_text(f"min: {minv:.1f}°C")
            
            # Wymusza odświeżenie wykresu
            self.canvas.draw()
            self.console_data(f"Zaktualizowano zakresy wykresu: {minv}°C do {maxv}°C")
            
        except Exception as e:
            self.console_data(f"Błąd aktualizacji zakresów wykresu: {e}")
    
    def process_new_data(self, new_data_list):
        """Przetwarza nowe dane z komunikatora"""
        for data_item in new_data_list:
            current_time = data_item['time']
            
            if data_item['type'] == 'temperature':
                self.data.append(data_item['value'])
                if len(self.time) < len(self.data):
                    self.time.append(current_time)
                    
            elif data_item['type'] == 'current':
                self.current.append(data_item['value'])
    
    def change_current(self):
        """Zmienia stan prądu"""
        config['current_off'] = bool(self.current_off_v.get())
        with open('config.json', "w") as config_file:
            json.dump(config, config_file, indent=4)
        
        self.current_off_text.config(text=f"Prąd płynie: {bool(self.current_off_v.get())}")
        
        # Wyślij komendę do urządzenia
        command = 'A' if config['current_off'] else 'a'
        self.controller.communicator.send_command(command)
        self.console_data(f"Zmiana stanu prądu: {'włączony' if config['current_off'] else 'wyłączony'}")
        
    def console_data(self, message):
        """Dodaje wiadomość do konsoli"""
        timestamp = time.strftime("%H:%M:%S")
        self.console.insert(INSERT, f'{timestamp}: {message}\n')
        self.console.see("end")
        
    def start_collect(self):
        """Rozpoczyna zbieranie danych do analizy"""
        self.start = len(self.data) - 1
        self.console_data(f'Test Start: {self.time[self.start]:.2f}s')
        
    def send_serial_data(self):
        """Wysyła dane temperatury do urządzenia"""
        self.time_change = time.time()
        temp_range = self.controller.temp.get().split(' /')
        
        try:
            value = float(self.entry.get()) if self.entry.get() else self.sent_data_value
            value = max(min(value, float(temp_range[1])), float(temp_range[0]))
        except ValueError:
            value = self.sent_data_value
        
        self.sent_data_value = value
        
        # Wyślij komendę
        command = f'*SETTPRS{self.sent_data_value};'
        self.controller.communicator.send_command(command)
        self.console_data(f'Ustawiono temperaturę: {self.sent_data_value}°C')
        
        # Aktualizuj interfejs
        self.sent_data_line.set_ydata([self.sent_data_value])
        self.up_range.set_ydata([float(temp_range[1])])
        self.down_range.set_ydata([float(temp_range[0])])
        self.set_data_label.config(text=f"Temp. zadana: {self.sent_data_value}°C")
        
        self.entry.delete(0, END)

    def update_graph(self):
        """Aktualizuje wykres"""
        try:
            if len(self.data) == 0 or len(self.time) == 0:
                return
                
            current_time = f"{(time.time() - self.time_start):.2f}"
            
            # Ustaw zakres wyświetlania
            if self.time[-1] > 20 and self.controller.graphFold:
                self.r = self.time[-1] - 20
            elif not self.controller.graphFold:
                self.r = 0.1
            
            # Aktualizuj linie wykresu
            self.line.set_data(self.time, self.data)
            
            if len(self.time) == len(self.current) and len(self.current) > 0:
                self.current_data_line.set_data(self.time, self.current)
                
                # Ustaw zakresy osi
                self.ax1.set_xlim(self.r, self.time[-1])
                self.ax1.set_ylim(min(self.data) - 5, max(self.data) + 5)
                self.ax2.set_xlim(self.r, self.time[-1])
                self.ax2.set_ylim(min(self.current) - 1, max(self.current) + 1)
                
                # Aktualizuj etykiety
                temp_range = self.controller.temp.get().split(' /')
                maxv = float(min(float(temp_range[1]), max(self.data) + 5))
                minv = float(max(float(temp_range[0]), min(self.data) - 5))
                
                self.down_range_text.set_position((self.time[-1], maxv))
                self.down_range_text.set_text(f"max: {maxv:.1f}°C")
                self.up_range_text.set_position((self.time[-1], minv))
                self.up_range_text.set_text(f"min: {minv:.1f}°C")
                
                self.last_data_text.set_position((self.time[-1] - 1, self.data[-1]))
                self.last_data_text.set_text(f"{self.data[-1]:.1f}°C")
                
                self.last_current_text.set_position((self.time[-1] - 1, self.current[-1]))
                self.last_current_text.set_text(f"{self.current[-1]:.2f}A")
                
                # Aktualizuj etykiety interfejsu
                self.last_data_label.config(text=f"Temp. aktualna: {self.data[-1]:.1f}°C")
                self.measure_time.config(text=f"Czas: {current_time}s")
                self.changed_time.config(text=f'Czas od zmiany: {(time.time() - self.time_change):.1f}s')
                
            self.canvas.draw_idle()  # Używaj draw_idle() dla lepszej wydajności
            
        except Exception as e:
            self.console_data(f"Błąd aktualizacji wykresu: {e}")

    def validate_entry(self, value):
        """Waliduje wprowadzoną wartość"""
        if value == '' or value == '-':
            return True
        try:
            float(value.replace('.', ''))
            return True
        except ValueError:
            return False

class Options(Toplevel):
    def __init__(self, parent, controller):
        Toplevel.__init__(self, parent)
        self.controller = controller
        self.title("Opcje")
        
        Label(self, text="Prędkość (baud):").grid(row=0, column=0)
        Label(self, text="Port szeregowy:").grid(row=0, column=1)
        Label(self, text="Zakres temperatur:").grid(row=0, column=2)
        
        self.portMenu = OptionMenu(self, controller.port, *controller.port_choice)
        self.portMenu.grid(row=1, column=0)
        
        # Combobox wyboru portu szeregowego (lepszy od OptionMenu)
        self.serialPortCombo = ttk.Combobox(self, textvariable=controller.serial_port, 
                                           values=controller.available_ports, 
                                           state="readonly", width=15)
        self.serialPortCombo.grid(row=1, column=1)
        
        # Przycisk odświeżenia portów
        self.refresh_ports_btn = Button(self, text="Odśwież porty", command=self.refresh_ports)
        self.refresh_ports_btn.grid(row=2, column=1)

        self.tempMenu = OptionMenu(self, controller.temp, *controller.tempRange_choice)
        self.tempMenu.grid(row=1, column=2)
        
        self.v = IntVar()
        self.v.set(self.controller.graphFold)
        self.fold = Checkbutton(self, variable=self.v, onvalue=True, offvalue=False, command=self.change)
        self.fold.grid(row=4, column=1, sticky='w')
        Label(self, text='Ciągły wykres').grid(row=4, column=0)
        
        # Suwaki PID
        self.p = Scale(self, from_=0, to=20, orient=HORIZONTAL, resolution=0.1)
        self.p.set(self.controller.v[0])
        self.p.grid(row=5, column=0)
        Label(self, text='Współczynnik P').grid(row=5, column=1, sticky='w')
        
        self.i = Scale(self, from_=0, to=20, orient=HORIZONTAL, resolution=0.1)
        self.i.set(self.controller.v[1])
        self.i.grid(row=6, column=0)
        Label(self, text='Współczynnik I').grid(row=6, column=1, sticky='w')
        
        self.d = Scale(self, from_=0, to=20, orient=HORIZONTAL, resolution=0.1)
        self.d.set(self.controller.v[2])
        self.d.grid(row=7, column=0)
        Label(self, text='Współczynnik D').grid(row=7, column=1, sticky='w')
        
        # Przycisk zapisu
        self.save = Button(self, text='Zapisz', command=self.Save)
        self.save.grid(row=8, columnspan=3)
        
        # Status połączenia i informacje o systemie
        system_info = f"System: {platform.system()}"
        status_text = "Połączony" if self.controller.connected else "Rozłączony"
        status_color = "green" if self.controller.connected else "red"
        
        self.system_label = Label(self, text=system_info)
        self.system_label.grid(row=9, columnspan=3)
        
        self.status_label = Label(self, text=f"Status: {status_text}", fg=status_color)
        self.status_label.grid(row=10, columnspan=3)

        for widget in self.winfo_children():
            widget.grid_configure(padx=5, pady=2)
            
    def change(self):
        """Zmienia ustawienie ciągłego wykresu"""
        self.controller.graphFold = bool(self.v.get())
        config['fold'] = bool(self.v.get())
    
    def refresh_ports(self):
        """Odświeża listę dostępnych portów szeregowych"""
        try:
            # Pobierz nową listę portów
            new_ports = get_available_serial_ports()
            self.controller.available_ports = new_ports
            
            # Aktualizuj Combobox
            self.serialPortCombo['values'] = new_ports
            
            # Jeśli aktualny port nie jest na liście, ustaw pierwszy dostępny
            if self.controller.serial_port.get() not in new_ports and new_ports:
                self.controller.serial_port.set(new_ports[0])
            
            print(f"Odswiezońo porty: {new_ports}")
            
        except Exception as e:
            print(f"Bład odswiezania portów: {e}")
            messagebox.showerror("Bład", f"Nie udao sie odswiezyc portów: {e}")
        
    def Save(self):
        """Zapisuje ustawienia"""
        try:
            # Wyślij ustawienia PID do urządzenia
            pid_command = f'*SETCK{self.p.get():.1f} {self.i.get():.1f} {self.d.get():.1f};'
            self.controller.communicator.send_command(pid_command)
            
            # Aktualizuj konfigurację
            self.controller.v = [self.p.get(), self.i.get(), self.d.get()]
            config['pid'] = self.controller.v
            config['port'] = self.controller.port.get()
            config['serial_port'] = self.controller.serial_port.get()
            config['temp_range'] = self.controller.temp.get()
            config['fold'] = self.controller.graphFold
            
            # Zapisz do pliku
            with open('config.json', "w") as config_file:
                json.dump(config, config_file, indent=4)
            
            # Forśuj aktualizację wykresów po zmianie ustawień
            self.controller.frame.setup_graph_ranges()
            
        except Exception as e:
            print(f"Błąd zapisywania konfiguracji: {e}")
            messagebox.showerror("Błąd", f"Nie udało się zapisać ustawień: {e}")

class StreamToFunction:
    """Klasa do przekierowywania stdout - zachowana dla kompatybilności"""
    def __init__(self, func):
        self.func = func

    def write(self, message):
        if message.strip():
            self.func(message)
            
    def flush(self):
        pass

if __name__ == "__main__":
    def check_dependencies():
        """Sprawdza czy wszystkie wymagane biblioteki są zainstalowane"""
        missing = []
        
        try:
            import tkinter
        except ImportError:
            missing.append("tkinter")
        
        try:
            import matplotlib
        except ImportError:
            missing.append("matplotlib")
        
        try:
            import serial
        except ImportError:
            missing.append("pyserial")
            
        try:
            import numpy
        except ImportError:
            missing.append("numpy")
        
        if missing:
            error_msg = f"Brakuje wymaganych bibliotek: {', '.join(missing)}\n\n"
            if platform.system().lower() == 'linux':
                error_msg += "Zainstaluj używając:\n"
                error_msg += f"pip install {' '.join(missing)}\n\n"
                error_msg += "Lub na Ubuntu/Debian:\n"
                error_msg += "sudo apt-get install python3-tk python3-matplotlib python3-serial python3-numpy\n\n"
                error_msg += "Może też być potrzebne dodanie użytkownika do grupy dialout:\n"
                error_msg += "sudo usermod -a -G dialout $USER\n"
                error_msg += "Następnie wyloguj się i zaloguj ponownie."
            else:
                error_msg += f"Zainstaluj używając: pip install {' '.join(missing)}"
            
            print(error_msg)
            try:
                messagebox.showerror("Brakuje zależności", error_msg)
            except:
                pass
            return False
        return True
    
    if not check_dependencies():
        sys.exit(1)
    
    try:
        # Sprawdzenie pliku konfiguracyjnego
        if not os.path.exists("config.json"):
            print("Brak pliku config.json - tworzenie domyślnego")
            default_config = {
                "port": "9600",
                "serial_port": get_default_serial_port(),
                "temp_range": "-10 /+50", 
                "fold": True,
                "pid": [6, 7, 4],
                "current_off": False
            }
            with open("config.json", "w") as f:
                json.dump(default_config, f, indent=4)
        
        # Utwórz i uruchom aplikację
        window = App()
        window.title("Kontroler Temperatury - Fotonika")
        window.protocol("WM_DELETE_WINDOW", lambda: window.on_closing())
        
        # Utwórz menu
        menu = Menu(window, background='#F0F0F0')
        window.config(menu=menu)
        
        fileMenu = Menu(menu, tearoff=0)
        fileMenu.add_command(label="Opcje", command=lambda: Options(window.container, window))
        fileMenu.add_command(label="Importuj konfigurację", command=lambda: window.import_config())
        fileMenu.add_command(label="Eksportuj konfigurację", command=lambda: window.export_config())
        fileMenu.add_separator()
        fileMenu.add_command(label="Zapisz i zamknij", command=lambda: window.on_closing())
        menu.add_cascade(label="Plik", menu=fileMenu)
        
        print("Aplikacja uruchomiona pomyślnie")
        window.mainloop()
        
    except Exception as e:
        print(f"Krytyczny błąd aplikacji: {e}")
        messagebox.showerror("Błąd krytyczny", f"Nie udało się uruchomić aplikacji:\n{e}")
        sys.exit(1)
    finally:
        print("Aplikacja zakończona")
