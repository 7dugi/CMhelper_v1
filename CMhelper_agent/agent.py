import tkinter as tk
from tkinter import ttk, messagebox
import requests
import pyautogui
import pyperclip
import time
import random
import threading
import io
import os
import sys
import winreg
import socket
import json
import uuid
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from PIL import Image
import win32clipboard
import win32gui
import win32con

API_BASE_URL = "https://cmhelper-v1.vercel.app/api"
POLL_INTERVAL_MS = 30000
HEARTBEAT_INTERVAL = 180

def get_agent_uuid():
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = json.load(f)
            if "agent_uuid" in data:
                return data["agent_uuid"]
    new_uuid = str(uuid.uuid4())
    with open(config_path, "w") as f:
        json.dump({"agent_uuid": new_uuid}, f)
    return new_uuid

AGENT_UUID = get_agent_uuid()

# Logger setup
if not os.path.exists("logs"):
    os.makedirs("logs")
logger = logging.getLogger("CMAgent")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler("logs/agent.log", when="midnight", interval=1, backupCount=30, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def mask_name(name):
    if not name: return ""
    if len(name) <= 2: return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]

def check_single_instance():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 18002))
        s.listen(1)
        def listen_for_wakeups(server_socket):
            while True:
                try:
                    conn, addr = server_socket.accept()
                    conn.recv(1024)
                    conn.close()
                    if 'app' in globals() and app:
                        app.after(0, app.load_queue)
                except:
                    pass
        threading.Thread(target=listen_for_wakeups, args=(s,), daemon=True).start()
        return True, s
    except socket.error:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', 18002))
            s.sendall(b"WAKE_UP")
            s.close()
        except:
            pass
        return False, None

def register_protocol():
    try:
        exe_path = os.path.abspath(sys.argv[0])
        key_path = r"Software\Classes\cmhelper"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValue(key, "", winreg.REG_SZ, "URL:CMhelper Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        cmd_key = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValue(cmd_key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)
    except Exception as e:
        logger.error(f"Failed to register protocol: {e}")

class CMHelperAgent(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CMhelper PC 에이전트")
        self.geometry("650x650")
        self.resizable(False, False)
        
        self.is_running = False
        self.tasks_to_send = []
        self.retry_queue = []
        self.consecutive_failures = 0
        self.current_task_id = None
        
        # UI Elements
        ttk.Label(self, text="카카오톡 자동 발송 에이전트", font=("Malgun Gothic", 16, "bold")).pack(pady=10)
        
        self.status_var = tk.StringVar(value="상태: ⚪ 대기 중")
        ttk.Label(self, textvariable=self.status_var, font=("Malgun Gothic", 10)).pack(pady=2)
        
        self.progress_var = tk.StringVar(value="진행률: 0 / 0")
        ttk.Label(self, textvariable=self.progress_var, font=("Malgun Gothic", 10)).pack(pady=2)
        
        columns = ("name", "contact", "status", "msg", "retry")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        self.tree.heading("name", text="고객명")
        self.tree.heading("contact", text="연락처")
        self.tree.heading("status", text="상태")
        self.tree.heading("msg", text="로그/사유")
        self.tree.heading("retry", text="재시도")
        
        self.tree.column("name", width=80, anchor=tk.CENTER)
        self.tree.column("contact", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=70, anchor=tk.CENTER)
        self.tree.column("msg", width=250, anchor=tk.W)
        self.tree.column("retry", width=50, anchor=tk.CENTER)
        self.tree.pack(pady=5, padx=10, fill=tk.X)
        
        self.log_text = tk.Text(self, height=8, font=("Malgun Gothic", 9))
        self.log_text.pack(pady=5, padx=10, fill=tk.X)
        
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(pady=10)
        
        self.load_btn = ttk.Button(self.btn_frame, text="대기열 불러오기", command=self.load_queue)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = ttk.Button(self.btn_frame, text="발송 시작", command=self.start_sending, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(self.btn_frame, text="중지", command=self.stop_sending, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(self.btn_frame, text="발송 취소 (선택)", command=self.cancel_queue)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        logger.info(f"에이전트 시작됨. UUID: {AGENT_UUID}")
        
        # Start Heartbeat Thread
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        
        # Auto Polling
        self.after(POLL_INTERVAL_MS, self._auto_poll)
        
        if len(sys.argv) > 1 and sys.argv[1].startswith("cmhelper://"):
            self.audit_log("SYSTEM", "웹에서 에이전트가 자동 호출되었습니다.")
            self.after(500, self.load_queue)

    def _auto_poll(self):
        if not self.is_running and not self.tasks_to_send and not self.retry_queue:
            self.load_queue(auto=True)
        self.after(POLL_INTERVAL_MS, self._auto_poll)

    def _heartbeat_loop(self):
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            if self.is_running:
                # Ping current task
                if self.current_task_id:
                    try: requests.put(f"{API_BASE_URL}/messages/{self.current_task_id}/heartbeat?agent_uuid={AGENT_UUID}", timeout=5)
                    except: pass
                # Ping queued tasks
                for task in self.tasks_to_send + self.retry_queue:
                    try: requests.put(f"{API_BASE_URL}/messages/{task.get('id')}/heartbeat?agent_uuid={AGENT_UUID}", timeout=5)
                    except: pass

    def audit_log(self, phase, msg, task_id=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] [{phase}] {msg}"
        self.log_text.insert(tk.END, log_msg + "\n")
        self.log_text.see(tk.END)
        self.update_idletasks()
        
        # Write to Rotating File
        file_msg = f"[JOB-{task_id}] {msg}" if task_id else msg
        if phase in ["FAILED", "API_ERR", "WARN"]:
            logger.error(f"[{phase}] {file_msg}")
        else:
            logger.info(f"[{phase}] {file_msg}")

    def update_tree_status(self, task_id, status_text, msg_text="", retry_count=0):
        for item in self.tree.get_children():
            if self.tree.item(item, "tags") == (str(task_id),):
                vals = self.tree.item(item, "values")
                self.tree.item(item, values=(vals[0], vals[1], status_text, msg_text, f"{retry_count}/2"))
                self.tree.see(item)
                break
        self.update_idletasks()

    def send_to_clipboard(self, clip_type, data):
        retry = 0
        while retry < 3:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(clip_type, data)
                win32clipboard.CloseClipboard()
                return True
            except:
                retry += 1
                time.sleep(0.5)
        raise Exception("ERR_CLIPBOARD_LOCKED")

    def copy_image_to_clipboard(self, image_data):
        image = Image.open(io.BytesIO(image_data))
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        image.close()
        self.send_to_clipboard(win32clipboard.CF_DIB, data)

    def activate_kakaotalk(self):
        hwnd = win32gui.FindWindow("EVA_Window_Dblclk", "카카오톡")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
        return False

    def close_all_chatrooms(self):
        def enum_cb(hwnd, results):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            if class_name == "EVA_Window_Dblclk" and title != "카카오톡" and title != "":
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        win32gui.EnumWindows(enum_cb, None)
        time.sleep(0.5)

    def load_queue(self, auto=False):
        if self.is_running: return
        if not auto: self.audit_log("FETCH", "서버에서 대기열을 가져옵니다.")
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self._fetch_tasks, args=(auto,), daemon=True).start()

    def _fetch_tasks(self, auto=False):
        try:
            res = requests.get(f"{API_BASE_URL}/messages/pending?agent_uuid={AGENT_UUID}")
            if res.status_code != 200:
                if not auto: self.audit_log("API_ERR", f"HTTP {res.status_code}")
                return
            
            data = res.json()
            if not data:
                return
                
            self.tasks_to_send = data
            total = len(self.tasks_to_send)
                
            self.audit_log("FETCH", f"총 {total}건 예약건 감지. 발송을 시작합니다.")
            self.progress_var.set(f"진행률: 0 / {total}")
            
            for t in self.tasks_to_send:
                m_name = mask_name(t.get("customer_name"))
                self.tree.insert("", "end", values=(m_name, "********", "⚪ 대기중", "", "0/2"), tags=(str(t.get("id")),))
                
            self.start_btn.config(state=tk.NORMAL)
            
            # Auto-start if fetched successfully
            self.after(2000, self.start_sending)
        except Exception as e:
            if not auto: self.audit_log("API_ERR", f"대기열 불러오기 실패: {e}")

    def cancel_queue(self):
        if self.is_running:
            self.audit_log("WARN", "발송 중에는 취소할 수 없습니다.")
            return
        selected_items = self.tree.selection()
        if not selected_items:
            self.audit_log("WARN", "취소할 항목을 선택해주세요.")
            return
        threading.Thread(target=self._run_cancel_selected, args=(selected_items,), daemon=True).start()

    def _run_cancel_selected(self, selected_items):
        for item in selected_items:
            tags = self.tree.item(item, "tags")
            if tags:
                task_id = tags[0]
                try: requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "CANCELLED", "error_code": "User Canceled"})
                except: pass
                self.tree.delete(item)
                self.tasks_to_send = [t for t in self.tasks_to_send if str(t.get("id")) != task_id]
        
        self.audit_log("CANCEL", "취소 완료.")
        if len(self.tasks_to_send) == 0:
            self.start_btn.config(state=tk.DISABLED)

    def start_sending(self):
        if self.is_running or not self.tasks_to_send: return
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        self.retry_queue = []
        self.consecutive_failures = 0
        threading.Thread(target=self._dispatcher_loop, daemon=True).start()

    def stop_sending(self):
        self.is_running = False
        self.status_var.set("상태: ⚪ 정지됨")
        self.audit_log("WARN", "사용자 중지 요청. 현재 작업 후 정지합니다.")

    def _dispatcher_loop(self):
        self.audit_log("SYSTEM", "Dispatcher 스레드 시작됨.")
        total = len(self.tasks_to_send)
        sent_count = 0
        
        while (self.tasks_to_send or self.retry_queue) and self.is_running:
            if self.consecutive_failures >= 5:
                self.audit_log("COOLDOWN", "연속 실패 5회 감지. 계정 보호를 위해 30초간 대기합니다.")
                for _ in range(30):
                    if not self.is_running: break
                    time.sleep(1)
                self.consecutive_failures = 0
            
            delay = random.uniform(3.0, 5.0)
            time.sleep(delay)
            if not self.is_running: break

            if self.retry_queue:
                task = self.retry_queue.pop(0)
            else:
                task = self.tasks_to_send.pop(0)

            self.current_task_id = task.get("id")
            success = self._process_job(task)
            self.current_task_id = None

            if success:
                sent_count += 1
                self.consecutive_failures = 0
                self.progress_var.set(f"진행률: {sent_count} / {total}")
            else:
                self.consecutive_failures += 1

        self.audit_log("SYSTEM", "모든 Dispatcher 작업 종료.")
        self.after(0, self._finish)

    def _process_job(self, task):
        customer_name = task.get("customer_name")
        m_name = mask_name(customer_name)
        msg_text = task.get("message_text", "")
        img_url = task.get("image_url")
        task_id = task.get("id")
        retry_count = task.get("retry_count", 0)
        
        self.status_var.set(f"상태: 🟡 '{m_name}' 님에게 발송 중...")
        self.audit_log("JOB_START", f"대상: {m_name} (재시도: {retry_count})", task_id)
        self.update_tree_status(task_id, "🟡 발송중", "", retry_count)
        
        try:
            self.close_all_chatrooms()
            if not self.activate_kakaotalk():
                raise Exception("ERR_KAKAO_NOT_FOUND")
            time.sleep(0.5)
            
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.3)
            
            pyautogui.press('end')
            pyautogui.press('backspace', presses=20)
            time.sleep(0.2)
            
            try:
                pyperclip.copy(customer_name)
                time.sleep(0.1)
            except:
                raise Exception("ERR_CLIPBOARD_LOCKED")
                
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(1.0)
            
            pyautogui.press('enter')
            time.sleep(1.5)
            
            active_hwnd = win32gui.GetForegroundWindow()
            active_title = win32gui.GetWindowText(active_hwnd).strip()
            active_class = win32gui.GetClassName(active_hwnd)
            
            if active_title == "카카오톡" or active_class != "EVA_Window_Dblclk":
                raise Exception("ERR_NOT_FOUND")
                
            if active_title != customer_name.strip():
                pyautogui.press('esc')
                raise Exception("ERR_NAME_MISMATCH")
            
            if img_url:
                try:
                    img_res = requests.get(img_url, timeout=10)
                    if img_res.status_code == 200:
                        self.copy_image_to_clipboard(img_res.content)
                        time.sleep(0.5)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.8)
                        pyautogui.press('enter')
                        time.sleep(1.0)
                except Exception as e:
                    self.audit_log("WARN", f"이미지 전송 실패: {e}", task_id)

            try:
                pyperclip.copy(msg_text)
                time.sleep(0.1)
            except:
                raise Exception("ERR_CLIPBOARD_LOCKED")
                
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(0.5)
            
            pyautogui.press('esc')
            
            try: requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "SUCCESS"})
            except: pass
            
            self.update_tree_status(task_id, "🟢 성공", "발송 완료", retry_count)
            self.audit_log("SUCCESS", f"{m_name} 발송 완료", task_id)
            return True

        except Exception as e:
            error_code = str(e)
            self.audit_log("FAILED", f"{m_name} 실패 사유: {error_code}", task_id)
            
            if retry_count < 2 and error_code in ["ERR_CLIPBOARD_LOCKED", "ERR_KAKAO_NOT_FOUND", "ERR_NOT_FOUND", "ERR_NAME_MISMATCH"]:
                task['retry_count'] = retry_count + 1
                self.retry_queue.append(task)
                self.update_tree_status(task_id, "🟠 복구중", error_code, retry_count + 1)
                self.audit_log("RETRY_QUEUE", f"재시도 큐에 등록됨 ({retry_count+1}/2)", task_id)
            else:
                try: requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "FAILED", "error_code": error_code})
                except: pass
                self.update_tree_status(task_id, "🔴 실패", error_code, retry_count)
                
            return False

    def _finish(self):
        self.is_running = False
        self.load_btn.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("상태: ⚪ 대기 중")

if __name__ == "__main__":
    is_first, server_socket = check_single_instance()
    if not is_first:
        sys.exit(0)
    register_protocol()
    app = CMHelperAgent()
    app.mainloop()
