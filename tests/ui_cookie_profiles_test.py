from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from mediadownloader.services import SettingsService
from mediadownloader.ui.pages.about_page import AboutPage
from mediadownloader.ui.pages.settings_page import ProfileDialog
from mediadownloader.utils.cookie_profiles import matched_profile


def test_profile_dialog_collects_label_hosts_and_file(qtbot) -> None:
    dialog = ProfileDialog()
    qtbot.addWidget(dialog)

    dialog.label_edit.setText("Conta pessoal")
    dialog.hosts_edit.setText("youtube.com, m.youtube.com")
    dialog.file_edit.setText("C:\\perfis\\youtube.cookies.txt")

    profile = dialog.profile_data()

    assert profile["label"] == "Conta pessoal"
    assert profile["hosts"] == ["youtube.com", "m.youtube.com"]
    assert profile["file"] == "C:\\perfis\\youtube.cookies.txt"
    assert profile["id"] and profile["hosts"]
    assert all(host == host.strip() for host in profile["hosts"])


def test_profile_dialog_rejects_missing_hosts_or_file(qtbot, monkeypatch) -> None:
    dialog = ProfileDialog()
    qtbot.addWidget(dialog)

    warnings: list[str] = []

    def fake_warning(parent, title, text) -> int:
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))

    dialog.hosts_edit.setText("youtube.com")
    dialog.file_edit.setText("")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert "cookies.txt" in warnings[0]

    dialog.file_edit.setText("C:\\a.txt")
    dialog.hosts_edit.setText("")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_about_page_has_diagnostics_action_buttons(qtbot) -> None:
    page = AboutPage()
    qtbot.addWidget(page)

    assert page.findChild(type(page.copy_diagnostics_button))
    assert page.copy_diagnostics_button.text() == "Copiar diagnóstico"
    assert page.open_logs_button.text() == "Abrir pasta de logs"
    assert page.copy_diagnostics_button.isEnabled()
