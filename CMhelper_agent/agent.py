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
from PIL import Image
import win32clipboard
import win32gui
import win32con

API_BASE_URL = "https://cmhelper-v1.vercel.app/api"
# Uncomment below for local testing
# API_BASE_URL = "http://localhost:8002/api"

def register_protocol():
    """Register cmhelper:// custom protocol in Windows Registry"""
    try:
        exe_path = os.path.abspath(sys.argv[0])
        key_path = r"Software\Classes\cmhelper"
        
        # Create root key
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValue(key, "", winreg.REG_SZ, "URL:CMhelper Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        
        # Create shell\open\command
        cmd_key = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValue(cmd_key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
        
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Failed to register protocol: {e}")

class CMHelperAgent(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CMhelper PC 에이전트")
        self.geometry("600x550")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        
        self.is_running = False
        
        # UI Elements
        ttk.Label(self, text="카카오톡 자동 발송 에이전트", font=("Malgun Gothic", 16, "bold")).pack(pady=10)
        
        self.status_var = tk.StringVar(value="상태: 대기 중")
        ttk.Label(self, textvariable=self.status_var, font=("Malgun Gothic", 10)).pack(pady=2)
        
        self.progress_var = tk.StringVar(value="진행률: 0 / 0")
        ttk.Label(self, textvariable=self.progress_var, font=("Malgun Gothic", 10)).pack(pady=2)
        
        # Treeview for Queue
        columns = ("name", "contact", "status", "msg")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        self.tree.heading("name", text="고객명")
        self.tree.heading("contact", text="연락처")
        self.tree.heading("status", text="상태")
        self.tree.heading("msg", text="오류/비고")
        
        self.tree.column("name", width=80, anchor=tk.CENTER)
        self.tree.column("contact", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=70, anchor=tk.CENTER)
        self.tree.column("msg", width=300, anchor=tk.W)
        self.tree.pack(pady=5, padx=10, fill=tk.X)
        
        self.log_text = tk.Text(self, height=6, font=("Malgun Gothic", 9))
        self.log_text.pack(pady=5, padx=10, fill=tk.X)
        
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(pady=10)
        
        self.load_btn = ttk.Button(self.btn_frame, text="대기열 불러오기", command=self.load_queue)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = ttk.Button(self.btn_frame, text="발송 시작", command=self.start_sending, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(self.btn_frame, text="중지", command=self.stop_sending, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.tasks_to_send = []
        
        # If launched via protocol, auto-start might be useful, or we just let them click start.
        if len(sys.argv) > 1 and sys.argv[1].startswith("cmhelper://"):
            self.log("웹에서 호출되었습니다! 대기열을 불러옵니다.")
            self.after(500, self.load_queue)
            
    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.update_idletasks()

    def update_tree_status(self, task_id, status_text, msg_text=""):
        for item in self.tree.get_children():
            if self.tree.item(item, "tags") == (str(task_id),):
                vals = self.tree.item(item, "values")
                self.tree.item(item, values=(vals[0], vals[1], status_text, msg_text))
                self.tree.see(item)
                break
        self.update_idletasks()

    def send_to_clipboard(self, clip_type, data):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(clip_type, data)
        win32clipboard.CloseClipboard()

    def copy_image_to_clipboard(self, image_path):
        image = Image.open(image_path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        self.send_to_clipboard(win32clipboard.CF_DIB, data)

    def activate_kakaotalk(self):
        hwnd = win32gui.FindWindow(None, "카카오톡")
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
        return False

    def load_queue(self):
        if self.is_running:
            return
        self.log("서버에서 대기열을 가져옵니다...")
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self._fetch_tasks, daemon=True).start()

    def _fetch_tasks(self):
        try:
            res = requests.get(f"{API_BASE_URL}/messages/pending")
            if res.status_code != 200:
                self.log(f"API 오류: HTTP {res.status_code}")
                return
            
            self.tasks_to_send = res.json()
            total = len(self.tasks_to_send)
            if total == 0:
                self.log("발송 대기 중인 메시지가 없습니다.")
                return
                
            self.log(f"총 {total}건의 메시지를 불러왔습니다. [발송 시작]을 눌러주세요.")
            self.progress_var.set(f"진행률: 0 / {total}")
            
            for t in self.tasks_to_send:
                self.tree.insert("", "end", values=(t.get("customer_name"), t.get("customer_contact", ""), "대기", ""), tags=(str(t.get("id")),))
                
            self.start_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"대기열 불러오기 실패: {e}")

    def start_sending(self):
        if self.is_running or not self.tasks_to_send:
            return
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self._run_send_loop, daemon=True).start()

    def stop_sending(self):
        self.is_running = False
        self.log("발송 중지 요청됨. 현재 작업 후 정지합니다.")

    def _run_send_loop(self):
        try:
            tasks = self.tasks_to_send
            total = len(tasks)
            sent_count = 0
            
            for i, task in enumerate(tasks):
                if not self.is_running:
                    self.log("작업이 사용자에 의해 중단되었습니다.")
                    break
                    
                if i > 0 and i % 30 == 0:
                    self.log("어뷰징 방지를 위해 15분간 휴식합니다...")
                    for m in range(15):
                        if not self.is_running: break
                        time.sleep(60)
                
                customer_name = task.get("customer_name")
                msg_text = task.get("message_text", "")
                img_url = task.get("image_url")
                task_id = task.get("id")
                
                if not customer_name:
                    continue
                
                self.status_var.set(f"상태: '{customer_name}' 님에게 발송 중...")
                self.update_tree_status(task_id, "진행중")
                self.log(f"[{i+1}/{total}] {customer_name} 발송 시도...")
                
                # 1. 쿨타임 대기 (5~8초)
                time.sleep(random.uniform(5.0, 8.0))
                
                # 2. 카톡 활성화 로직
                if not self.activate_kakaotalk():
                    err_msg = "카카오톡 창을 찾을 수 없습니다!"
                    self.log(err_msg)
                    self.update_tree_status(task_id, "실패", err_msg)
                    self.is_running = False
                    break
                time.sleep(0.5)
                
                # Ctrl+F 로 검색창 이동
                pyautogui.hotkey('ctrl', 'f')
                time.sleep(0.5)
                
                # 이름 복사 후 붙여넣기
                pyperclip.copy(customer_name)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(1.0)
                
                # 엔터 눌러서 채팅방 열기
                pyautogui.press('enter')
                time.sleep(1.5) # 창 열리는 시간 조금 더 대기
                
                # 열린 창의 제목 검사 (동명이인/친구추가 팝업 방지)
                active_hwnd = win32gui.GetForegroundWindow()
                active_title = win32gui.GetWindowText(active_hwnd).strip()
                
                if active_title != customer_name.strip():
                    err_msg = f"이름 불일치 (기대:{customer_name} / 실제:{active_title})"
                    self.log(f"-> 발송 실패: {err_msg}")
                    pyautogui.press('esc') # 팝업 또는 엉뚱한 창 닫기/검색 취소
                    try:
                        requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "failed"})
                    except: pass
                    self.update_tree_status(task_id, "실패", "이름 불일치 또는 미등록")
                    continue
                
                # 성공적으로 정확한 채팅방이 열린 경우
                pyperclip.copy(msg_text)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.5)
                
                if img_url:
                    try:
                        img_res = requests.get(img_url)
                        if img_res.status_code == 200:
                            temp_img = "temp.png"
                            with open(temp_img, "wb") as f:
                                f.write(img_res.content)
                            self.copy_image_to_clipboard(temp_img)
                            time.sleep(0.5)
                            pyautogui.hotkey('ctrl', 'v')
                            time.sleep(0.5)
                            if os.path.exists(temp_img):
                                os.remove(temp_img)
                    except Exception as e:
                        self.log(f"이미지 첨부 실패: {e}")
                
                # 최종 엔터 (전송)
                pyautogui.press('enter')
                time.sleep(0.5)
                
                # ESC 눌러서 채팅방 닫기
                pyautogui.press('esc')
                
                # 서버 상태 업데이트
                requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "sent"})
                self.update_tree_status(task_id, "성공")
                
                sent_count += 1
                self.progress_var.set(f"진행률: {sent_count} / {total}")
                
            self.log("발송 작업이 완료되었습니다!")
            self._finish()
            
        except Exception as e:
            self.log(f"실행 중 오류 발생: {e}")
            self._finish()

    def _finish(self):
        self.is_running = False
        self.load_btn.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("상태: 대기 중")
        self.tasks_to_send = []

if __name__ == "__main__":
    register_protocol()
    app = CMHelperAgent()
    app.mainloop()
