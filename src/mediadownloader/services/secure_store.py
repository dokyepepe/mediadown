"""Small secret storage abstraction backed by Windows Credential Manager."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Protocol

from mediadownloader.version import APP_ID


class SecretStore(Protocol):
    """Persistence contract used by OAuth services without exposing credentials."""

    def read(self) -> str:
        ...

    def write(self, secret: str) -> None:
        ...

    def delete(self) -> None:
        ...


class MemorySecretStore:
    """Non-persistent store useful for tests and unsupported development hosts."""

    def __init__(self) -> None:
        self.secret = ""

    def read(self) -> str:
        return self.secret

    def write(self, secret: str) -> None:
        self.secret = secret

    def delete(self) -> None:
        self.secret = ""


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.c_void_p),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialStore:
    """Store an opaque UTF-8 secret under the current Windows user account."""

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    def __init__(self, target: str = f"{APP_ID}/SpotifyOAuth") -> None:
        if sys.platform != "win32":
            raise OSError("O Gerenciador de Credenciais requer Windows.")
        self.target = target
        self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._advapi.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        self._advapi.CredWriteW.restype = wintypes.BOOL
        self._advapi.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_Credential)),
        ]
        self._advapi.CredReadW.restype = wintypes.BOOL
        self._advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._advapi.CredDeleteW.restype = wintypes.BOOL
        self._advapi.CredFree.argtypes = [ctypes.c_void_p]
        self._advapi.CredFree.restype = None

    def read(self) -> str:
        pointer = ctypes.POINTER(_Credential)()
        if not self._advapi.CredReadW(
            self.target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)
        ):
            error = ctypes.get_last_error()
            if error == self.ERROR_NOT_FOUND:
                return ""
            raise ctypes.WinError(error)
        try:
            credential = pointer.contents
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-8")
        finally:
            self._advapi.CredFree(pointer)

    def write(self, secret: str) -> None:
        data = secret.encode("utf-8")
        buffer = ctypes.create_string_buffer(data)
        credential = _Credential()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self.target
        credential.CredentialBlobSize = len(data)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.c_void_p)
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "Spotify OAuth"
        if not self._advapi.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def delete(self) -> None:
        if self._advapi.CredDeleteW(self.target, self.CRED_TYPE_GENERIC, 0):
            return
        error = ctypes.get_last_error()
        if error != self.ERROR_NOT_FOUND:
            raise ctypes.WinError(error)


def default_secret_store() -> SecretStore:
    """Use the protected Windows vault, falling back to memory on dev-only hosts."""
    if sys.platform == "win32":
        return WindowsCredentialStore()
    return MemorySecretStore()
