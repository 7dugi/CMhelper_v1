import sys
import time
from pywinauto import Application

def dump_kakao_ui():
    print("Starting KakaoTalk UI Dump...")
    try:
        # Connect to the KakaoTalk main window
        app = Application(backend="uia").connect(title="카카오톡", timeout=5)
        main_win = app.window(title="카카오톡")
        
        print("--- Main Window Control Identifiers ---")
        # To avoid massive output, we dump to a file and read it back
        with open("kakao_ui_dump.txt", "w", encoding="utf-8") as f:
            # redirect stdout to file
            original_stdout = sys.stdout
            sys.stdout = f
            main_win.print_control_identifiers(depth=4)
            sys.stdout = original_stdout
            
        print("Dump saved to kakao_ui_dump.txt successfully.")
        
    except Exception as e:
        print(f"Error connecting to KakaoTalk: {e}")

if __name__ == "__main__":
    dump_kakao_ui()
