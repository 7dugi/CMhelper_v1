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
import socket

try:
    from .api_client import AgentApiClient, AuthenticationError, AgentApiError
    from .kakao_ui import (
        KakaoUIAdapter,
        KakaoUIError,
        KakaoWindowNotFoundError,
        KakaoChatsNavigationError,
        KakaoSearchError,
        KakaoAmbiguousResultError,
        KakaoTitleMismatchError,
        KakaoPopupBlockedError,
    )
except ImportError:
    from api_client import AgentApiClient, AuthenticationError, AgentApiError
    from kakao_ui import (
        KakaoUIAdapter,
        KakaoUIError,
        KakaoWindowNotFoundError,
        KakaoChatsNavigationError,
        KakaoSearchError,
        KakaoAmbiguousResultError,
        KakaoTitleMismatchError,
        KakaoPopupBlockedError,
    )

API_BASE_URL = "https://cmhelper-v1.vercel.app/api"
# API_BASE_URL = "http://localhost:8002/api"

def check_single_instance():
    """이미 실행 중이면 기존 인스턴스에 신호 보내고 종료, 아니면 서버 열고 계속"""
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
                    # 기존 에이전트에 깨우기 신호 (인증 상태일 때만 대기열 새로고침)
                    if 'app' in globals() and app:
                        if app.api_client.is_authenticated():
                            app.after(0, app.load_queue)
                        else:
                            app.after(0, lambda: app.log("웹에서 호출되었습니다. 먼저 로그인해주세요."))
                except:
                    pass
        threading.Thread(target=listen_for_wakeups, args=(s,), daemon=True).start()
        return True, s
    except socket.error:
        # 이미 실행 중 -> 기존 인스턴스에 신호 보냄
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', 18002))
            s.sendall(b"WAKE_UP")
            s.close()
        except:
            pass
        return False, None

def register_protocol():
    """Register cmhelper:// custom protocol in Windows Registry"""
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
        print(f"Failed to register protocol: {e}")

class CMHelperAgent(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CMhelper PC 에이전트")
        self.geometry("600x640")
        self.resizable(False, False)

        self.api_client = AgentApiClient(base_url=API_BASE_URL)
        self.kakao_ui = KakaoUIAdapter()
        self.is_running = False
        self.tasks_to_send = []

        # UI Elements
        ttk.Label(self, text="카카오톡 자동 발송 에이전트", font=("Malgun Gothic", 16, "bold")).pack(pady=8)

        # Authentication Section
        auth_frame = ttk.LabelFrame(self, text="사용자 로그인 (인증)", padding=6)
        auth_frame.pack(pady=4, padx=10, fill=tk.X)

        ttk.Label(auth_frame, text="이메일:").grid(row=0, column=0, padx=4, pady=2, sticky=tk.W)
        self.email_entry = ttk.Entry(auth_frame, width=22)
        self.email_entry.grid(row=0, column=1, padx=4, pady=2, sticky=tk.W)

        ttk.Label(auth_frame, text="비밀번호:").grid(row=0, column=2, padx=4, pady=2, sticky=tk.W)
        self.password_entry = ttk.Entry(auth_frame, width=16, show="*")
        self.password_entry.grid(row=0, column=3, padx=4, pady=2, sticky=tk.W)

        self.login_btn = ttk.Button(auth_frame, text="로그인", command=self.handle_login)
        self.login_btn.grid(row=0, column=4, padx=6, pady=2)

        self.email_entry.bind("<Return>", lambda e: self.handle_login())
        self.password_entry.bind("<Return>", lambda e: self.handle_login())

        self.auth_status_var = tk.StringVar(value="인증 상태: 미로그인 (로그인이 필요합니다)")
        self.auth_status_label = ttk.Label(auth_frame, textvariable=self.auth_status_var, font=("Malgun Gothic", 9))
        self.auth_status_label.grid(row=1, column=0, columnspan=5, padx=4, pady=2, sticky=tk.W)

        # Status / Progress
        self.status_var = tk.StringVar(value="상태: 대기 중")
        ttk.Label(self, textvariable=self.status_var, font=("Malgun Gothic", 10)).pack(pady=2)

        self.progress_var = tk.StringVar(value="진행률: 0 / 0")
        ttk.Label(self, textvariable=self.progress_var, font=("Malgun Gothic", 10)).pack(pady=2)

        # Treeview for Queue
        columns = ("name", "contact", "status", "msg")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=7)
        self.tree.heading("name", text="고객명")
        self.tree.heading("contact", text="연락처")
        self.tree.heading("status", text="상태")
        self.tree.heading("msg", text="오류/비고")

        self.tree.column("name", width=80, anchor=tk.CENTER)
        self.tree.column("contact", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=70, anchor=tk.CENTER)
        self.tree.column("msg", width=300, anchor=tk.W)
        self.tree.pack(pady=4, padx=10, fill=tk.X)

        self.log_text = tk.Text(self, height=6, font=("Malgun Gothic", 9))
        self.log_text.pack(pady=4, padx=10, fill=tk.X)

        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(pady=8)

        self.load_btn = ttk.Button(self.btn_frame, text="대기열 불러오기", command=self.load_queue, state=tk.DISABLED)
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(self.btn_frame, text="발송 시작", command=self.start_sending, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(self.btn_frame, text="중지", command=self.stop_sending, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_btn = ttk.Button(self.btn_frame, text="발송 취소 (선택)", command=self.cancel_queue, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        # 프로토콜로 호출된 경우 창만 열고 안내
        if len(sys.argv) > 1 and sys.argv[1].startswith("cmhelper://"):
            self.log("웹에서 호출되었습니다. 로그인 후 대기열을 불러와주세요.")

    def handle_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        # Immediately clear password entry
        self.password_entry.delete(0, tk.END)

        if not email or not password:
            self.log("이메일과 비밀번호를 모두 입력해주세요.")
            return

        self.login_btn.config(state=tk.DISABLED)
        self.auth_status_var.set("인증 상태: 로그인 시도 중...")
        threading.Thread(target=self._run_login, args=(email, password), daemon=True).start()

    def _run_login(self, email, password):
        try:
            success = self.api_client.login(email, password)
            if success:
                self.auth_status_var.set("인증 상태: 로그인 완료")
                self.log("로그인 성공. [대기열 불러오기]를 눌러주세요.")
                self.load_btn.config(state=tk.NORMAL)
            else:
                self.auth_status_var.set("인증 상태: 로그인 실패")
                self.log("로그인 실패: 아이디 또는 비밀번호를 확인해주세요.")
        except AuthenticationError:
            self.auth_status_var.set("인증 상태: 로그인 실패 (인증 거부)")
            self.log("로그인 실패: 아이디/비밀번호를 확인하거나 관리자 승인 상태를 확인하세요.")
            self._handle_auth_invalidation("인증 거부")
        except Exception as e:
            self.auth_status_var.set("인증 상태: 로그인 오류")
            self.log(f"로그인 중 네트워크/서버 오류 발생: {e}")
            self._handle_auth_invalidation("네트워크 오류")
        finally:
            self.login_btn.config(state=tk.NORMAL)

    def _handle_auth_invalidation(self, reason="인증 만료"):
        self.api_client.clear_auth()
        self.auth_status_var.set("인증 상태: 미로그인 (재로그인 필요)")
        self.load_btn.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)
        self.is_running = False

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

    def copy_image_to_clipboard(self, image_data):
        """이미지 bytes를 파일 저장 없이 바로 클립보드로 복사"""
        image = Image.open(io.BytesIO(image_data))
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        image.close()
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
        if not self.api_client.is_authenticated():
            self.log("대기열을 불러오려면 먼저 로그인해야 합니다.")
            return
        self.log("서버에서 대기열을 가져옵니다...")
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self._fetch_tasks, daemon=True).start()

    def _fetch_tasks(self):
        try:
            self.tasks_to_send = self.api_client.get_pending_messages()
            total = len(self.tasks_to_send)
            if total == 0:
                self.log("발송 대기 중인 메시지가 없습니다.")
                self.progress_var.set("진행률: 0 / 0")
                self.start_btn.config(state=tk.DISABLED)
                self.cancel_btn.config(state=tk.DISABLED)
                return

            self.log(f"총 {total}건의 메시지를 불러왔습니다. [발송 시작]을 눌러주세요.")
            self.progress_var.set(f"진행률: 0 / {total}")

            for t in self.tasks_to_send:
                self.tree.insert("", "end", values=(t.get("customer_name"), t.get("customer_contact", ""), "대기", ""), tags=(str(t.get("id")),))

            self.start_btn.config(state=tk.NORMAL)
            self.cancel_btn.config(state=tk.NORMAL)
        except AuthenticationError:
            self.log("인증이 유효하지 않습니다. 다시 로그인해주세요.")
            self._handle_auth_invalidation("인증 만료")
        except Exception as e:
            self.log(f"대기열 불러오기 실패: {e}")

    def cancel_queue(self):
        """선택한 항목만 취소. 아무것도 선택 안 했으면 안내 메시지"""
        if self.is_running:
            self.log("발송 중에는 취소할 수 없습니다. 먼저 중지해주세요.")
            return
        if not self.api_client.is_authenticated():
            self.log("로그인이 필요합니다.")
            return

        selected_items = self.tree.selection()
        if not selected_items:
            self.log("취소할 항목을 먼저 클릭해서 선택해주세요. (Ctrl+클릭으로 여러 개 선택 가능)")
            return

        threading.Thread(target=self._run_cancel_selected, args=(selected_items,), daemon=True).start()

    def _run_cancel_selected(self, selected_items):
        try:
            self.log(f"선택된 {len(selected_items)}건을 취소하는 중...")
            cancelled_count = 0
            for item in selected_items:
                tags = self.tree.item(item, "tags")
                if tags:
                    task_id = tags[0]
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 오류로 취소 작업이 중단되었습니다. 재로그인이 필요합니다.")
                        self._handle_auth_invalidation("인증 만료")
                        return
                    except Exception as exc:
                        self.log(f"항목 {task_id} 취소 실패 (서버 오류): {exc}")
                        continue
                    # 서버 상태 업데이트 성공 시에만 화면 목록 및 대기열 목록에서 제거
                    self.tree.delete(item)
                    self.tasks_to_send = [t for t in self.tasks_to_send if str(t.get("id")) != task_id]
                    cancelled_count += 1

            total = len(self.tasks_to_send)
            self.log(f"취소 완료 ({cancelled_count}건 성공). 남은 대기 건수: {total}건")
            self.progress_var.set(f"진행률: 0 / {total}")
            if total == 0:
                self.start_btn.config(state=tk.DISABLED)
                self.cancel_btn.config(state=tk.DISABLED)
        except Exception as e:
            self.log(f"취소 실패: {e}")

    def start_sending(self):
        if self.is_running or not self.tasks_to_send:
            return
        if not self.api_client.is_authenticated():
            self.log("발송을 시작하려면 먼저 로그인해야 합니다.")
            return
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)
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
                if not self.api_client.is_authenticated():
                    self.log("인증 정보가 없습니다. 발송을 중단합니다.")
                    self._handle_auth_invalidation("인증 없음")
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
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                        self._handle_auth_invalidation("인증 만료")
                    except Exception:
                        pass
                    self.update_tree_status(task_id, "실패", err_msg)
                    self.is_running = False
                    break
                time.sleep(0.8)

                # 3. UIA 어댑터를 통한 카카오톡 채팅 탭 탐색, 검색, 1건 결과 진입 및 창 제목 검증
                nav_success = False
                chat_opened = False
                failure_reported = False
                try:
                    self.kakao_ui.open_chat_for_recipient(customer_name)
                    nav_success = True
                    chat_opened = True
                except KakaoWindowNotFoundError as e:
                    err_msg = f"카카오톡 창을 찾을 수 없습니다: {e}"
                    self.log(err_msg)
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                        self._handle_auth_invalidation("인증 만료")
                    except Exception:
                        pass
                    self.update_tree_status(task_id, "실패", err_msg)
                    failure_reported = True
                    self.is_running = False
                    break
                except KakaoTitleMismatchError as e:
                    err_msg = f"이름 불일치: {e}"
                    self.log(f"-> 발송 실패: {err_msg}")
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                        self._handle_auth_invalidation("인증 만료")
                        break
                    except Exception:
                        pass
                    self.update_tree_status(task_id, "실패", "이름 불일치 또는 미등록")
                    failure_reported = True
                    continue
                except (KakaoChatsNavigationError, KakaoSearchError, KakaoAmbiguousResultError, KakaoPopupBlockedError, KakaoUIError) as e:
                    err_msg = f"채팅방 탐색 실패: {e}"
                    self.log(f"-> 발송 실패: {err_msg}")
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                        self._handle_auth_invalidation("인증 만료")
                        break
                    except Exception:
                        pass
                    self.update_tree_status(task_id, "실패", str(e))
                    failure_reported = True
                    continue
                except Exception as e:
                    err_msg = f"예상치 못한 탐색 오류: {e}"
                    self.log(f"-> 발송 실패: {err_msg}")
                    try:
                        self.api_client.update_message_status(int(task_id), "failed")
                    except AuthenticationError:
                        self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                        self._handle_auth_invalidation("인증 만료")
                        break
                    except Exception:
                        pass
                    self.update_tree_status(task_id, "실패", err_msg)
                    failure_reported = True
                    continue
                finally:
                    # 모든 경로(정상 완료, 안전 실패, 취소, 예외)에서 임시 검색어 및 검색 상태 정리
                    try:
                        cleanup_ok = self.kakao_ui.cleanup_search()
                        if not cleanup_ok:
                            self.log("검색 상태 정리 실패")
                            nav_success = False
                    except Exception as clean_err:
                        self.log(f"검색 상태 정리 중 오류: {clean_err}")
                        nav_success = False

                if not nav_success:
                    if chat_opened:
                        pyautogui.press('esc')
                    if not failure_reported:
                        err_msg = "검색 상태 정리 실패"
                        self.log(f"-> 발송 실패: {err_msg}")
                        try:
                            self.api_client.update_message_status(int(task_id), "failed")
                        except AuthenticationError:
                            self.log("인증 만료로 상태 업데이트 실패 및 작업 중단")
                            self._handle_auth_invalidation("인증 만료")
                            break
                        except Exception:
                            pass
                        self.update_tree_status(task_id, "실패", err_msg)
                    continue

                # 7. 이미지 먼저 첨부 및 발송 (이미지 팝업이 텍스트 발송을 막는 현상 수정)
                if img_url:
                    try:
                        img_bytes = self.api_client.download_image(img_url)
                        self.copy_image_to_clipboard(img_bytes)
                        time.sleep(0.5)
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.8)
                        pyautogui.press('enter') # 이미지 팝업 승인 또는 발송
                        time.sleep(1.0)
                    except Exception as e:
                        self.log(f"이미지 첨부 실패: {e}")

                # 8. 텍스트 붙여넣기 및 발송
                pyperclip.copy(msg_text)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.5)

                # 9. 최종 엔터 (텍스트 발송)
                pyautogui.press('enter')
                time.sleep(0.5)

                # 10. ESC 눌러서 채팅방 닫기
                pyautogui.press('esc')

                # 11. 서버 상태 업데이트 (서버 성공 확인 시에만 로컬 UI 성공 반영)
                server_update_success = False
                try:
                    self.api_client.update_message_status(int(task_id), "sent")
                    server_update_success = True
                except AuthenticationError:
                    self.log("인증 만료로 서버 상태 업데이트 실패. 작업을 중단합니다.")
                    self.update_tree_status(task_id, "실패", "인증 만료")
                    self._handle_auth_invalidation("인증 만료")
                    break
                except Exception as e:
                    self.log(f"서버 상태 업데이트 실패: {e}")
                    self.update_tree_status(task_id, "실패", "서버 상태 업데이트 실패")

                if server_update_success:
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
        if self.api_client.is_authenticated():
            self.load_btn.config(state=tk.NORMAL)
            if self.tasks_to_send:
                self.cancel_btn.config(state=tk.NORMAL)
        else:
            self.load_btn.config(state=tk.DISABLED)
            self.cancel_btn.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("상태: 대기 중")
        self.tasks_to_send = []

if __name__ == "__main__":
    is_first, server_socket = check_single_instance()
    if not is_first:
        sys.exit(0)
    register_protocol()
    app = CMHelperAgent()
    app.mainloop()
