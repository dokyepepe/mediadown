from PySide6.QtCore import Qt

from mediadownloader.ui.pages.qrcode_page import QrCodePage


def test_qrcode_page_validates_and_generates_an_image(qtbot) -> None:
    page = QrCodePage()
    qtbot.addWidget(page)

    page.url_input.setText("endereco-invalido")
    qtbot.mouseClick(page.generate_button, Qt.MouseButton.LeftButton)
    assert page.notice.isVisibleTo(page)
    assert page.copy_button.isEnabled() is False

    page.url_input.setText("https://example.com/path?a=1")
    qtbot.mouseClick(page.generate_button, Qt.MouseButton.LeftButton)
    assert page._pixmap.isNull() is False
    assert page.copy_button.isEnabled() is True
    assert page.save_button.isEnabled() is True
