from tkinter import *
from tkinter import messagebox, filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import os
import time
from datetime import datetime
import json
import serial.tools.list_ports
import sys

config = {}
with open("config.json", 'r') as file:
    config = json.load(file)

class App(Tk):
    def __init__(self, *args, **kwargs):
        Tk.__init__(self, *args, **kwargs)
        
        self.container = Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.port_choice = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
        self.port = StringVar(self)
        self.port.set(config['port'])
        self.tempRange_choice = ['-10 /+50', '-10 /+100', '-100 /+10', '-50 /+50', '+15 /+30', '+30 /+45', '+45 /+60', '-100 /+250']
        self.temp = StringVar(self)
        self.temp.set(config['temp_range'])
        self.v = config['pid']
        self.graphFold = config['fold']
        self.connected = True
        
        self.frame = StartPage(self.container, self)
        self.frame.grid(row=0, column=0, sticky="nsew")
        self.frame.tkraise()
        
        sys.stdout = StreamToFunction(self.frame.console_data)

        try:
            self.connection = serial.Serial("COM4",int(self.port.get()),timeout=0)
            self.connected = True
        except:
            self.connected = False
            print('No divice connected')

        self.update_graph()

    def update_graph(self):
        self.frame.update_graph()
        self.after(10, self.update_graph)
        
    def on_closing(self):
        answer = messagebox.askquestion("Warning", "Do you want to save the data?", icon="warning")
        if answer == "yes":
            dir = filedialog.askdirectory() or None
            if dir == None:
                return 
            name = 'pomiar-{}'.format(datetime.today().strftime('%Y-%m-%d'))
            existing_folders = [f for f in os.listdir(dir) if os.path.isdir(os.path.join(dir, f))]
            if not name in existing_folders:
                dir = os.path.join(dir, name)
                os.makedirs(dir)
            else:
                matching_folders = [f for f in existing_folders if f.startswith(name) and f[-2].isdigit()]
                dir = os.path.join(dir,f'{name} ({len(matching_folders)})')
                os.makedirs(dir)
            save_path = os.path.join(dir, "plot.png")
            self.frame.fig.savefig(save_path)
            json_path = os.path.join(dir, "data.json")
            with open(json_path, "w") as json_file:
                json.dump({"temp":self.frame.data,"cur":self.frame.current,"time":self.frame.time}, json_file,indent=4)
        window.destroy()
        
    def import_config(self):
        global config
        dir = filedialog.askopenfilename(
        title="Select a JSON file",
        filetypes=[("JSON files", "*.json")],
        )
        with open(dir,'r') as new_config:
            config = json.load(new_config)
        self.port.set(config['port'])
        self.temp.set(config['temp_range'])
        self.v = config['pid']
        self.graphFold = config['fold']
        Options(window.container,window).Save()

    def export_config(self):
        global config
        dir = filedialog.askdirectory()
        config_path = os.path.join(dir, "config.json")
        with open(config_path, "w") as new_config:
            json.dump(config, new_config)

class StartPage(LabelFrame):
    def __init__(self, parent, controller):
        LabelFrame.__init__(self, parent)
        self.controller = controller
        
        self.data = [0]
        self.current = [0]
        self.time = [0]
        self.sent_data_value = 20.0
        self.buffor = ['*GETTACT;','*GETIOUT;','A']
        self.time_start = time.time()
        self.time_change = time.time()
        self.r = 1
        
        self.entry = Entry(self, validate="key", validatecommand=(controller.register(self.validate_entry), '%P'))
        self.entry.bind("<Return>",lambda e:self.send_serial_data())
        self.entry.grid(row=0, column=1)

        self.send_button = Button(self, text="Send Data", command=self.send_serial_data)
        self.send_button.grid(row=1, column=1)

        self.last_data_label = Label(self)
        self.last_data_label.grid(row=1, column=2,sticky='w')

        self.set_data_label = Label(self,text=f"Set Temp. : {self.sent_data_value}°C")
        self.set_data_label.grid(row=0, column=2,sticky='w')
        
        self.current_off_v = IntVar()
        self.current_off_v.set(config['current_off'])
        self.current_off = Checkbutton(self,variable=self.current_off_v,onvalue=True,offvalue=False,command=self.change_current)
        self.current_off.grid(row=0,column=2,sticky='e')
        
        self.current_off_text = Label(self,text=f"Current flowing: {bool(self.current_off_v.get())}")
        self.current_off_text.grid(row=0,column=3,sticky='w')

        self.measure_time = Label(self)
        self.measure_time.grid(row=0, column=4)

        self.changed_time = Label(self)
        self.changed_time.grid(row=1, column=4)
        
        self.console = Text(self)
        self.console.grid(row=2,column=1,columnspan=3)
        
        for widget in self.winfo_children():
            widget.grid_configure(padx=5, pady=5,rowspan=1)

        self.fig = Figure(figsize=(5, 5), dpi=100)
        self.fig.patch.set_facecolor('#F0F0F0')
        self.ax1 = self.fig.add_subplot(1,1,1)
        self.ax2 = self.ax1.twinx()
        self.ax1.grid()
        self.line, = self.ax1.plot(self.time,self.data, 'g')
        self.current_data_line, = self.ax2.plot(self.time,self.current, 'orange')
        maxv = float(controller.temp.get().split(' /')[1])
        minv = float(controller.temp.get().split(' /')[0])
        self.last_data_text = self.ax1.text(0, 0, "0", ha='right', va='bottom', fontsize=8, color='red')
        self.last_current_text = self.ax2.text(0, 0, "0", ha='right', va='bottom', fontsize=8, color='orange')
        self.up_range_text = self.ax1.text(self.time[-1]*0.8, maxv, f"min: {maxv:.3f}°C", ha='right', va='top', fontsize=8, color='grey')
        self.down_range_text = self.ax1.text(self.time[-1]*0.8, minv, f"max: {minv:.3f}°C", ha='right', va='bottom', fontsize=8, color='grey')
        self.up_range = self.ax1.axhline(y=maxv, color='grey', linestyle='--')
        self.down_range = self.ax1.axhline(y=minv, color='grey', linestyle='--')
        self.sent_data_line = self.ax1.axhline(y=self.sent_data_value, color='r', linestyle='--')
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew",rowspan=20)
    def change_current(self):
        config['current_off'] = bool(self.current_off_v.get())
        with open('config.json', "w") as config_file:
            json.dump(config, config_file)
        self.current_off_text.config(text=f"Current flowing: {bool(self.current_off_v.get())}")
        
    def console_data(self,f):
        self.console.insert(INSERT, f'{(time.time() - self.time_start):.2f}: {f}\n')
        self.console.see("end")

    def update_graph(self):
        timev = f"{(time.time() - self.time_start):.2f}"
        if self.controller.connected:
            for b in self.buffor:
                if not self.controller.connection.in_waiting:
                    self.controller.connection.write(str.encode(b))
                v = self.controller.connection.readline().decode('Latin-1')
                if config['current_off']:
                    self.controller.connection.write(str.encode('a'))
                elif 'a' in v:
                    self.controller.connection.write(str.encode('A'))
                if '*TACT ' in v:
                    self.data.append(float(v[5:12]))
                    print(f'Temperature: {v[5:12]}C')
                    if self.data[-1] >= float(self.controller.temp.get().split(' /')[1]):
                        config['current_off'] = True
                    else:
                        config['current_off'] = False
                if '*IOUT ' in v:
                    c = float(v[9:15].replace('A',''))
                    self.current.append(c)
                    print(f'Current: {c}A')
                if '*CK ' in v and "*GETCK;" in self.buffor:
                    self.controller.v = v[3:].split(' ')
                self.controller.connection.flush()
                self.buffor = self.buffor[:2]
        if len(self.data) > len(self.time):
            self.time.append(timev)
        if self.time[-1] > 20 and self.controller.graphFold:
            self.r = self.time[-1]-20
        elif not self.controller.graphFold:
            self.r = 0.1
        self.line.set_data(self.time, self.data)
        if len(self.time) == len(self.current):
            self.current_data_line.set_data(self.time,self.current)
            self.ax1.set_xlim(self.r, self.time[-1])
            self.ax1.set_ylim(min(self.data) - 20, max(self.data) + 20)
            self.ax2.set_xlim(self.r, self.time[-1])
            self.ax2.set_ylim(min(self.current) - 20, max(self.current) + 20)
        maxv = float(min(float(self.controller.temp.get().split(' /')[1]), max(self.data) + 20))
        minv = float(max(float(self.controller.temp.get().split(' /')[0]), min(self.data) - 20))
        self.down_range_text.set_position((self.time[-1], maxv))
        self.down_range_text.set_text(f"max: {maxv:.1f}°C")
        self.up_range_text.set_position((self.time[-1], minv))
        self.up_range_text.set_text(f"min: {minv:.1f}°C")
        self.last_data_text.set_position((self.time[-1] - 1, self.data[-1]))
        self.last_data_text.set_text(f"{self.data[-1]}°C")
        self.last_current_text.set_position((self.time[-1] - 1, self.current[-1]))
        self.last_current_text.set_text(f"{self.current[-1]}A")
        self.last_data_label.config(text=f"Current Temp. : {self.data[-1]}°C")
        self.measure_time.config(text=f"Time : {timev}s")
        self.changed_time.config(text=f'Time of measure : {(time.time() - self.time_change):.2f}s')
        self.canvas.draw()

    def send_serial_data(self):
        self.time_change = time.time()
        m = self.controller.temp.get().split(' /')
        v = 0
        try:
            v = max(min(float(self.entry.get()), float(m[1])), float(m[0]))
        except ValueError:
            v = max(min(self.sent_data_value, float(m[1])), float(m[0]))
        self.sent_data_value = max(min(v, float(m[1])), float(m[0]))
        if self.controller.connected:
            self.controller.connection.write(str.encode(f'*SETTPRS{self.sent_data_value};'))
            print(f'Set Temperatur: {self.sent_data_value}°C')
        else:
            print("No divice connected")
        self.sent_data_line.set_ydata([self.sent_data_value])
        self.up_range.set_ydata([float(m[1])])
        self.down_range.set_ydata([float(m[0])])
        self.set_data_label.config(text=f"Set Temp. : {self.sent_data_value}°C")
        self.update_graph()
        self.entry.delete(0, len(str(self.sent_data_value)))

    def validate_entry(self, value):
        if value == '' or value == '-':
            return True
        try:
            float(value.replace('.',''))
            return True
        except ValueError:
            return False

class Options(Toplevel):
    def __init__(self, parent, controller):
        Toplevel.__init__(self, parent)
        self.controller = controller
        
        Label(self, text="Port:").grid(row=0, column=0)
        Label(self, text="Temp Range:").grid(row=0, column=1)
        
        self.portMenu = OptionMenu(self, controller.port, *controller.port_choice)
        self.portMenu.grid(row=1, column=0)

        self.tempMenu = OptionMenu(self, controller.temp, *controller.tempRange_choice)
        self.tempMenu.grid(row=1, column=1)
        
        self.v = IntVar()
        self.v.set(self.controller.graphFold)
        self.fold = Checkbutton(self,variable=self.v,onvalue=True,offvalue=False,command=self.change)
        self.fold.grid(row=3,column=1,sticky='w')
        Label(self,text='Continuous Graph').grid(row=3,column=0)
        
        self.p = Scale(self,from_=0,to=20,orient=HORIZONTAL)
        self.p.set(self.controller.v[0])
        self.p.grid(row=4,column=0)
        Label(self,text='P-coefficient').grid(row=4,column=1,sticky='w')
        self.i = Scale(self,from_=0,to=20,orient=HORIZONTAL)
        self.i.set(self.controller.v[1])
        self.i.grid(row=5,column=0)
        Label(self,text='I-coefficient').grid(row=5,column=1,sticky='w')
        self.d = Scale(self,from_=0,to=20,orient=HORIZONTAL)
        self.d.set(self.controller.v[2])
        self.d.grid(row=6,column=0)
        Label(self,text='D-coefficient').grid(row=6,column=1,sticky='w')
        
        self.save = Button(self,text='Save',command=self.Save)
        self.save.grid(row=7,columnspan=2)

        for widget in self.winfo_children():
            widget.grid_configure(padx=5, pady=2)
            
    def change(self):
        self.controller.graphFold = bool(self.v.get())
        config['fold'] = bool(self.v.get())
    def Save(self):
        self.controller.frame.buffor.append(f'*SETCK{self.p.get()} {self.i.get()} {self.d.get()};')
        #self.controller.connection.write(str.encode(f'*SETCK{self.p.get()} {self.i.get()} {self.d.get()};'))
        self.controller.v = [self.p.get(), self.i.get(), self.d.get()]
        config['pid'] = [self.p.get(), self.i.get(), self.d.get()]
        config['port'] = self.controller.port.get()
        config['temp_range'] = self.controller.temp.get()
        config['fold'] = self.controller.graphFold
        self.controller.graphFold = config['fold']
        with open('config.json', "w") as config_file:
            json.dump(config, config_file)
        self.controller.frame.update_graph()
class StreamToFunction:
    def __init__(self, func):
        self.func = func

    def write(self, message):
        if message.strip():
            self.func(message)
    def flush(self):
        pass

if __name__ == "__main__":
    window = App()
    window.title("Temperature Controller")
    window.protocol("WM_DELETE_WINDOW",window.on_closing)

    menu = Menu(window,background='#F0F0F0')
    window.config(menu=menu)
    fileMenu = Menu(menu,tearoff=0)
    fileMenu.add_command(label="Options", command=lambda:Options(window.container,window))
    fileMenu.add_command(label="Import config", command=lambda: window.import_config())
    fileMenu.add_command(label="Export config", command=lambda: window.export_config())
    fileMenu.add_command(label="Save & Exit", command=lambda: window.on_closing())
    menu.add_cascade(label="File", menu=fileMenu)
    window.mainloop()
