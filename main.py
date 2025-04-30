import ctypes
import logging
import os
import sys
import threading
import time
import tkinter as tk
import winreg

import pygetwindow as gw
import pystray
from PIL import Image
from pystray import MenuItem as item

CONFIG_PATH = "config.json"

logging.basicConfig(
    filename="vscode_force_pomodoro.log",
    filemode="a",
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

APP_NAME = "VSCode Force Pomodoro"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
EXE_PATH = os.path.abspath(sys.argv[0])
TIME_TO_LOCK = 45 * 60
TIME_TO_SHOW_COUNTDOWN_BEFORE_LOCK = 60
COUNTDOWN_TIME = TIME_TO_LOCK - TIME_TO_SHOW_COUNTDOWN_BEFORE_LOCK
TIME_TO_KEEP_LOCKED = 15 * 60
COUNTDOWN_DURATION = TIME_TO_LOCK - COUNTDOWN_TIME

state = "stopped"
lock = threading.Lock()
vscode_time = 0
locked_until = None
should_exit = False
start_with_windows = False
time_item = item(
    lambda item: f"{vscode_time // 60:02}:{vscode_time % 60:02}",
    lambda: None,
    enabled=False,
)


tray_icon = None


def start_app():
    global state
    state = "running"
    update_tooltip()
    tray_icon.menu = build_menu()


def stop_app():
    global state, vscode_time
    state = "stopped"
    vscode_time = 0
    update_tooltip()
    tray_icon.menu = build_menu()


def update_tooltip():
    if tray_icon:
        status = "Rodando" if state == "running" else "Parado"
        tray_icon.title = f"{APP_NAME} – {status}"


def build_menu():
    state_label = "Parar" if state == "running" else "Iniciar"
    state_action = stop_app if state == "running" else start_app

    return pystray.Menu(
        time_item,
        item(state_label, state_action),
        item("Sair", quit_app),
    )


def is_vscode_active():
    logger.info(f"is_vscode_active checks at {vscode_time}")
    try:
        window = gw.getActiveWindow()
        if not window:
            logger.info("VSCode is closed")
            return False
        is_active = "Visual Studio Code" in window.title and not window.isMinimized
        logger.info(f"VSCode window active status is {is_active}")
        return is_active
    except Exception as e:
        logger.error(str(e))
        return False


def lock_screen():
    logger.info(f"locking screen at {vscode_time}")
    ctypes.windll.user32.LockWorkStation()


def show_overlay():
    logger.info(f"show_overlay started at time {vscode_time}")
    overlay = tk.Tk()
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True)
    overlay.configure(bg="red")
    overlay.geometry("300x50+0+0")
    label = tk.Label(
        overlay,
        text=f"Faltam {COUNTDOWN_DURATION} segundos!",
        fg="white",
        bg="red",
        font=("Helvetica", 20, "bold"),
    )
    label.pack()

    def countdown():
        for i in range((COUNTDOWN_DURATION - 1), 0, -1):
            logger.info(f"show_overlay countdown in secs {i}")
            label.config(text=f"Faltam {i} segundos!")
            overlay.update()
            time.sleep(1)
        overlay.destroy()

    threading.Thread(target=countdown).start()
    overlay.mainloop()


def toggle_startup():
    global start_with_windows
    logger.info(f"toggle_startup status is {start_with_windows}")
    if start_with_windows:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
            start_with_windows = False
        except FileNotFoundError as e:
            logger.error(str(e))
            pass
    else:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, EXE_PATH)
        start_with_windows = True

    logger.info(f"start_with_windows set to {start_with_windows}")


def monitor_loop():
    global vscode_time, locked_until
    logger.info(
        f"monitor_loop started with time: {vscode_time} and locked_until: {locked_until}"
    )

    try:
        while not should_exit:
            if state != "running":
                time.sleep(1)
                continue
            if locked_until and time.time() < locked_until:
                logger.info(f"monitor_loop window locked until: {locked_until}")
                lock_screen()
                time.sleep(5)
                continue
            elif locked_until:
                locked_until = None

            if is_vscode_active():
                logger.info(f"monitor_loop vscode is active at: {vscode_time}")
                vscode_time += 1
                if tray_icon:
                    tray_icon.update_menu()

            time.sleep(1)

            if vscode_time == COUNTDOWN_TIME:
                logger.info(f"monitor_loop show overlay at: {vscode_time}")
                threading.Thread(target=show_overlay).start()
            elif vscode_time >= TIME_TO_LOCK:
                logger.info(f"monitor_loop locked screen at: {vscode_time}")
                lock_screen()
                locked_until = time.time() + TIME_TO_KEEP_LOCKED
                vscode_time = 0
    except Exception as e:
        logger.exception(f"monitor_loop crashed with error: {e}")


def setup_startup_flag():
    global start_with_windows
    logger.info(f"setup_startup_flag {start_with_windows}")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            start_with_windows = True
    except FileNotFoundError as e:
        logger.error(str(e))
        start_with_windows = False


def quit_app(icon):
    logger.info(f"quit_app at {vscode_time}")
    global should_exit
    should_exit = True
    icon.stop()


def run_tray():
    global tray_icon
    logger.info(f"run_tray at {vscode_time}")
    setup_startup_flag()
    image = Image.open("icon.ico")
    tray_icon = pystray.Icon(APP_NAME, image, menu=build_menu())
    update_tooltip()
    threading.Thread(target=monitor_loop, daemon=True).start()
    tray_icon.run()


if __name__ == "__main__":
    run_tray()
