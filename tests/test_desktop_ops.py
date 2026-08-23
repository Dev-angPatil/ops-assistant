"""Unit tests for Desktop and File Manipulation Operations."""

import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock

from ops_assistant.tools import desktop_ops


class TestDesktopOps(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ops_test_desktop_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("subprocess.Popen")
    @patch("shutil.which")
    def test_open_folder(self, mock_which, mock_popen):
        mock_which.return_value = "/usr/bin/xdg-open"
        res = desktop_ops.open_folder(self.test_dir)
        self.assertTrue(res["success"])
        self.assertIn("Opened directory", res["message"])
    def test_open_folder_nonexistent(self):
        res = desktop_ops.open_folder("/non/existent/path/9999")
        self.assertFalse(res["success"])
        self.assertIn("error", res)

    @patch("subprocess.Popen")
    @patch("shutil.which")
    def test_open_file(self, mock_which, mock_popen):
        test_file = os.path.join(self.test_dir, "sample.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        mock_which.return_value = "/usr/bin/xdg-open"
        res = desktop_ops.open_file(test_file)
        self.assertTrue(res["success"])

    @patch("subprocess.Popen")
    @patch("shutil.which")
    def test_open_image(self, mock_which, mock_popen):
        test_img = os.path.join(self.test_dir, "photo.png")
        with open(test_img, "wb") as f:
            f.write(b"PNG_DATA")
        mock_which.return_value = "/usr/bin/xdg-open"
        res = desktop_ops.open_image(test_img)
        self.assertTrue(res["success"])

    @patch("webbrowser.open")
    def test_open_browser(self, mock_wb_open):
        mock_wb_open.return_value = True
        res = desktop_ops.open_browser("https://github.com")
        self.assertTrue(res["success"])
        mock_wb_open.assert_called_once_with("https://github.com", new=2)

    def test_move_and_copy_and_trash(self):
        src_file = os.path.join(self.test_dir, "original.txt")
        with open(src_file, "w") as f:
            f.write("important data")

        # Copy
        dst_copy = os.path.join(self.test_dir, "copy.txt")
        c_res = desktop_ops.copy_path(src_file, dst_copy)
        self.assertTrue(c_res["success"])
        self.assertTrue(os.path.exists(dst_copy))

        # Move
        dst_move = os.path.join(self.test_dir, "moved.txt")
        m_res = desktop_ops.move_path(src_file, dst_move)
        self.assertTrue(m_res["success"])
        self.assertFalse(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dst_move))
        self.assertIn("rollback_command", m_res)

        # Trash
        t_res = desktop_ops.trash_path(dst_move)
        self.assertTrue(t_res["success"])
        self.assertFalse(os.path.exists(dst_move))

    def test_find_available_wallpapers(self):
        found = desktop_ops.find_available_wallpapers()
        self.assertIsInstance(found, list)

    @patch("shutil.which")
    def test_set_wallpaper(self, mock_which):
        img = os.path.join(self.test_dir, "wall.jpg")
        with open(img, "w") as f:
            f.write("image data")
        mock_which.return_value = None
        res = desktop_ops.set_wallpaper(img)
        self.assertTrue(res["success"])
        self.assertIn("wallpaper", res)

    def test_extended_desktop_media_and_ipc_commands(self):
        from ops_assistant.nlp.nl_compiler import NaturalLanguageCompiler

        # Media controls
        c_pause = NaturalLanguageCompiler.compile("pause music")
        self.assertIsNotNone(c_pause)
        self.assertIn("playerctl pause", c_pause["command"])

        c_play = NaturalLanguageCompiler.compile("resume music")
        self.assertIsNotNone(c_play)
        self.assertIn("playerctl play", c_play["command"])

        c_next = NaturalLanguageCompiler.compile("next song")
        self.assertIsNotNone(c_next)
        self.assertIn("playerctl next", c_next["command"])

        c_now = NaturalLanguageCompiler.compile("what song is playing")
        self.assertIsNotNone(c_now)
        self.assertIn("playerctl metadata", c_now["command"])

        # Brightness
        c_br = NaturalLanguageCompiler.compile("set brightness to 80%")
        self.assertIsNotNone(c_br)
        self.assertIn("brightnessctl set 80%", c_br["command"])

        c_br_up = NaturalLanguageCompiler.compile("increase brightness")
        self.assertIsNotNone(c_br_up)
        self.assertIn("brightnessctl set +10%", c_br_up["command"])

        # Window management
        c_close_win = NaturalLanguageCompiler.compile("close active window")
        self.assertIsNotNone(c_close_win)
        self.assertIn("killactive", c_close_win["command"])

        c_float = NaturalLanguageCompiler.compile("toggle floating")
        self.assertIsNotNone(c_float)
        self.assertIn("togglefloating", c_float["command"])

        c_ws = NaturalLanguageCompiler.compile("switch to workspace 2")
        self.assertIsNotNone(c_ws)
        self.assertIn("workspace 2", c_ws["command"])

        # File actions & archiving
        c_del = NaturalLanguageCompiler.compile("delete demo_folder")
        self.assertIsNotNone(c_del)
        self.assertIn("gio trash 'demo_folder'", c_del["command"])

        c_zip = NaturalLanguageCompiler.compile("zip folder my_project")
        self.assertIsNotNone(c_zip)
        self.assertIn("tar -czvf 'my_project.tar.gz'", c_zip["command"])

        # Notifications & Battery
        c_notif = NaturalLanguageCompiler.compile("send notification Backup complete")
        self.assertIsNotNone(c_notif)
        self.assertIn("notify-send", c_notif["command"])

        c_bat = NaturalLanguageCompiler.compile("check battery status")
        self.assertIsNotNone(c_bat)
        self.assertIn("upower", c_bat["command"])


if __name__ == "__main__":
    unittest.main()