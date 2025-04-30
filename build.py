import shutil
import subprocess

subprocess.run(
    [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--icon=icon.ico",
        "--name",
        "VSCode Force Pomodoro",
        "main.py",
    ]
)

shutil.copy("icon.ico", "dist/")
