"""CMhelper PC Agent - KakaoTalk UIA Navigation & Automation Adapter

This module provides a narrow, robust, testable UIA-only adapter for KakaoTalk desktop:
- Activates KakaoTalk main window via UIAutomation (pywinauto).
- Identifies and selects ONLY the Chats ("채팅") navigation tab.
- Explicitly rejects Friends ("친구"), Add Friend ("친구추가"), new-chat controls,
  coordinate clicking, image-location automation, Ctrl+2, and Friends-search fallback.
- Identifies and activates chat-list search edit control, sets recipient name.
- Opens EXACTLY ONE matching existing chat result (fails closed on 0 or >1 results).
- Positively validates foreground conversation window title matches recipient name.
- Provides an idempotent cleanup method to clear transient search text and dismiss
  search results without modifying or deleting KakaoTalk user data.
- Bounded constants: 5.0s element timeout, 3 retries, 0.5s interval.
"""
import time
import sys

try:
    from pywinauto import Desktop, Application
    from pywinauto.controls.uiawrapper import UIAWrapper
except ImportError:
    Desktop = None
    Application = None
    UIAWrapper = None

try:
    import win32gui
except ImportError:
    win32gui = None


# Explicit Bounded Constants
DEFAULT_TIMEOUT_SEC = 5.0
MAX_RETRIES = 3
RETRY_INTERVAL_SEC = 0.5

# Allowed accessible names for Chats navigation tab
CHATS_TAB_NAMES = ("채팅", "Chats", "채팅 탭", "채팅 목록", "채팅방")

# Prohibited accessible names that must NEVER be selected or navigated to
PROHIBITED_TAB_NAMES = (
    "친구", "Friends", "친구 탭", "친구목록", "친구 목록",
    "친구 추가", "친구추가", "Add Friend", "Add Friends",
    "새로운 채팅", "새로운채팅", "새 채팅", "New Chat",
    "오픈채팅", "오픈 채팅", "Open Chat",
    "더보기", "More", "설정", "Settings",
)

# Search control accessible names
SEARCH_CONTROL_NAMES = ("검색", "Search", "채팅방 검색", "채팅 검색")
PROHIBITED_SEARCH_NAMES = ("친구 검색", "친구추가 검색", "Search Friends")


class KakaoUIError(Exception):
    """Base exception for Kakao UIA automation errors."""
    pass


class KakaoWindowNotFoundError(KakaoUIError):
    """KakaoTalk main window not found or cannot be activated."""
    pass


class KakaoChatsNavigationError(KakaoUIError):
    """Failed to select or verify Chats navigation control."""
    pass


class KakaoSearchError(KakaoUIError):
    """Failed to locate search control or perform search."""
    pass


class KakaoAmbiguousResultError(KakaoUIError):
    """Search returned 0 or multiple matching chat results."""
    pass


class KakaoTitleMismatchError(KakaoUIError):
    """Foreground conversation window title does not match recipient name."""
    pass


class KakaoPopupBlockedError(KakaoUIError):
    """Blocked by unexpected popup or modal dialog."""
    pass


class KakaoCleanupError(KakaoUIError):
    """Error during transient search cleanup."""
    pass


def _get_element_name(elem) -> str:
    """Extract accessible name / window text from an element or fake wrapper."""
    if hasattr(elem, "element_info") and hasattr(elem.element_info, "name") and elem.element_info.name:
        return str(elem.element_info.name).strip()
    if hasattr(elem, "window_text") and callable(elem.window_text):
        try:
            txt = elem.window_text()
            if txt:
                return str(txt).strip()
        except Exception:
            pass
    if hasattr(elem, "texts") and callable(elem.texts):
        try:
            txts = elem.texts()
            if txts and txts[0]:
                return str(txts[0]).strip()
        except Exception:
            pass
    if hasattr(elem, "name") and elem.name:
        return str(elem.name).strip()
    return ""


def _get_control_type(elem) -> str:
    """Extract control type from an element or fake wrapper."""
    if hasattr(elem, "element_info") and hasattr(elem.element_info, "control_type") and elem.element_info.control_type:
        return str(elem.element_info.control_type)
    if hasattr(elem, "friendly_class_name") and callable(elem.friendly_class_name):
        try:
            return str(elem.friendly_class_name())
        except Exception:
            pass
    if hasattr(elem, "control_type") and elem.control_type:
        return str(elem.control_type)
    return ""


def _is_element_selected(elem) -> bool:
    """Check if element is currently selected / active."""
    if hasattr(elem, "is_selected") and callable(elem.is_selected):
        try:
            return bool(elem.is_selected())
        except Exception:
            pass
    if hasattr(elem, "get_toggle_state") and callable(elem.get_toggle_state):
        try:
            return elem.get_toggle_state() == 1
        except Exception:
            pass
    if hasattr(elem, "is_selected") and isinstance(elem.is_selected, bool):
        return elem.is_selected
    if hasattr(elem, "selected"):
        return bool(elem.selected)
    if hasattr(elem, "is_active"):
        return bool(elem.is_active)
    return False


class KakaoUIAdapter:
    """UIA-only adapter for KakaoTalk navigation, chat search, result opening,
    title validation, and transient-search cleanup.
    
    Adheres strictly to fail-closed behavior, bounded timeouts and retries,
    chats-only navigation (prohibiting Friends/Add Friend/new chat),
    and idempotent cleanup across all execution paths.
    """

    DEFAULT_TIMEOUT_SEC = DEFAULT_TIMEOUT_SEC
    MAX_RETRIES = MAX_RETRIES
    RETRY_INTERVAL_SEC = RETRY_INTERVAL_SEC
    CHATS_TAB_NAMES = CHATS_TAB_NAMES
    PROHIBITED_TAB_NAMES = PROHIBITED_TAB_NAMES
    SEARCH_CONTROL_NAMES = SEARCH_CONTROL_NAMES
    PROHIBITED_SEARCH_NAMES = PROHIBITED_SEARCH_NAMES

    def __init__(
        self,
        element_timeout: float = DEFAULT_TIMEOUT_SEC,
        max_retries: int = MAX_RETRIES,
        retry_interval: float = RETRY_INTERVAL_SEC,
        backend: str = "uia",
        desktop=None,
        app=None,
    ):
        self.element_timeout = element_timeout
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.backend = backend
        self._desktop = desktop
        self._app = app
        self._main_window = None
        self._search_edit = None

    def get_main_window(self):
        """Find and activate KakaoTalk main window via UIA within bounded timeout."""
        if self._main_window is not None:
            return self._main_window

        for attempt in range(1, self.max_retries + 1):
            try:
                if self._desktop is not None:
                    desktop = self._desktop
                elif Desktop is not None:
                    desktop = Desktop(backend=self.backend)
                else:
                    raise KakaoWindowNotFoundError("pywinauto Desktop이 초기화되지 않았습니다.")

                windows = []
                if hasattr(desktop, "windows") and callable(desktop.windows):
                    for w in desktop.windows():
                        w_title = _get_element_name(w)
                        # A locked KakaoTalk window is still a KakaoTalk process
                        # state.  Keep it as a candidate so the explicit lock
                        # guard below can fail closed with the correct reason,
                        # rather than misreporting it as a missing main window.
                        if (
                            w_title in ("카카오톡", "KakaoTalk")
                            or "카카오톡" in w_title and "잠금" in w_title
                            or "KakaoTalk" in w_title and "Lock" in w_title
                        ):
                            windows.append(w)

                if not windows:
                    if attempt < self.max_retries:
                        time.sleep(self.retry_interval)
                        continue
                    raise KakaoWindowNotFoundError("카카오톡 메인 창을 찾을 수 없습니다.")

                win = windows[0]
                w_title = _get_element_name(win)
                if "잠금" in w_title or "Lock" in w_title:
                    raise KakaoPopupBlockedError("카카오톡이 잠금 모드 상태입니다.")

                # Focus and restore if needed
                if hasattr(win, "set_focus") and callable(win.set_focus):
                    try:
                        win.set_focus()
                    except Exception:
                        pass
                if hasattr(win, "restore") and callable(win.restore):
                    try:
                        win.restore()
                    except Exception:
                        pass

                return win
            except (KakaoWindowNotFoundError, KakaoPopupBlockedError):
                raise
            except Exception as e:
                if attempt >= self.max_retries:
                    raise KakaoWindowNotFoundError(f"카카오톡 창 활성화 실패: {e}")
                time.sleep(self.retry_interval)

        raise KakaoWindowNotFoundError("카카오톡 창을 찾을 수 없습니다 (타임아웃).")

    def select_chats_tab(self, main_window=None):
        """Identify and select ONLY the Chats navigation control.
        
        Positively verifies Chats state before returning.
        Explicitly rejects Friends, Add Friend, and new chat controls.
        """
        win = main_window or self.get_main_window()

        for attempt in range(1, self.max_retries + 1):
            descendants = []
            if hasattr(win, "descendants") and callable(win.descendants):
                try:
                    descendants = win.descendants()
                except Exception:
                    descendants = []
            elif hasattr(win, "children") and callable(win.children):
                try:
                    descendants = win.children()
                except Exception:
                    descendants = []

            chats_control = None
            for elem in descendants:
                name = _get_element_name(elem)
                # Check prohibited controls
                if any(p == name or (len(p) > 2 and p in name) for p in self.PROHIBITED_TAB_NAMES):
                    continue

                if name in self.CHATS_TAB_NAMES or any(name == c for c in self.CHATS_TAB_NAMES):
                    chats_control = elem
                    break

            if chats_control is None:
                if attempt < self.max_retries:
                    time.sleep(self.retry_interval)
                    continue
                raise KakaoChatsNavigationError("채팅 탭 컨트롤을 찾을 수 없습니다.")

            # Double-check prohibited guard on chosen control
            chosen_name = _get_element_name(chats_control)
            if any(p == chosen_name or (len(p) > 2 and p in chosen_name) for p in self.PROHIBITED_TAB_NAMES):
                raise KakaoChatsNavigationError(f"허용되지 않은 탭('{chosen_name}')이 감지되어 선택을 중단합니다.")

            # Select / Invoke Chats tab
            try:
                if hasattr(chats_control, "select") and callable(chats_control.select):
                    chats_control.select()
                elif hasattr(chats_control, "click_input") and callable(chats_control.click_input):
                    chats_control.click_input()
                elif hasattr(chats_control, "invoke") and callable(chats_control.invoke):
                    chats_control.invoke()
                elif hasattr(chats_control, "click") and callable(chats_control.click):
                    chats_control.click()
            except Exception as e:
                if attempt >= self.max_retries:
                    raise KakaoChatsNavigationError(f"채팅 탭 선택 실패: {e}")
                time.sleep(self.retry_interval)
                continue

            time.sleep(0.1)
            if self._verify_chats_state(chats_control, win):
                return chats_control

            if attempt < self.max_retries:
                time.sleep(self.retry_interval)

        raise KakaoChatsNavigationError("채팅 탭 활성화 상태 검증 실패 (타임아웃).")

    def _verify_chats_state(self, chats_control, win=None) -> bool:
        """Positively verify that Chats tab/view is active and selected."""
        if _is_element_selected(chats_control):
            return True

        if getattr(chats_control, "is_active", False) or getattr(chats_control, "selected", False):
            return True

        if hasattr(chats_control, "get_toggle_state") and callable(chats_control.get_toggle_state):
            try:
                if chats_control.get_toggle_state() == 1:
                    return True
            except Exception:
                pass

        if win is not None:
            try:
                edit = self._find_search_control(win, silent=True)
                if edit is not None:
                    return True
            except Exception:
                pass

        return False

    def _find_search_control(self, win, silent=False):
        """Find the chat-list search edit control."""
        descendants = []
        if hasattr(win, "descendants") and callable(win.descendants):
            try:
                descendants = win.descendants()
            except Exception:
                descendants = []
        elif hasattr(win, "children") and callable(win.children):
            try:
                descendants = win.children()
            except Exception:
                descendants = []

        for elem in descendants:
            name = _get_element_name(elem)
            ctype = _get_control_type(elem)

            # Reject prohibited search controls
            if any(p in name for p in self.PROHIBITED_SEARCH_NAMES):
                continue

            # Identify Edit control or search name
            if ctype in ("Edit", "EditControl", "ControlType.Edit") or name in self.SEARCH_CONTROL_NAMES or "검색" in name:
                if "친구" not in name and "Add" not in name:
                    return elem

        if not silent:
            raise KakaoSearchError("채팅 검색창 컨트롤을 찾을 수 없습니다.")
        return None

    def search_chat(self, recipient_name: str, main_window=None):
        """Identify chat-list search edit control, set intended name, and trigger search."""
        if not recipient_name or not recipient_name.strip():
            raise KakaoSearchError("검색 대상 이름이 비어있습니다.")

        target_name = recipient_name.strip()
        win = main_window or self.get_main_window()

        for attempt in range(1, self.max_retries + 1):
            edit = self._find_search_control(win, silent=(attempt < self.max_retries))
            if edit is None:
                time.sleep(self.retry_interval)
                continue

            self._search_edit = edit
            try:
                if hasattr(edit, "set_edit_text") and callable(edit.set_edit_text):
                    edit.set_edit_text(target_name)
                elif hasattr(edit, "set_text") and callable(edit.set_text):
                    edit.set_text(target_name)
                elif hasattr(edit, "type_keys") and callable(edit.type_keys):
                    if hasattr(edit, "set_focus") and callable(edit.set_focus):
                        edit.set_focus()
                    edit.type_keys(target_name, with_spaces=True)
                elif hasattr(edit, "set_value") and callable(edit.set_value):
                    edit.set_value(target_name)
                else:
                    setattr(edit, "text", target_name)

                time.sleep(0.2)
                return edit
            except Exception as e:
                if attempt >= self.max_retries:
                    raise KakaoSearchError(f"검색어 입력 실패: {e}")
                time.sleep(self.retry_interval)

        raise KakaoSearchError("채팅 검색창에 검색어를 입력할 수 없습니다 (타임아웃).")

    def _get_chat_search_results(self, win, target_name: str) -> list:
        """Find and return list of matching chat items from search results."""
        descendants = []
        if hasattr(win, "descendants") and callable(win.descendants):
            try:
                descendants = win.descendants()
            except Exception:
                descendants = []
        elif hasattr(win, "children") and callable(win.children):
            try:
                descendants = win.children()
            except Exception:
                descendants = []

        matching_items = []
        for elem in descendants:
            name = _get_element_name(elem)
            ctype = _get_control_type(elem)

            if name in self.CHATS_TAB_NAMES or any(name == p for p in self.PROHIBITED_TAB_NAMES):
                continue
            if ctype in ("Edit", "EditControl", "ControlType.Edit", "Button", "ScrollBar"):
                continue

            # Matching chat item logic
            if name == target_name or target_name == name.strip():
                if "친구 찾기" not in name and "새로운 친구" not in name and "친구추가" not in name:
                    matching_items.append(elem)

        return matching_items

    def _check_for_popups(self, win=None):
        """Check if any blocking popups or modal dialogs are present."""
        if self._desktop is not None:
            desktop = self._desktop
        elif Desktop is not None:
            try:
                desktop = Desktop(backend=self.backend)
            except Exception:
                return
        else:
            return

        if hasattr(desktop, "windows") and callable(desktop.windows):
            try:
                for w in desktop.windows():
                    title = _get_element_name(w)
                    if any(p in title for p in ("친구 추가", "친구추가", "새로운 대화", "알림", "경고", "오류", "Error")):
                        raise KakaoPopupBlockedError(f"예상치 못한 팝업 감지: '{title}'")
            except KakaoPopupBlockedError:
                raise
            except Exception:
                pass

    def open_matching_chat_result(self, expected_name: str, main_window=None):
        """Ensure exactly one existing chat result matches expected_name, and open it.
        
        Fails closed on 0 results, >1 results, unexpected popups, or mismatch.
        """
        win = main_window or self.get_main_window()
        target_name = expected_name.strip()

        # Check for blocking popups first
        self._check_for_popups(win)

        for attempt in range(1, self.max_retries + 1):
            results = self._get_chat_search_results(win, target_name)

            if len(results) == 0:
                if attempt < self.max_retries:
                    time.sleep(self.retry_interval)
                    continue
                raise KakaoAmbiguousResultError(f"검색 결과 없음: '{target_name}'에 일치하는 채팅방이 없습니다.")

            if len(results) > 1:
                raise KakaoAmbiguousResultError(
                    f"검색 결과 모호: '{target_name}'에 일치하는 채팅방이 {len(results)}개 발견되었습니다 (동명이인 또는 중복)."
                )

            # Exactly one result!
            matched_item = results[0]
            try:
                if hasattr(matched_item, "double_click_input") and callable(matched_item.double_click_input):
                    matched_item.double_click_input()
                elif hasattr(matched_item, "invoke") and callable(matched_item.invoke):
                    matched_item.invoke()
                elif hasattr(matched_item, "click_input") and callable(matched_item.click_input):
                    matched_item.click_input()
                elif hasattr(matched_item, "open") and callable(matched_item.open):
                    matched_item.open()
                elif hasattr(matched_item, "click") and callable(matched_item.click):
                    matched_item.click()

                time.sleep(0.3)
                return matched_item
            except Exception as e:
                if attempt >= self.max_retries:
                    raise KakaoUIError(f"채팅방 열기 실패: {e}")
                time.sleep(self.retry_interval)

        raise KakaoAmbiguousResultError(f"채팅방 검색 결과 열기 실패: {target_name}")

    def verify_conversation_title(self, expected_name: str, timeout_sec: float = None) -> bool:
        """Validate that the active foreground conversation window title matches expected_name.
        
        Fails closed if title mismatches, window is absent, or popup is detected.
        """
        timeout = timeout_sec or self.element_timeout
        target_name = expected_name.strip()
        start_time = time.time()

        while time.time() - start_time <= timeout:
            self._check_for_popups()

            foreground_title = self._get_foreground_window_title()
            if foreground_title:
                if foreground_title.strip() == target_name:
                    return True
                if foreground_title.strip() not in ("카카오톡", "KakaoTalk", ""):
                    raise KakaoTitleMismatchError(
                        f"이름 불일치 (기대: '{target_name}', 실제: '{foreground_title.strip()}')"
                    )

            time.sleep(self.retry_interval)

        foreground_title = self._get_foreground_window_title()
        if foreground_title and foreground_title.strip() == target_name:
            return True

        raise KakaoTitleMismatchError(
            f"채팅방 제목 확인 실패 또는 불일치 (기대: '{target_name}', 실제: '{foreground_title}')"
        )

    def _get_foreground_window_title(self) -> str:
        """Get title of current foreground window."""
        if self._desktop is not None and hasattr(self._desktop, "get_foreground_title"):
            return str(self._desktop.get_foreground_title()).strip()

        if win32gui is not None:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    return win32gui.GetWindowText(hwnd).strip()
            except Exception:
                pass
        return ""

    def cleanup_search(self, main_window=None) -> bool:
        """Idempotently clear transient chat-list search text and dismiss search-result state.
        
        Safe across all execution paths (normal completion, failure, cancellation, exception).
        Never deletes KakaoTalk user data.
        """
        try:
            win = main_window or self._main_window
            if win is None:
                try:
                    win = self.get_main_window()
                except Exception:
                    win = None

            if win is not None:
                edit = self._search_edit or self._find_search_control(win, silent=True)
                if edit is not None:
                    try:
                        if hasattr(edit, "set_edit_text") and callable(edit.set_edit_text):
                            edit.set_edit_text("")
                        elif hasattr(edit, "set_text") and callable(edit.set_text):
                            edit.set_text("")
                        elif hasattr(edit, "set_value") and callable(edit.set_value):
                            edit.set_value("")
                        else:
                            setattr(edit, "text", "")
                    except Exception:
                        pass

                try:
                    if hasattr(win, "type_keys") and callable(win.type_keys):
                        win.type_keys("{ESC}")
                except Exception:
                    pass

            self._search_edit = None
            return True
        except Exception:
            return False

    def open_chat_for_recipient(self, recipient_name: str) -> bool:
        """High-level orchestration:
        1. Activate KakaoTalk main window via UIA.
        2. Select and verify Chats navigation tab (rejecting Friends/Add Friend).
        3. Identify search edit and enter recipient name.
        4. Verify exactly one matching chat result and open it.
        5. Verify foreground conversation window title matches recipient name.
        """
        if not recipient_name or not recipient_name.strip():
            raise KakaoSearchError("수신자 이름이 유효하지 않습니다.")

        win = self.get_main_window()
        self.select_chats_tab(win)
        self.search_chat(recipient_name, win)
        self.open_matching_chat_result(recipient_name, win)
        self.verify_conversation_title(recipient_name)
        return True

    # Alias for compatibility
    navigate_and_open_chat = open_chat_for_recipient
