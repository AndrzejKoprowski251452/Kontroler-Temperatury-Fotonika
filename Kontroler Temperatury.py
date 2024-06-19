from tkinter import *
from tkinter import messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import time
import json
import serial
import serial.tools
import serial.tools.list_ports

data = [0]
sent_data_value = 50
time_start = time.time()
timev = float(str(time.time()-time_start)[:5])
connection = serial.Serial('COM3',9600)
def lerp(x1: float, y1: float, x: float):
    return float(str(x1+((y1-x1)*x))[:5])
def generate_data():
    return lerp(data[-1],sent_data_value,0.1)

def update_graph():
    global maxv,minv,timev
    data.append(generate_data())
    timev = float(str(time.time()-time_start)[:5])
    r = 0
    if len(data) > 100:
        r = len(data)-100
    line.set_data(range(len(data)), data)
    plot.set_xlim(r, len(data))
    plot.set_ylim(min(data)-20, max(data)+20)
    maxv = float(temp.get().split(' /')[1])
    minv = float(temp.get().split(' /')[0])
    down_range_text.set_position((len(data)/10,maxv))
    down_range_text.set_text(f"max: {maxv}°C")
    up_range_text.set_position((len(data)/10,minv))
    up_range_text.set_text(f"min: {minv}°C")
    last_data_text.set_position((len(data),data[-1]))
    last_data_text.set_text(f"{data[-1]}°C")
    last_data_label.config(text=f"Current Temp. : {data[-1]}°C")
    measure_time.config(text=f"Time : {timev}s")
    canvas.draw()
        
def update_options():
    global current
    a = ""
    MAX_CURRENT = Canvas(options,width=130,height=40)
    MAX_CURRENT.create_rectangle(0,0,130,40,fill='black')
    for i in range(6):
        MAX_CURRENT.create_rectangle(10+20*i,10,20*(i+1),30,fill='grey')
        MAX_CURRENT.create_text(15+20*i,35,text=f"{i+1}",fill="white", font=('Helvetica 8 bold'))
        MAX_CURRENT.create_rectangle(10+20*i,20-(10*pid[i]["on"]),20*(i+1),30-(10*pid[i]["on"]),fill='white')  
        MAX_CURRENT.bind('<Button>', clicked)
        a += str(pid[i]["on"])
    MAX_CURRENT.grid(row=0, column=5, padx=5, pady=5, sticky="nsew")
    current.set(str(int(a,2)*0.1)[:3])
    currentValue.config(text=f'Current: {current.get()}A')
        
def send_serial_data():
    global sent_data_value,port
    m = temp.get().split(' /')
    v = 0
    try:
        v = float(entry.get())
    except ValueError:
        v = max(min(sent_data_value,float(m[1])),float(m[0]))
    sent_data_value = max(min(v,float(m[1])),float(m[0]))
    sent_data_line.set_ydata([sent_data_value])
    up_range.set_ydata([float(m[1])])
    down_range.set_ydata([float(m[0])])
    set_data_label.config(text=f"Set Temp. : {sent_data_value}°C")
    update_graph()
    #current.get()
    #temp.get()
    entry.delete(0,len(str(sent_data_value)))
    
def change_port():
    global connection
    connection.port(port.get())
    
def validate_entry(value):
    if value == '' or value == '-':
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False

def on_closing():
    answer = messagebox.askquestion("Warning", "Do you want to save the data?", icon="warning")
    if answer == "yes":
        data_dict = {
            "data": data,
            "pid_port": port.get(),
            "pid_current": current.get(),
            "pid_temp": temp.get(),
            "sent_data_value": sent_data_value,
            "time":float(str(time.time()-time_start)[:4])
        }
        script_dir = os.path.dirname(os.path.abspath(__file__))
        measure_dir = os.path.join(script_dir, "Pomiary")
        if not os.path.exists(measure_dir):
            os.makedirs(measure_dir)
        existing_folders = [int(folder[-1]) for folder in os.listdir(measure_dir) if os.path.isdir(os.path.join(measure_dir, folder))]
        latest_number = max(existing_folders) + 1 if existing_folders else 1
        new_folder = os.path.join(measure_dir, 'Pomiar '+str(latest_number))
        os.makedirs(new_folder)
        save_path = os.path.join(new_folder, "plot.png")
        fig.savefig(save_path)
        json_path = os.path.join(new_folder, "data.json")
        with open(json_path, "w") as json_file:
            json.dump(data_dict, json_file)
    window.destroy()
    
def clicked(event):
    for i in pid:
        if i["x1"] <= event.x <= i["x2"] and i["y1"] <= event.y <= i["y2"]:
            i["on"] = int(not bool(i['on']))
    update_options()

window = Tk()
window.title("Kontroler Temperatury")
w = 600
h = 750
window.minsize(w,h)
window.maxsize(w,h)

frame = Frame(window)
frame.pack()

options = LabelFrame(frame,text="Options")
options.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
data_panel = LabelFrame(frame,text="Data Panel")
data_panel.grid(row=0, padx=10, pady=10,sticky="news")
graphs = LabelFrame(frame,text="Graph")
graphs.grid(row=2, padx=10, pady=10,sticky="news")
 
entry = Entry(data_panel,validate="key",validatecommand=(window.register(validate_entry), '%P'))
entry.grid(row=0,column=0)

send_button = Button(data_panel, text="Send Data", command=send_serial_data)
send_button.grid(row=1,column=0)

last_data_label = Label(data_panel, text="")
last_data_label.grid(row=0,column=1)

set_data_label = Label(data_panel, text=f"Set Temp. : {sent_data_value}°C")
set_data_label.grid(row=1,column=1)

measure_time = Label(data_panel, text=f"Time : {str(time.time()-time_start)[:5]}s")
measure_time.grid(row=0,column=2,sticky="ne")

for widget in data_panel.winfo_children():
    widget.grid_configure(padx=5, pady=5)
    
Label(options,text="Port:").grid(row=0,column=0)
Label(options,text="Temp Range:").grid(row=0,column=1)

pid = []
for i in range(6):
    b = {'x1':10+20*i,'y1':10,'x2':20*(i+1),'y2':30,'on':0}
    pid.append(b)
    
port_choice = ['1200','2400','4800','9600','19200','38400','57600','115200']
port = StringVar(options)
port.set('1200')
port.trace_add("write",lambda v,i,m:change_port())
portMenu = OptionMenu(options, port, *port_choice)
portMenu.grid(row=1,column=0)

tempRange_choice = ['-10 /+50','-10 /+100','-100 /+10','-50 /+50','+15 /+30','+30 /+45','+45 /+60','-100 /+250']
temp = StringVar(options)
temp.set('-10 /+50')
temp.trace_add("write",lambda v,i,m:send_serial_data())
tempMenu = OptionMenu(options, temp, *tempRange_choice)
tempMenu.grid(row=1,column=1)

current_choice = ['0.0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '1.0', '1.1', '1.2', '1.3', '1.4', '1.5', '1.6', '1.7', '1.8', '1.9', '2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8', '2.9', '3.0', '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9', '4.0', '4.1', '4.2', '4.3', '4.4', '4.5', '4.6', '4.7', '4.8', '4.9', '5.0', '5.1', '5.2', '5.3', '5.4', '5.5', '5.6', '5.7', '5.8', '5.9', '6.0', '6.1', '6.2', '6.3']
current_choice.sort()
current = StringVar(options)
current.set('0.1')
current.trace_add("write",lambda v,i,m:currentValue.config(text=f'Current: {current.get()}A'))
currentMenu = OptionMenu(options, current, *current_choice)
currentMenu.grid(row=0,column=4)
currentValue = Label(options,text=f'Current: 0.0A')
currentValue.grid(row=0,column=3)
update_options()

for widget in options.winfo_children():
    widget.grid_configure(padx=5, pady=2)

fig = Figure(figsize=(5, 5), dpi = 100)
fig.patch.set_facecolor('#F0F0F0')
plot = fig.add_subplot(111)
plot.grid()

line, = plot.plot(data, 'g')

maxv = float(temp.get().split(' /')[1])
minv = float(temp.get().split(' /')[0])
last_data_text = plot.text(0, 0, f"0", ha='left', va='bottom', fontsize=8, color='red')
up_range_text = plot.text(len(data), maxv, f"min: {maxv}°C", ha='left', va='bottom', fontsize=8, color='grey')
down_range_text = plot.text(len(data), minv, f"max: {minv}°C", ha='left', va='bottom', fontsize=8, color='grey')
up_range = plot.axhline(y=maxv, color='grey', linestyle='--')
down_range = plot.axhline(y=minv, color='grey', linestyle='--')
sent_data_line = plot.axhline(y=sent_data_value, color='r', linestyle='--')

canvas = FigureCanvasTkAgg(fig, master=graphs)
canvas.draw()
canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

def update_periodically():
    update_graph()
    #print(serial.tools.list_ports.comports()[0])
    window.after(100, update_periodically)

update_periodically()

window.protocol("WM_DELETE_WINDOW", on_closing)
mainloop()