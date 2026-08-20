from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mediadownloader.support import SUPPORT_PIX_KEY, SUPPORT_PIX_PAYLOAD
from mediadownloader.ui.pages.about_page import AboutPage


def _crc16_ccitt_false(value: str) -> str:
    crc = 0xFFFF
    for byte in value.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x1021) & 0xFFFF
                if crc & 0x8000
                else (crc << 1) & 0xFFFF
            )
    return f"{crc:04X}"


def test_support_pix_details_match_the_supplied_static_qr_code() -> None:
    assert str(uuid.UUID(SUPPORT_PIX_KEY)) == SUPPORT_PIX_KEY
    assert SUPPORT_PIX_KEY in SUPPORT_PIX_PAYLOAD
    payload_without_crc = SUPPORT_PIX_PAYLOAD[:-4]
    assert SUPPORT_PIX_PAYLOAD[-4:] == _crc16_ccitt_false(payload_without_crc)


def test_about_page_exposes_optional_pix_support(qapp, qtbot) -> None:
    page = AboutPage()
    qtbot.addWidget(page)

    assert page.support_card.qr_label.pixmap() is not None
    assert not page.support_card.qr_label.pixmap().isNull()
    assert page.support_card.key_label.text() == SUPPORT_PIX_KEY

    qtbot.mouseClick(page.support_card.copy_payload_button, Qt.MouseButton.LeftButton)

    assert QApplication.clipboard().text() == SUPPORT_PIX_PAYLOAD
    assert page.support_card.copy_payload_button.text() == "Pix Copia e Cola copiado"

    qtbot.mouseClick(page.support_card.copy_button, Qt.MouseButton.LeftButton)

    assert QApplication.clipboard().text() == SUPPORT_PIX_KEY
    assert page.support_card.copy_button.text() == "Chave Pix copiada"
