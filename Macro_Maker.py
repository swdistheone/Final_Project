import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pynput import mouse, keyboard
import threading, time, json, pyautogui, os, math, sys, datetime

# -------------------- GLOBALS --------------------
recorded_events = []
recording = False
stop_flag = threading.Event()
speed_multiplier = 1.0
hotkey_macros = {}  # dict (e.g., {"<f6>": "/path/to/macro.json"})
bg_color_running = "#ffcccc"
bg_color_default = "#f0f0f0"
bg_cycle_enabled = False
macro_playing = False
click_count = 0
repeat_count = 1
pause_flag = threading.Event()
pause_flag.set()  # initially unpaused
current_macro_path = None  # updated by Load

SPECIAL_KEYS = {
    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
    'alt_l': 'alt', 'alt_r': 'alt',
    'shift_l': 'shift', 'shift_r': 'shift',
    'cmd': 'command', 'cmd_r': 'command',
    'win': 'win'
}

# -------------------- HELPERS --------------------
def normalize_key(k):
    """Normalize pynput key names for pyautogui."""
    if isinstance(k, str):
        k = k.lower()
        if k.startswith("key."):
            k = k[4:]
        return SPECIAL_KEYS.get(k, k)
    return k

def ui(fn, *a, **kw):
    """Thread-safe call to update UI."""
    root.after(0, lambda: fn(*a, **kw))

def smart_sleep(seconds):
    """Sleep that checks pause flag and stop flag for responsiveness."""
    end = time.time() + seconds
    while time.time() < end and macro_playing:
        wait_while_paused()
        time.sleep(min(0.02, end - time.time()))

# -------------------- THEME / BACKGROUND --------------------
def apply_theme(*_):
    """Set theme from dropdown and (re)start RGB cycle if selected."""
    global bg_color_default, bg_cycle_enabled
    theme = theme_var.get()
    if theme == "light":
        bg_color_default = "#f0f0f0"; bg_cycle_enabled = False
    elif theme == "dark":
        bg_color_default = "#2e2e2e"; bg_cycle_enabled = False
    elif theme == "blue":
        bg_color_default = "#d0e6ff"; bg_cycle_enabled = False
    elif theme == "green":
        bg_color_default = "#d4f7d4"; bg_cycle_enabled = False
    elif theme == "purple":
        bg_color_default = "#e0d4f7"; bg_cycle_enabled = False
    elif theme == "yellow":
        bg_color_default = "#fff7d4"; bg_cycle_enabled = False
    elif theme == "orange":
        bg_color_default = "#ffe0b3"; bg_cycle_enabled = False
    elif theme == "pink":
        bg_color_default = "#ffd4e7"; bg_cycle_enabled = False
    elif theme == "RGB":
        bg_color_default = "#ffffff"; bg_cycle_enabled = True

    # Apply to root + children (best-effort for non-ttk widgets)
    root.configure(bg=bg_color_default)
    for w in root.winfo_children():
        try:
            w.configure(bg=bg_color_default)
        except Exception:
            pass

    # Start/continue the RGB cycle (no-op if disabled)
    cycle_background()

def cycle_background(t=0.0):
    """Animate background if RGB theme is active and not recording/playing."""
    if not bg_cycle_enabled:
        # Ensure static theme color applied
        root.configure(bg=bg_color_default)
        for w in root.winfo_children():
            try:
                w.configure(bg=bg_color_default)
            except Exception:
                pass
        return  # stop cycling until re-enabled

    # If recording or playing, don't animate; try again soon
    if recording or macro_playing:
        root.after(200, lambda: cycle_background(t + 0.005))
        return

    # Smooth RGB sine-wave
    r = int((math.sin(t) * 127) + 128)
    g = int((math.sin(t + 2) * 127) + 128)
    b = int((math.sin(t + 4) * 127) + 128)
    color = f"#{r:02x}{g:02x}{b:02x}"

    # Apply color to root and children
    root.configure(bg=color)
    for w in root.winfo_children():
        try:
            w.configure(bg=color)
        except Exception:
            pass

    root.after(200, lambda: cycle_background(t + 0.005))

# -------------------- RECORDING --------------------
def on_click(x, y, button, pressed):
    if recording:
        event_type = 'press' if pressed else 'release'
        recorded_events.append((event_type, button.name, time.time()))

def on_press(key):
    if recording:
        try:
            recorded_events.append(('key_press', key.char, time.time()))
        except AttributeError:
            recorded_events.append(('key_press', str(key), time.time()))

def on_release(key):
    if recording:
        try:
            recorded_events.append(('key_release', key.char, time.time()))
        except AttributeError:
            recorded_events.append(('key_release', str(key), time.time()))

def listen_for_stop():
    def on_key(key):
        if key == keyboard.Key.enter:
            stop_flag.set()
            return False
    with keyboard.Listener(on_press=on_key) as listener:
        listener.join()

def record_macro():
    global recording, recorded_events
    recorded_events = []
    recording = True
    stop_flag.clear()

    messagebox.showinfo("Recording", "Recording started. Press Enter to stop.")

    def _record():
        global recording
        with mouse.Listener(on_click=on_click) as ml, \
             keyboard.Listener(on_press=on_press, on_release=on_release) as kl:
            listener_thread = threading.Thread(target=listen_for_stop, daemon=True)
            listener_thread.start()

            while not stop_flag.is_set():
                time.sleep(0.01)

            ml.stop(); kl.stop()
            listener_thread.join()

        recording = False
        if recorded_events:
            base = recorded_events[0][-1]
            for i in range(len(recorded_events)):
                recorded_events[i] = (*recorded_events[i][:-1], recorded_events[i][-1] - base)

        messagebox.showinfo("Stopped", f"Recording stopped. {len(recorded_events)} events recorded.")

    threading.Thread(target=_record, daemon=True).start()

# -------------------- MACRO EDITOR --------------------
def open_macro_editor():
    editor = tk.Toplevel(root)
    editor.title("Macro Editor")
    editor.geometry("600x400")
    listbox = tk.Listbox(editor, width=80, height=20)
    listbox.pack(pady=10)
    
    def refresh_list():
        listbox.delete(0, tk.END)
        for i, event in enumerate(recorded_events):
            listbox.insert(tk.END, f"{i+1}: {event}")

    refresh_list()

    def delete_selected():
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del recorded_events[idx]
        refresh_list()

    tk.Button(editor, text="Delete Selected Step", command=delete_selected).pack(pady=5)
    tk.Button(editor, text="Close", command=editor.destroy).pack(pady=5)

# -------------------- SAVE/LOAD --------------------
def save_macro():
    file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
    if file:
        with open(file, "w") as f:
            json.dump(recorded_events, f)
        messagebox.showinfo("Saved", "Macro saved successfully!")

def load_macro():
    global current_macro_path
    file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
    if file:
        current_macro_path = file
        messagebox.showinfo("Loaded", f"Loaded: {os.path.basename(file)}")

# -------------------- PLAYBACK --------------------
def stop_macro():
    global macro_playing
    macro_playing = False

def toggle_pause():
    if pause_flag.is_set():
        pause_flag.clear()
        pause_btn.config(text="▶️ Resume")
    else:
        pause_flag.set()
        pause_btn.config(text="⏸ Pause")

def wait_while_paused():
    while not pause_flag.is_set():
        time.sleep(0.05)

def play_macro_events_with_pause(events):
    def _play():
        global macro_playing, click_count
        # Always reset clicks at the very start of playback
        click_count = 0
        ui(click_label.config, text=f"Clicks: {click_count}")

        macro_playing = True
        # Temporarily override background while running
        ui(root.configure, bg=bg_color_running)
        ui(indicator_label.pack, pady=5)
        ui(stop_btn.pack, pady=5)
        ui(pause_btn.pack, pady=5)
        ui(countdown_label.pack, pady=3)
        ui(progress_bar.pack, pady=5)
        ui(progress_bar.config, maximum=len(events), value=0)

        for repeat in range(repeat_count):
            for i, event in enumerate(events):
                if not macro_playing:
                    break
                wait_while_paused()

                if i > 0:
                    delay = (event[-1] - events[i - 1][-1]) / speed_multiplier
                    ui(countdown_label.config, text=f"Step {i}/{len(events)} (delay {delay:.2f}s)")
                    smart_sleep(delay)

                event_type, data, _ = event
                if event_type == 'press':
                    pyautogui.mouseDown(button=data)
                    click_count += 1
                    ui(click_label.config, text=f"Clicks: {click_count}")
                elif event_type == 'release':
                    pyautogui.mouseUp(button=data)
                elif event_type == 'key_press':
                    pyautogui.keyDown(normalize_key(data))
                elif event_type == 'key_release':
                    pyautogui.keyUp(normalize_key(data))

                ui(progress_bar.config, value=i+1)

        # Restore UI
        ui(indicator_label.pack_forget)
        ui(countdown_label.pack_forget)
        ui(stop_btn.pack_forget)
        ui(pause_btn.pack_forget)
        ui(progress_bar.pack_forget)
        ui(root.configure, bg=bg_color_default)  # base color; RGB cycle (if any) resumes
        macro_playing = False
        messagebox.showinfo("Done", "Macro playback finished.")

        # If RGB is enabled, ensure the cycle continues
        if bg_cycle_enabled:
            ui(cycle_background)

    threading.Thread(target=_play, daemon=True).start()

def play_macro():
    update_speed_repeat()
    path = current_macro_path or "macro.json"
    try:
        with open(path, "r") as f:
            events = json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load macro: {e}")
        return
    play_macro_events_with_pause(events)

# -------------------- SCHEDULING --------------------
def schedule_macro():
    file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
    if not file:
        return
    time_str = simpledialog.askstring("Schedule Time", "Enter time (HH:MM, 24hr format):")
    if not time_str:
        return
    try:
        h, m = map(int, time_str.split(':'))
        now = datetime.datetime.now()
        run_time = datetime.datetime(now.year, now.month, now.day, h, m)
        if run_time < now:
            run_time += datetime.timedelta(days=1)
        delay_sec = (run_time - now).total_seconds()
        def run_scheduled():
            time.sleep(delay_sec)
            play_macro_file(file)
        threading.Thread(target=run_scheduled, daemon=True).start()
        messagebox.showinfo("Scheduled", f"Macro scheduled to run at {run_time.strftime('%H:%M')}")
    except:
        messagebox.showerror("Invalid", "Time format should be HH:MM")

# -------------------- HOTKEYS --------------------
def assign_hotkey():
    macro_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
    if not macro_file:
        return
    key = simpledialog.askstring("Assign Key", "Enter key (e.g., f6, f7):")
    if not key:
        return
    key = f"<{key.lower()}>"
    hotkey_macros[key] = macro_file
    messagebox.showinfo("Assigned", f"Hotkey {key.upper()} → {macro_file}")

def play_macro_file(file_path):
    """Runs a macro by file path (used by hotkeys + scheduler). Ensures clicks reset."""
    global click_count
    click_count = 0
    ui(click_label.config, text=f"Clicks: {click_count}")
    try:
        with open(file_path, "r") as f:
            events = json.load(f)
        play_macro_events_with_pause(events)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to play macro file: {e}")

def listen_for_macro_keys():
    def on_press(key):
        name = None
        try:
            name = f"<{key.name.lower()}>"
        except AttributeError:
            if hasattr(key, "char") and key.char:
                name = f"<{key.char.lower()}>"
        if not name:
            return
        path = hotkey_macros.get(name)
        if path:
            threading.Thread(target=play_macro_file, args=(path,), daemon=True).start()
    keyboard.Listener(on_press=on_press).start()

# -------------------- GUI --------------------
root = tk.Tk()
root.title("🔥 Macro Recorder")
root.geometry("1080x900")
root.resizable(False, False)
root.configure(bg=bg_color_default)

indicator_label = tk.Label(root, text="Your custom macro running...", font=("Arial", 12), fg="red", bg=bg_color_default)
countdown_label = tk.Label(root, text="", font=("Arial", 10), bg=bg_color_default)
click_label = tk.Label(root, text="Clicks: 0", font=("Arial", 11), bg=bg_color_default)
click_label.pack(pady=3)

tk.Label(root, text="Record your macro and then execute it.", font=("Arial", 15), bg=bg_color_default).pack(pady=10)


text_box = tk.Text(root, height=3, width=40)
text_box.pack(pady=5)

tk.Button(root, text="Record your macro (Enter to stop recording)", command=record_macro).pack(pady=6)
tk.Button(root, text="Edit/View Recorded Macro Steps", command=open_macro_editor).pack(pady=6)
tk.Button(root, text="Save your last recorded macro", command=save_macro).pack(pady=6)
tk.Button(root, text="Load a saved macro", command=load_macro).pack(pady=6)
tk.Button(root, text="Play your macro", command=play_macro).pack(pady=6)
pause_btn = tk.Button(root, text="⏸ Pause", command=toggle_pause)
tk.Button(root, text="Schedule Macro for a time (military time)", command=schedule_macro).pack(pady=5)
stop_btn = tk.Button(root, text="⏹ Stop Playback", command=stop_macro)


tk.Label(root, text="How fast do you want to execute?:", bg=bg_color_default).pack(pady=2)
speed_slider = tk.Scale(root, from_=0.2, to=10, resolution=0.1, orient=tk.HORIZONTAL, bg=bg_color_default)
speed_slider.set(1.0)
speed_slider.pack()

repeat_var = tk.IntVar(value=1)
tk.Label(root, text="How many times to loop?", bg=bg_color_default).pack(pady=2)
repeat_entry = tk.Entry(root, textvariable=repeat_var)
repeat_entry.pack()

def update_speed_repeat():
    global speed_multiplier, repeat_count
    speed_multiplier = speed_slider.get()
    try:
        repeat_count = int(repeat_var.get())
    except:
        repeat_count = 1

speed_slider.bind("<ButtonRelease-1>", lambda e: update_speed_repeat())
repeat_entry.bind("<FocusOut>", lambda e: update_speed_repeat())

# Theme dropdown with all options; hooked to apply_theme
theme_var = tk.StringVar(value="light")
colors = ["light", "dark", "blue", "green", "purple", "yellow", "orange", "pink", "RGB"]
ttk.OptionMenu(root, theme_var, "light", *colors, command=lambda *_: apply_theme()).pack(pady=6)

assign_btn = tk.Button(root, text="Give any key a Macro.", command=assign_hotkey)
assign_btn.pack(pady=5)

tk.Label(root, text="Use your assigned keys to play macros globally", font=("Arial", 9), bg=bg_color_default).pack(pady=4)
tk.Label(root, text="Made By Sean Dorsey", font=("Arial", 9), bg=bg_color_default).pack(side="bottom", pady=10)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.pack_forget()

# Start hotkey listener + apply initial theme, including RGB cycle if selected
threading.Thread(target=listen_for_macro_keys, daemon=True).start()
apply_theme()

root.mainloop()

# Optional CLI Playback
if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--play":
    play_macro_file(sys.argv[2])
