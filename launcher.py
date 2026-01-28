import requests
import os
import sys
import time
import shutil
import traceback

# --- DEPENDENCY IMPORTS FOR PYINSTALLER ---
# PyInstaller needs to see these imports to bundle them.
# We don't use them directly in launcher, but the dynamic script will.
if False:
    import tkinter
    import tkinter.ttk 
    from tkinter import ttk, messagebox
    import webbrowser
    import threading
    import gspread
    import oauth2client
    from oauth2client.service_account import ServiceAccountCredentials  # Critical for PyInstaller
    import selenium
    import pyperclip
    import PIL
    import datetime
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException

# --- CONFIGURATION (USER MUST UPDATE THIS) ---
REMOTE_BASE_URL = "https://raw.githubusercontent.com/pengyu21/cafe-auto-update/refs/heads/main/"

FILES_TO_SYNC = [
    "cafeauto.py", 
    "gui_main.py", 
    "pyarmor_runtime_000000/__init__.py", 
    "pyarmor_runtime_000000/pyarmor_runtime.pyd"
]
VERSION_FILE = "version.txt"
JSON_FILE = "service_account.json"

def show_error(title, message):
    """Shows an error message box using ctypes (safe for windowed mode)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10) # 0x10 = MB_ICONERROR
    except:
        print(f"[{title}] {message}")

def hide_file(filename):
    """Sets the file as hidden on Windows."""
    try:
        import ctypes
        if os.path.exists(filename):
            # FILE_ATTRIBUTE_HIDDEN = 0x02
            ctypes.windll.kernel32.SetFileAttributesW(filename, 0x02)
    except:
        pass

def get_base_path():
    """Returns the base path for resources."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def ensure_json_file():
    """Extracts service_account.json from the bundle if needed."""
    if os.path.exists(JSON_FILE):
        return

    bundled_path = os.path.join(get_base_path(), JSON_FILE)
    if os.path.exists(bundled_path):
        try:
            shutil.copy(bundled_path, JSON_FILE)
        except Exception as e:
            show_error("Launcher Error", f"Failed to extract {JSON_FILE}: {e}")

def get_remote_version():
    try:
        # Add timestamp to bypass cache
        url = REMOTE_BASE_URL + VERSION_FILE + f"?t={time.time()}"
        print(f"[Launcher] Checking version from: {url}")
        
        # Increased timeout to 5s
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return None
    except Exception as e:
        # Silently fail on connection error in production usually, or log
        print(f"[Launcher] Error checking remote version: {e}")
        return None

def parse_version(v):
    """Parses version string into tuple of integers for comparison."""
    try:
        return tuple(map(int, v.split('.')))
    except:
        return (0, 0, 0)

def get_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"

def update_files():
    print("[Launcher] Starting update process...")
    # In windowed mode, we can't print easily. 
    # Just try download. If fail, we proceed with old files.
    for filename in FILES_TO_SYNC:
        # Add timestamp to bypass cache
        url = REMOTE_BASE_URL + filename + f"?t={time.time()}"
        try:
            # Support subdirectories for PyArmor runtime
            dir_name = os.path.dirname(filename)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                hide_file(dir_name) # Hide the folder too
                
            print(f"[Launcher] Downloading {filename}...")
            response = requests.get(url, timeout=15) # Increased timeout
            if response.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(response.content)
                hide_file(filename) 
        except Exception as e:
            print(f"[Launcher] Failed to download {filename}: {e}")
            pass
    
    remote_ver = get_remote_version()
    if remote_ver:
        try:
            with open(VERSION_FILE, "w", encoding="utf-8") as f:
                f.write(remote_ver)
            print(f"[Launcher] Updated version.txt to {remote_ver}")
        except: pass

def run_application():
    ensure_json_file()
    
    # Hide all related files and folders on every startup
    hide_targets = FILES_TO_SYNC + [VERSION_FILE, JSON_FILE]
    for f in hide_targets:
        hide_file(f)
        # Also hide parent folders if any
        parent = os.path.dirname(f)
        if parent: hide_file(parent)

    if not os.path.exists("gui_main.py"):
        show_error("Launcher Error", "gui_main.py not found.\nPlease check your internet connection and try again.")
        return

    # Dynamic Execution
    try:
        import runpy
        
        # 1. Ensure current directory is in sys.path
        current_dir = os.getcwd()
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # 2. Add exe dir
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if exe_dir not in sys.path and exe_dir != current_dir:
            sys.path.insert(0, exe_dir)

        # 3. Validation: Check if files exist and are not empty
        if os.path.getsize("cafeauto.py") < 100:
             show_error("File Error", "cafeauto.py seems too small/corrupted.\nPlease check GitHub URL or internet.")
             return

        # 4. Try loading cafeauto dynamically to ensure it exists
        try:
            # Clear from sys.modules to force fresh load from path
            if 'cafeauto' in sys.modules: del sys.modules['cafeauto']
            if 'gui_main' in sys.modules: del sys.modules['gui_main']

            import importlib.util
            spec = importlib.util.spec_from_file_location("cafeauto", os.path.join(current_dir, "cafeauto.py"))
            cafeauto_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cafeauto_mod)
            
            # NOTE: We skip constant 'hasattr' checks here because PyArmor 
            # obfuscation wraps the module and standard inspection may fail.
            print("[Launcher] cafeauto module loaded successfully.")
        except Exception as e:
            show_error("Import Error", f"Failed to load cafeauto.py:\n{traceback.format_exc()}")
            return

        # 5. Run gui_main using runpy (safer than exec)
        print("[Launcher] Running gui_main.py...")
        runpy.run_path("gui_main.py", run_name="__main__")
        
    except Exception as e:
        err_msg = f"Failed to run app: {e}\n\n{traceback.format_exc()}"
        show_error("Execution Error", err_msg)

def main():
    # Only try update if we can access the server
    try:
        print("[Launcher] Checking for updates...")
        local_ver = get_local_version()
        remote_ver = get_remote_version()
        
        if remote_ver and parse_version(remote_ver) > parse_version(local_ver):
             print(f"[Launcher] New version available: {remote_ver} (Current: {local_ver})")
             update_files()
    except Exception as e:
        print(f"[Launcher] Update check failed: {e}")

    run_application()

if __name__ == "__main__":
    main()
