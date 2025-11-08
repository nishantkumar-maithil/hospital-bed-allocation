
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
import bisect, heapq

from database import init_db, add_patient_to_db, discharge_patient_from_db

wards = {}
patients = []
patient_names = []

def get_ward_priority():
    return [(-1 * (w["capacity"] - w["occupied"]), ward) for ward, w in wards.items()]

def update_visualization():
    for row in tree.get_children():
        tree.delete(row)
    for ward, data in wards.items():
        capacity = data["capacity"]
        occupied = data["occupied"]
        available = capacity - occupied
        tree.insert("", "end", values=(ward, capacity, occupied, available))
    update_patient_list()

def update_patient_list():
    for row in patient_tree.get_children():
        patient_tree.delete(row)
    for p in patients:
        patient_tree.insert("", "end", values=(p["name"], p["ward"]))

def allocate_bed():
    name = entry_name.get().strip()
    ward_choice = combo_ward.get().strip()

    if not name:
        messagebox.showwarning("Input Error", "Please enter patient name.")
        return

    if not ward_choice:
        heap = get_ward_priority()
        heapq.heapify(heap)
        _, ward_choice = heapq.heappop(heap)
        messagebox.showinfo("Auto Allocation", f"Automatically assigned to {ward_choice}")

    ward_data = wards[ward_choice]
    if ward_data["occupied"] >= ward_data["capacity"]:
        messagebox.showerror("Full", f"Sorry, {ward_choice} is full!")
        return

    name_key = name.lower().replace(" ", "_")
    patient_entry = {"name": name, "ward": ward_choice}
    idx = bisect.bisect_left(patient_names, name_key)
    patients.insert(idx, patient_entry)
    patient_names.insert(idx, name_key)
    ward_data["occupied"] += 1

    add_patient_to_db(name, name_key, ward_choice)
    update_visualization()

    messagebox.showinfo("Success", f"Bed allocated to {name} in {ward_choice}")
    entry_name.delete(0, tk.END)
    combo_ward.set("")

def discharge_patient():
    name = entry_discharge.get().strip().lower()
    if not name:
        messagebox.showwarning("Input Error", "Enter a patient name to discharge.")
        return

    idx = bisect.bisect_left(patient_names, name)
    if idx < len(patient_names) and patient_names[idx] == name:
        patient = patients[idx]
        ward = patient["ward"]
        wards[ward]["occupied"] -= 1
        del patients[idx]
        del patient_names[idx]
        discharge_patient_from_db(name)
        update_visualization()
        messagebox.showinfo("Discharged", f"{name.title()} discharged from {ward}")
        entry_discharge.delete(0, tk.END)
    else:
        messagebox.showwarning("Not Found", f"No patient found with name {name.title()}")

app = tb.Window(themename="cosmo")
app.title("🏥 Smart Hospital Bed Allocation System")
app.geometry("900x700")

title = tb.Label(
    app,
    text="🏥 Smart Hospital Bed Allocation System",
    font=("Helvetica", 22, "bold"),
    bootstyle="primary",
)
title.pack(pady=20)

frame_table = tb.Frame(app)
frame_table.pack(pady=10)

columns = ("Ward", "Capacity", "Occupied", "Available")
tree = ttk.Treeview(frame_table, columns=columns, show="headings", height=8)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, anchor="center", width=150)
tree.pack()


# Allocation Frame
# -----------------------------
frame_allocate = tb.Labelframe(app, text="Allocate Bed", bootstyle="info")
frame_allocate.pack(pady=15, padx=25, fill="x")

tb.Label(frame_allocate, text="Patient Name:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5)
entry_name = tb.Entry(frame_allocate, width=25)
entry_name.grid(row=0, column=1, padx=5, pady=5)

tb.Label(frame_allocate, text="Select Ward:", font=("Arial", 11)).grid(row=0, column=2, padx=5, pady=5)
combo_ward = tb.Combobox(frame_allocate, values=list(wards.keys()), width=22, state="readonly")
combo_ward.grid(row=0, column=3, padx=5, pady=5)

btn_allocate = tb.Button(frame_allocate, text="Allocate Bed", bootstyle="success", command=allocate_bed)
btn_allocate.grid(row=0, column=4, padx=10)

frame_discharge = tb.Labelframe(app, text="Discharge Patient", bootstyle="danger")
frame_discharge.pack(pady=15, padx=25, fill="x")

tb.Label(frame_discharge, text="Patient Name:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5)
entry_discharge = tb.Entry(frame_discharge, width=25)
entry_discharge.grid(row=0, column=1, padx=5, pady=5)

btn_discharge = tb.Button(frame_discharge, text="Discharge", bootstyle="danger-outline", command=discharge_patient)
btn_discharge.grid(row=0, column=2, padx=10)

frame_patients = tb.Labelframe(app, text="Current Patients", bootstyle="secondary")
frame_patients.pack(pady=20, padx=25, fill="both", expand=True)

columns_patient = ("Name", "Ward")
patient_tree = ttk.Treeview(frame_patients, columns=columns_patient, show="headings", height=8)
for col in columns_patient:
    patient_tree.heading(col, text=col)
    patient_tree.column(col, anchor="center", width=180)
patient_tree.pack(fill="both", expand=True, padx=10, pady=10)

init_db(wards, patients, patient_names)
combo_ward["values"] = list(wards.keys())
update_visualization()

footer = tb.Label(app, text="Developed using Python, Tkinter, MySQL & DAA Concepts", font=("Arial", 10), bootstyle="secondary")
footer.pack(side="bottom", pady=10)

app.mainloop()