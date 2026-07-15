import codecs

with codecs.open('CMhelper_agent/agent.py', 'r', 'utf-8') as f:
    content = f.read()

# 1. Add single instance socket logic
socket_logic = """
import socket

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
        import threading
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
"""

content = content.replace('import winreg\r\n', 'import winreg\r\nimport socket\r\n')

main_block_old = """if __name__ == "__main__":
    register_protocol()
    app = CMHelperAgent()
    app.mainloop()"""

main_block_new = """if __name__ == "__main__":
    is_first, server_socket = check_single_instance()
    if not is_first:
        import sys
        sys.exit(0)
    register_protocol()
    app = CMHelperAgent()
    app.after(500, app.load_queue)
    app.mainloop()"""

content = content.replace(main_block_old, main_block_new)
content = content.replace('import socket\r\n', socket_logic)


# 2. Modify Ctrl+F logic to add Ctrl+2
search_logic_old = """                # Ctrl+F 로 검색창 이동
                pyautogui.hotkey('ctrl', 'f')"""

search_logic_new = """                # Ctrl+2 로 채팅 목록 탭 이동 (친구 추가 버튼 방지)
                pyautogui.hotkey('ctrl', '2')
                time.sleep(0.5)
                
                # Ctrl+F 로 검색창 이동
                pyautogui.hotkey('ctrl', 'f')"""

content = content.replace(search_logic_old, search_logic_new)

# 3. Modify cancel_queue to delete selected items only
cancel_old = """    def cancel_queue(self):
        if self.is_running:
            self.log("발송 중에는 취소할 수 없습니다. 먼저 중지해주세요.")
            return
        threading.Thread(target=self._run_cancel, daemon=True).start()

    def _run_cancel(self):
        try:
            self.log("대기열을 취소하는 중...")
            res = requests.delete(f"{API_BASE_URL}/messages/pending")
            if res.status_code == 200:
                self.log("대기열이 성공적으로 취소/비워졌습니다.")
                self.tasks_to_send = []
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.progress_var.set("진행률: 0 / 0")
                self.start_btn.config(state=tk.DISABLED)
            else:
                self.log(f"취소 실패: HTTP {res.status_code}")
        except Exception as e:
            self.log(f"취소 실패: {e}")"""

cancel_new = """    def cancel_queue(self):
        selected_items = self.tree.selection()
        if not selected_items:
            self.log("취소할 항목을 먼저 선택해주세요.")
            return
            
        if self.is_running:
            self.log("발송 중에는 취소할 수 없습니다. 먼저 중지해주세요.")
            return
        threading.Thread(target=self._run_cancel_selected, args=(selected_items,), daemon=True).start()

    def _run_cancel_selected(self, selected_items):
        try:
            self.log("선택된 대기열을 취소하는 중...")
            for item in selected_items:
                tags = self.tree.item(item, "tags")
                if tags:
                    task_id = tags[0]
                    requests.put(f"{API_BASE_URL}/messages/{task_id}/status", json={"status": "failed"})
                    self.tree.delete(item)
                    self.tasks_to_send = [t for t in self.tasks_to_send if str(t.get("id")) != task_id]
            self.log("선택된 항목이 취소되었습니다.")
            
            total = len(self.tasks_to_send)
            self.progress_var.set(f"진행률: 0 / {total}")
            if total == 0:
                self.start_btn.config(state=tk.DISABLED)
        except Exception as e:
            self.log(f"취소 실패: {e}")"""

content = content.replace(cancel_old, cancel_new)

with codecs.open('CMhelper_agent/agent.py', 'w', 'utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
