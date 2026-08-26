"""CMhelper PC Agent - KakaoTalk UIA Navigation & Fail-Closed Unit Tests

Uses exclusively synthetic/fake UI objects (pure Python test doubles, no actual UIAutomation
or KakaoTalk process required).

Covers:
1. Chats tab selection and state verification.
2. Positive rejection of Friends, Add Friend, and new chat controls.
3. Missing / ambiguous controls handling.
4. Bounded timeout and retry limits.
5. Exactly-one existing-chat matching (0 results and >1 results fail closed).
6. Foreground conversation title validation and mismatch fail-closed.
7. Blocking popup and lock-mode detection and fail-closed.
8. Idempotent cleanup of transient search text across all paths without deleting Kakao data.
9. Proof that no send action occurs after navigation or validation failure.
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure CMhelper_agent is in sys.path
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

from kakao_ui import (
    KakaoUIAdapter,
    KakaoUIError,
    KakaoWindowNotFoundError,
    KakaoChatsNavigationError,
    KakaoSearchError,
    KakaoAmbiguousResultError,
    KakaoTitleMismatchError,
    KakaoPopupBlockedError,
    DEFAULT_TIMEOUT_SEC,
    MAX_RETRIES,
)


class FakeElementInfo:
    def __init__(self, name="", control_type=""):
        self.name = name
        self.control_type = control_type


class FakeUIElement:
    def __init__(self, name="", control_type="", is_selected=False, children=None):
        self.element_info = FakeElementInfo(name=name, control_type=control_type)
        self.name = name
        self.control_type = control_type
        self._is_selected = is_selected
        self._children = children or []
        self.text = ""
        self.click_count = 0
        self.select_count = 0
        self.double_click_count = 0
        self.invoke_count = 0
        self.keys_typed = []

    def window_text(self):
        return self.name

    def texts(self):
        return [self.name]

    def is_selected(self):
        return self._is_selected

    def select(self):
        self.select_count += 1
        self._is_selected = True

    def click(self):
        self.click_count += 1

    def click_input(self):
        self.click_count += 1

    def double_click_input(self):
        self.double_click_count += 1

    def invoke(self):
        self.invoke_count += 1

    def set_edit_text(self, text):
        self.text = text

    def set_text(self, text):
        self.text = text

    def type_keys(self, keys, **kwargs):
        self.keys_typed.append(keys)

    def descendants(self):
        result = []
        for c in self._children:
            result.append(c)
            if hasattr(c, "descendants"):
                result.extend(c.descendants())
        return result

    def children(self):
        return list(self._children)


class FakeDesktop:
    def __init__(self, windows=None, foreground_title=""):
        self._windows = windows or []
        self._foreground_title = foreground_title

    def windows(self):
        return list(self._windows)

    def get_foreground_title(self):
        return self._foreground_title


class TestKakaoUIAdapterChatsSelection(unittest.TestCase):
    def setUp(self):
        self.chats_tab = FakeUIElement(name="채팅", control_type="TabItem", is_selected=False)
        self.search_edit = FakeUIElement(name="검색", control_type="Edit")
        self.main_win = FakeUIElement(
            name="카카오톡",
            control_type="Window",
            children=[self.chats_tab, self.search_edit],
        )
        self.desktop = FakeDesktop(windows=[self.main_win], foreground_title="홍길동")
        self.adapter = KakaoUIAdapter(
            element_timeout=1.0,
            max_retries=2,
            retry_interval=0.01,
            desktop=self.desktop,
        )

    def test_chats_tab_selection_success(self):
        selected = self.adapter.select_chats_tab(self.main_win)
        self.assertEqual(selected.name, "채팅")
        self.assertTrue(self.chats_tab.is_selected())
        self.assertGreaterEqual(self.chats_tab.select_count + self.chats_tab.click_count, 1)

    def test_chats_tab_english_chats_name(self):
        chats_en = FakeUIElement(name="Chats", control_type="TabItem", is_selected=False)
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[chats_en, self.search_edit])
        selected = self.adapter.select_chats_tab(win)
        self.assertEqual(selected.name, "Chats")
        self.assertTrue(chats_en.is_selected())

    def test_rejection_of_friends_tab(self):
        friends_tab = FakeUIElement(name="친구", control_type="TabItem", is_selected=False)
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[friends_tab, self.search_edit])
        with self.assertRaises(KakaoChatsNavigationError):
            self.adapter.select_chats_tab(win)
        self.assertFalse(friends_tab.is_selected())
        self.assertEqual(friends_tab.select_count, 0)

    def test_rejection_of_add_friend_control(self):
        add_friend_btn = FakeUIElement(name="친구 추가", control_type="Button")
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[add_friend_btn, self.search_edit])
        with self.assertRaises(KakaoChatsNavigationError):
            self.adapter.select_chats_tab(win)
        self.assertEqual(add_friend_btn.click_count, 0)

    def test_prohibited_new_chat_rejected(self):
        new_chat_btn = FakeUIElement(name="새로운 채팅", control_type="Button")
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[new_chat_btn, self.search_edit])
        with self.assertRaises(KakaoChatsNavigationError):
            self.adapter.select_chats_tab(win)


class TestKakaoUIAdapterSearchAndResults(unittest.TestCase):
    def setUp(self):
        self.chats_tab = FakeUIElement(name="채팅", control_type="TabItem", is_selected=True)
        self.search_edit = FakeUIElement(name="검색", control_type="Edit")
        self.chat_item1 = FakeUIElement(name="홍길동", control_type="ListItem")
        self.main_win = FakeUIElement(
            name="카카오톡",
            control_type="Window",
            children=[self.chats_tab, self.search_edit, self.chat_item1],
        )
        self.desktop = FakeDesktop(windows=[self.main_win], foreground_title="홍길동")
        self.adapter = KakaoUIAdapter(
            element_timeout=1.0,
            max_retries=2,
            retry_interval=0.01,
            desktop=self.desktop,
        )

    def test_search_chat_sets_recipient_name(self):
        edit = self.adapter.search_chat("홍길동", self.main_win)
        self.assertEqual(edit.text, "홍길동")
        self.assertEqual(self.adapter._search_edit, edit)

    def test_search_chat_empty_name_raises(self):
        with self.assertRaises(KakaoSearchError):
            self.adapter.search_chat("", self.main_win)
        with self.assertRaises(KakaoSearchError):
            self.adapter.search_chat("   ", self.main_win)

    def test_missing_search_control_raises(self):
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[self.chats_tab])
        with self.assertRaises(KakaoSearchError):
            self.adapter.search_chat("홍길동", win)

    def test_exactly_one_matching_result_opens_chat(self):
        opened = self.adapter.open_matching_chat_result("홍길동", self.main_win)
        self.assertEqual(opened.name, "홍길동")
        self.assertGreaterEqual(
            opened.double_click_count + opened.invoke_count + opened.click_count, 1
        )

    def test_zero_results_fails_closed(self):
        win = FakeUIElement(name="카카오톡", control_type="Window", children=[self.chats_tab, self.search_edit])
        with self.assertRaises(KakaoAmbiguousResultError):
            self.adapter.open_matching_chat_result("존재하지않는고객", win)

    def test_multiple_results_ambiguous_fails_closed(self):
        chat_item2 = FakeUIElement(name="홍길동", control_type="ListItem")
        win = FakeUIElement(
            name="카카오톡",
            control_type="Window",
            children=[self.chats_tab, self.search_edit, self.chat_item1, chat_item2],
        )
        with self.assertRaises(KakaoAmbiguousResultError):
            self.adapter.open_matching_chat_result("홍길동", win)


class TestKakaoUIAdapterTitleValidationAndPopups(unittest.TestCase):
    def setUp(self):
        self.chats_tab = FakeUIElement(name="채팅", control_type="TabItem", is_selected=True)
        self.search_edit = FakeUIElement(name="검색", control_type="Edit")
        self.main_win = FakeUIElement(
            name="카카오톡",
            control_type="Window",
            children=[self.chats_tab, self.search_edit],
        )

    def test_title_match_succeeds(self):
        desktop = FakeDesktop(windows=[self.main_win], foreground_title="홍길동")
        adapter = KakaoUIAdapter(
            element_timeout=0.2,
            max_retries=2,
            retry_interval=0.01,
            desktop=desktop,
        )
        self.assertTrue(adapter.verify_conversation_title("홍길동"))

    def test_title_mismatch_fails_closed(self):
        desktop = FakeDesktop(windows=[self.main_win], foreground_title="엉뚱한사람")
        adapter = KakaoUIAdapter(
            element_timeout=0.2,
            max_retries=2,
            retry_interval=0.01,
            desktop=desktop,
        )
        with self.assertRaises(KakaoTitleMismatchError):
            adapter.verify_conversation_title("홍길동")

    def test_blocking_popup_fails_closed(self):
        popup_win = FakeUIElement(name="친구 추가", control_type="Window")
        desktop = FakeDesktop(windows=[self.main_win, popup_win], foreground_title="친구 추가")
        adapter = KakaoUIAdapter(
            element_timeout=0.2,
            max_retries=2,
            retry_interval=0.01,
            desktop=desktop,
        )
        with self.assertRaises(KakaoPopupBlockedError):
            adapter.open_matching_chat_result("홍길동", self.main_win)

    def test_lock_mode_fails_closed(self):
        lock_win = FakeUIElement(name="카카오톡 잠금 모드", control_type="Window")
        desktop = FakeDesktop(windows=[lock_win], foreground_title="카카오톡 잠금 모드")
        adapter = KakaoUIAdapter(
            element_timeout=0.2,
            max_retries=2,
            retry_interval=0.01,
            desktop=desktop,
        )
        with self.assertRaises(KakaoPopupBlockedError):
            adapter.get_main_window()


class TestKakaoUIAdapterCleanupAndOrchestration(unittest.TestCase):
    def setUp(self):
        self.chats_tab = FakeUIElement(name="채팅", control_type="TabItem", is_selected=True)
        self.search_edit = FakeUIElement(name="검색", control_type="Edit")
        self.chat_item = FakeUIElement(name="홍길동", control_type="ListItem")
        self.main_win = FakeUIElement(
            name="카카오톡",
            control_type="Window",
            children=[self.chats_tab, self.search_edit, self.chat_item],
        )
        self.desktop = FakeDesktop(windows=[self.main_win], foreground_title="홍길동")
        self.adapter = KakaoUIAdapter(
            element_timeout=0.5,
            max_retries=2,
            retry_interval=0.01,
            desktop=self.desktop,
        )

    def test_cleanup_clears_search_edit_and_sends_esc(self):
        self.search_edit.set_edit_text("홍길동")
        self.adapter._search_edit = self.search_edit
        self.assertEqual(self.search_edit.text, "홍길동")

        success = self.adapter.cleanup_search(self.main_win)
        self.assertTrue(success)
        self.assertEqual(self.search_edit.text, "")
        self.assertIn("{ESC}", self.main_win.keys_typed)
        self.assertIsNone(self.adapter._search_edit)

    def test_cleanup_is_idempotent(self):
        self.assertTrue(self.adapter.cleanup_search(self.main_win))
        self.assertTrue(self.adapter.cleanup_search(self.main_win))
        self.assertTrue(self.adapter.cleanup_search(None))

    def test_open_chat_for_recipient_happy_path(self):
        result = self.adapter.open_chat_for_recipient("홍길동")
        self.assertTrue(result)
        self.assertTrue(self.chats_tab.is_selected())
        self.assertEqual(self.search_edit.text, "홍길동")
        self.assertGreaterEqual(
            self.chat_item.double_click_count + self.chat_item.invoke_count + self.chat_item.click_count,
            1,
        )

    def test_bounded_constants_conformity(self):
        self.assertEqual(DEFAULT_TIMEOUT_SEC, 5.0)
        self.assertEqual(MAX_RETRIES, 3)


class TestAgentSendLoopWithKakaoUIAdapter(unittest.TestCase):
    """Test the agent orchestration seam proving that when navigation/validation
    fails or cleanup fails, no message or image sending occurs and status is marked failed.
    """
    def setUp(self):
        from agent import CMHelperAgent
        self.CMHelperAgent = CMHelperAgent

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_aborts_send_on_navigation_failure(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 501, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": None}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True

        # Adapter raises navigation error
        mock_adapter = MagicMock()
        mock_adapter.open_chat_for_recipient.side_effect = KakaoAmbiguousResultError("동명이인 발견")
        agent.kakao_ui = mock_adapter

        # Run send loop once
        with patch("time.sleep"):
            # Set is_running to False after 1 iteration to prevent loop continuation
            def stop_after_one(*args, **kwargs):
                agent.is_running = False
            agent.update_tree_status.side_effect = stop_after_one

            self.CMHelperAgent._run_send_loop(agent)

        # Proof: Cleanup was called in finally
        mock_adapter.cleanup_search.assert_called()

        # Proof: Message text was NEVER copied to clipboard or typed
        mock_copy.assert_not_called()

        # Proof: Message was marked failed on API client
        agent.api_client.update_message_status.assert_called_with(501, "failed")

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_aborts_send_on_title_mismatch(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 502, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": "http://img.png"}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True

        # Adapter raises title mismatch
        mock_adapter = MagicMock()
        mock_adapter.open_chat_for_recipient.side_effect = KakaoTitleMismatchError("이름 불일치")
        agent.kakao_ui = mock_adapter

        with patch("time.sleep"):
            def stop_after_one(*args, **kwargs):
                agent.is_running = False
            agent.update_tree_status.side_effect = stop_after_one

            self.CMHelperAgent._run_send_loop(agent)

        # Proof: Cleanup called
        mock_adapter.cleanup_search.assert_called()

        # Proof: No image download, no clipboard copy, no hotkey
        agent.api_client.download_image.assert_not_called()
        mock_copy.assert_not_called()

        # Proof: Status updated to failed
        agent.api_client.update_message_status.assert_called_with(502, "failed")

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_reports_failed_on_activate_kakaotalk_not_found(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 503, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": None}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True
        agent.activate_kakaotalk.return_value = False

        with patch("time.sleep"):
            self.CMHelperAgent._run_send_loop(agent)

        mock_copy.assert_not_called()
        agent.api_client.update_message_status.assert_called_with(503, "failed")
        agent.update_tree_status.assert_called_with(503, "실패", "카카오톡 창을 찾을 수 없습니다!")
        self.assertFalse(agent.is_running)

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_reports_failed_on_kakao_window_not_found_error(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 504, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": None}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True
        agent.activate_kakaotalk.return_value = True

        mock_adapter = MagicMock()
        mock_adapter.open_chat_for_recipient.side_effect = KakaoWindowNotFoundError("창 없음")
        mock_adapter.cleanup_search.return_value = True
        agent.kakao_ui = mock_adapter

        with patch("time.sleep"):
            self.CMHelperAgent._run_send_loop(agent)

        mock_adapter.cleanup_search.assert_called()
        mock_copy.assert_not_called()
        agent.api_client.update_message_status.assert_called_with(504, "failed")
        agent.update_tree_status.assert_called_with(504, "실패", "카카오톡 창을 찾을 수 없습니다: 창 없음")
        self.assertFalse(agent.is_running)

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_aborts_send_and_reports_failed_on_cleanup_failure(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 505, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": None}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True
        agent.activate_kakaotalk.return_value = True

        mock_adapter = MagicMock()
        mock_adapter.open_chat_for_recipient.return_value = True
        # cleanup_search returns False indicating cleanup failure
        mock_adapter.cleanup_search.return_value = False
        agent.kakao_ui = mock_adapter

        with patch("time.sleep"):
            def stop_after_one(*args, **kwargs):
                agent.is_running = False
            agent.update_tree_status.side_effect = stop_after_one

            self.CMHelperAgent._run_send_loop(agent)

        mock_adapter.cleanup_search.assert_called()
        mock_copy.assert_not_called()
        mock_press.assert_called_with("esc")
        agent.api_client.update_message_status.assert_called_with(505, "failed")

    @patch("pyautogui.hotkey")
    @patch("pyautogui.press")
    @patch("pyperclip.copy")
    def test_agent_send_loop_aborts_send_and_reports_failed_on_cleanup_exception(self, mock_copy, mock_press, mock_hotkey):
        agent = MagicMock()
        agent.is_running = True
        agent.tasks_to_send = [
            {"id": 506, "customer_name": "홍길동", "message_text": "비밀 메시지", "image_url": None}
        ]
        agent.api_client = MagicMock()
        agent.api_client.is_authenticated.return_value = True
        agent.activate_kakaotalk.return_value = True

        mock_adapter = MagicMock()
        mock_adapter.open_chat_for_recipient.return_value = True
        # cleanup_search throws exception
        mock_adapter.cleanup_search.side_effect = RuntimeError("Cleanup failed unexpectedly")
        agent.kakao_ui = mock_adapter

        with patch("time.sleep"):
            def stop_after_one(*args, **kwargs):
                agent.is_running = False
            agent.update_tree_status.side_effect = stop_after_one

            self.CMHelperAgent._run_send_loop(agent)

        mock_adapter.cleanup_search.assert_called()
        mock_copy.assert_not_called()
        mock_press.assert_called_with("esc")
        agent.api_client.update_message_status.assert_called_with(506, "failed")


if __name__ == "__main__":
    unittest.main()
