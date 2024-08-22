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
from contextlib import redirect_stdout
import sys
import io

def cut_num(v, n=2):
    if isinstance(v, float):
        v = np.floor(v * 10**n) / 10**n
        return float(v)

class App(Tk):
    def __init__(self, *args, **kwargs):
        Tk.__init__(self, *args, **kwargs)
        
        self.container = Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.port_choice = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
        self.port = StringVar(self)
        self.port.set('9600')
        self.tempRange_choice = ['-10 /+50', '-10 /+100', '-100 /+10', '-50 /+50', '+15 /+30', '+30 /+45', '+45 /+60', '-100 /+250']
        self.temp = StringVar(self)
        self.temp.set('-10 /+100')
        self.graphFold = True
        self.connected = True
        
        try:
            self.connection = serial.Serial("COM4",int(self.port.get()),timeout=0)
            self.connected = True
        except:
            self.connected = False
            print('No divice connected')
        
        self.frame = StartPage(self.container, self)
        self.frame.grid(row=0, column=0, sticky="nsew")
        self.frame.tkraise()

        self.update_graph()

    def update_graph(self):
        self.frame.update_graph()
        self.after(100, self.update_graph)
        
    def on_closing(self):
        answer = messagebox.askquestion("Warning", "Do you want to save the data?", icon="warning")
        if answer == "yes":
            data_dict = {
                "data": self.frame.data,
                "pid_port": self.port.get(),
                "pid_temp": self.temp.get(),
                "sent_data_value": self.frame.sent_data_value,
                "time":cut_num(time.time()-self.frame.time_start)
            }
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
                json.dump(data_dict, json_file)
            self.connection.write(str.encode('*SETTPRS20.0;'))
            window.destroy()

class StartPage(LabelFrame):
    def __init__(self, parent, controller):
        LabelFrame.__init__(self, parent)
        self.controller = controller
        
        self.data = [0]
        self.current = [0]
        self.time = [0]
        self.sent_data_value = 20
        self.buffor = ['*GETTACT;','*GETIOUT;']
        self.time_start = time.time()
        self.time_change = time.time()
        self.r = 0
        
        self.entry = Entry(self, validate="key", validatecommand=(controller.register(self.validate_entry), '%P'))
        self.entry.grid(row=0, column=1)

        self.send_button = Button(self, text="Send Data", command=self.send_serial_data)
        self.send_button.grid(row=0, column=2,sticky='w')

        self.last_data_label = Label(self)
        self.last_data_label.grid(row=1, column=2,sticky='w')

        self.set_data_label = Label(self,text=f"Set Temp. : {self.sent_data_value}°C")
        self.set_data_label.grid(row=1, column=1)

        self.measure_time = Label(self)
        self.measure_time.grid(row=0, column=3)

        self.changed_time = Label(self)
        self.changed_time.grid(row=1, column=3)
        
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
        self.last_data_text = self.ax1.text(0, 0, "0", ha='left', va='bottom', fontsize=8, color='red')
        self.last_current_text = self.ax2.text(0, 0, "0", ha='left', va='bottom', fontsize=8, color='orange')
        self.up_range_text = self.ax1.text(self.time[-1]*0.8, maxv, f"min: {maxv}°C", ha='left', va='bottom', fontsize=8, color='grey')
        self.down_range_text = self.ax1.text(self.time[-1]*0.8, minv, f"max: {minv}°C", ha='left', va='bottom', fontsize=8, color='grey')
        self.up_range = self.ax1.axhline(y=maxv, color='grey', linestyle='--')
        self.down_range = self.ax1.axhline(y=minv, color='grey', linestyle='--')
        self.sent_data_line = self.ax1.axhline(y=self.sent_data_value, color='r', linestyle='--')
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew",rowspan=20)
        
    def console_data(self,f):
        self.console.insert(INSERT, f)

    def update_graph(self):
        sys.stdout = StreamToFunction(self.console_data)
        timev = cut_num(time.time() - self.time_start)
        if self.controller.connected:
            for b in self.buffor:
                if not self.controller.connection.in_waiting:
                    self.controller.connection.write(str.encode(b))
                    self.controller.connection.flush()
                v = self.controller.connection.readline().decode('Latin-1')
                print(v)
                if '*TACT ' in v:
                    self.data.append(float(v[5:12]))
                    self.time.append(timev)
                if '*IOUT ' in v:
                    self.current.append(float(v[9:15].replace('A','')))
        if self.time[-1] > 20 and self.controller.graphFold:
            self.r = self.time[-1]-20
        self.line.set_data(self.time, self.data)
        if len(self.time) == len(self.current):
            self.current_data_line.set_data(self.time,self.current)
        self.ax1.set_xlim(self.r, self.time[-1])
        self.ax1.set_ylim(min(self.data) - 20, max(self.data) + 20)
        self.ax2.set_xlim(self.r, self.time[-1])
        self.ax2.set_ylim(min(self.current) - 20, max(self.current) + 20)
        maxv = min(float(self.controller.temp.get().split(' /')[1]), max(self.data) + 20)
        minv = max(float(self.controller.temp.get().split(' /')[0]), min(self.data) - 20)
        self.down_range_text.set_position((self.time[-1], maxv))
        self.down_range_text.set_text(f"max: {maxv}°C")
        self.up_range_text.set_position((self.time[-1], minv))
        self.up_range_text.set_text(f"min: {minv}°C")
        self.last_data_text.set_position((self.time[-1] - 1, self.data[-1]))
        self.last_data_text.set_text(f"{self.data[-1]}°C")
        self.last_current_text.set_position((self.time[-1] - 1, self.current[-1]))
        self.last_current_text.set_text(f"{self.current[-1]}A")
        self.last_data_label.config(text=f"Current Temp. : {self.data[-1]}°C")
        self.measure_time.config(text=f"Time : {timev}s")
        self.changed_time.config(text=f'Time of measure : {cut_num(time.time() - self.time_change)}s')
        self.canvas.draw()

    def send_serial_data(self):
        self.time_change = time.time()
        m = self.controller.temp.get().split(' /')
        v = 0
        try:
            v = float(self.entry.get())
        except ValueError:
            v = max(min(self.sent_data_value, float(m[1])), float(m[0]))
        self.sent_data_value = max(min(v, float(m[1])), float(m[0]))
        if self.controller.connected:
            self.controller.connection.write(str.encode(f'*SETTPRS{self.sent_data_value};'))
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
        self.fold = Checkbutton(self,variable=self.v,onvalue=True,offvalue=False,command=self.change())
        
        self.p = Scale(self,orient=HORIZONTAL)
        self.i = Scale(self,orient=HORIZONTAL)
        self.d = Scale(self,orient=HORIZONTAL)
        
        self.save = Button(self,text='Save',command=self.Save())

        for widget in self.winfo_children():
            widget.grid_configure(padx=5, pady=2)
            
    def change(self):
        self.controller.graphFold = self.v.get()
    def Save(self):
        self.controller.connection.write(str.encode(f'*;'))
class StreamToFunction:
    def __init__(self, func):
        self.func = func

    def write(self, message):
        if message.strip():  # Ignore empty messages (like newlines)
            self.func(message)
    def flush(self):
        pass

if __name__ == "__main__":
    window = App()
    window.title("Temperature Controller")

    menu = Menu(window,background='#F0F0F0')
    window.config(menu=menu)
    fileMenu = Menu(menu,tearoff=0)
    fileMenu.add_command(label="Graph", command=lambda: window.show_frame(StartPage))
    fileMenu.add_command(label="Options", command=lambda:Options(window.container,window))
    fileMenu.add_command(label="Save & Exit", command=lambda: window.on_closing())
    menu.add_cascade(label="File", menu=fileMenu)
    window.mainloop()
