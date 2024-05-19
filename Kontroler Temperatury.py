from tkinter import *
from tkinter import messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import time
import json
import numpy as np

data = [1]
sent_data_value = 50
time_start = time.time()
settings = {"sent_data_value":50,"pid1":[1,1,1],"pid2":[1,1,0,0,1,0]}
stabilize = False
def lerp(x1: float, y1: float, x: float):
    return float(str(x1+((y1-x1)*x))[:5])
def generate_data():
    return lerp(data[-1],sent_data_value,0.1)

def update_graph():
    data.append(generate_data())
    line.set_data(range(len(data)), data)
    plot.set_xlim(0, len(data))
    plot.set_ylim(0, max(data)+20)
    last_data_text.set_position((len(data)-1,data[-1]))
    last_data_text.set_text(f"{data[-1]}")
    last_data_label.config(text=f"Current Temp. : {data[-1]}")
    stabilization_time.config(text=f"Time : {str(time.time()-time_start)[:5]}")
    canvas.draw()
    global stabilize
    if abs(data[-1]-sent_data_value) < 0.1 and not stabilize:
        global measure
        stabilize = True
        messagebox.showinfo(title="Complite",message="Temperatura ustabiliziowana")
        
def update_options(n):
    global pid_temp,pid_current
    a = ""
    if n == 0:
        BAUDRATE = Canvas(options,width=70,height=40)
        BAUDRATE.create_rectangle(0,0,70,40,fill='black')
        for i in range(1,4):
            BAUDRATE.create_rectangle(10+20*(i-1),10,20*i,30,fill='grey')
            BAUDRATE.create_text(15+20*(i-1),35,text=f"{i}",fill="white", font=('Helvetica 8 bold'))
            BAUDRATE.create_rectangle(10+20*(i-1),20-(10*pid1[i-1]["on"]),20*i,30-(10*pid1[i-1]["on"]),fill='white')  
            BAUDRATE.bind('<Button>', clicked1)
            a += str(pid1[(i-1)]["on"])
        BAUDRATE.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        pid_temp.config(text=f"Port: {str((2**int(a,2))*1200)}")
    else:
        MAX_CURRENT = Canvas(options,width=130,height=40)
        MAX_CURRENT.create_rectangle(0,0,130,40,fill='black')
        for i in range(1,7):
            MAX_CURRENT.create_rectangle(10+20*(i-1),10,20*i,30,fill='grey')
            MAX_CURRENT.create_text(15+20*(i-1),35,text=f"{i}",fill="white", font=('Helvetica 8 bold'))
            MAX_CURRENT.create_rectangle(10+20*(i-1),20-(10*pid2[(i-1)]["on"]),20*i,30-(10*pid2[(i-1)]["on"]),fill='white')  
            MAX_CURRENT.bind('<Button>', clicked2)
            a += str(pid2[(i-1)]["on"])
        MAX_CURRENT.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        pid_current.config(text=f"Current: {str(int(a,2)*0.1)[:4]}A")

def send_serial_data():
    global sent_data_value,stabilize
    sent_data_value = float(entry.get())  
    sent_data_line.set_ydata([sent_data_value])
    set_data_label.config(text=f"Set Temp. : {sent_data_value}")
    stabilize = False
    entry.delete(0,len(str(sent_data_value)))
    
def validate_entry(new_value):
    if new_value == "" or new_value.isdigit():
        return True
    return False

def on_closing():
    answer = messagebox.askquestion("Warning", "Do you want to save the data?", icon="warning")
    if answer == "yes":
        data_dict = {
            "data": data,
            "pid1": pid1,
            "pid2": pid2,
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
    
def clicked1(event):
    for i in pid1:
        if i["x1"] <= event.x <= i["x2"]:
            if i["y1"] <= event.y <= i["y2"]:
                if i["on"] == 1:
                    i["on"] = 0
                else:
                    i["on"] = 1
    update_options(0)
def clicked2(event):
    for i in pid2:
        if i["x1"] <= event.x <= i["x2"]:
            if i["y1"] <= event.y <= i["y2"]:
                if i["on"] == 1:
                    i["on"] = 0
                else:
                    i["on"] = 1
    update_options(1)

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

set_data_label = Label(data_panel, text=f"Set Temp. : {sent_data_value}")
set_data_label.grid(row=1,column=1)

stabilization_time = Label(data_panel, text=f"Time : {str(time.time()-time_start)[:5]}")
stabilization_time.grid(row=0,column=2,sticky="ne")

for widget in data_panel.winfo_children():
    widget.grid_configure(padx=5, pady=5)
    
pid1 = []
pid2 = []
for i in range(3):
    b = {'x1':10+20*i,'y1':10,'x2':20*(i+1),'y2':30,'on':settings["pid1"][i]}
    pid1.append(b)

for i in range(6):
    b = {'x1':10+20*i,'y1':10,'x2':20*(i+1),'y2':30,'on':settings["pid2"][i]}
    pid2.append(b)
    
pid_current = Label(options,text="Current:")
pid_current.grid(row=0,column=4)
pid_temp = Label(options,text="Port: ")
pid_temp.grid(row=0,column=1)

update_options(0)
update_options(1)

fig = Figure(figsize=(5, 5), dpi = 100)
fig.patch.set_facecolor('#F0F0F0')
plot = fig.add_subplot(111)
plot.grid()

line, = plot.plot(data, 'g')

last_data_text = plot.text(0, 0, f"0", ha='left', va='bottom', fontsize=8, color='red')
sent_data_line = plot.axhline(y=sent_data_value, color='r', linestyle='--')

canvas = FigureCanvasTkAgg(fig, master=graphs)
canvas.draw()
canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

def update_periodically():
    update_graph()
    window.after(100, update_periodically)

update_periodically()

window.protocol("WM_DELETE_WINDOW", on_closing)
mainloop()