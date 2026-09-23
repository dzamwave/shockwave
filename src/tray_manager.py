import ctypes
from ctypes import wintypes
import threading
import os
import sys

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidate = os.path.join(root_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# Win32 Constants
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

WM_USER = 0x0400
WM_TRAY_CALLBACK = WM_USER + 20
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9

GA_ROOT = 2

TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800

ID_SHOW_WIDGET = 1001
ID_SHOW_CONSOLE = 1002
ID_HIDE_CONSOLE = 1003
ID_QUIT = 1004

# 64-bit safe LRESULT & WNDPROC types
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

# Win32 Structure for Tray Icon
class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', wintypes.BYTE * 8)
    ]

CLSID_TaskbarList = GUID(0x56FDF344, 0xFD6D, 0x11d0, (wintypes.BYTE * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90))
IID_ITaskbarList = GUID(0x56FDF342, 0xFD6D, 0x11d0, (wintypes.BYTE * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90))

class ITaskbarListVtbl(ctypes.Structure):
    _fields_ = [
        ('QueryInterface', ctypes.c_void_p),
        ('AddRef', ctypes.c_void_p),
        ('Release', ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)),
        ('HrInit', ctypes.c_void_p),
        ('AddTab', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)),
        ('DeleteTab', ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)),
        ('ActivateTab', ctypes.c_void_p),
        ('SetActiveAlt', ctypes.c_void_p),
    ]

class ITaskbarList(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(ITaskbarListVtbl))]

def delete_taskbar_tab(hwnd):
    """Removes the window's button/tab from the Windows taskbar."""
    if not hwnd:
        return
    try:
        ole32 = ctypes.oledll.ole32
        ole32.CoInitialize(None)
        pTaskbarList = ctypes.POINTER(ITaskbarList)()
        hr = ole32.CoCreateInstance(ctypes.byref(CLSID_TaskbarList), None, 1, ctypes.byref(IID_ITaskbarList), ctypes.byref(pTaskbarList))
        if hr == 0 and pTaskbarList:
            pTaskbarList.contents.lpVtbl.contents.DeleteTab(pTaskbarList, hwnd)
            pTaskbarList.contents.lpVtbl.contents.Release(pTaskbarList)
    except Exception:
        pass

def add_taskbar_tab(hwnd):
    """Restores the window's button/tab to the Windows taskbar."""
    if not hwnd:
        return
    try:
        ole32 = ctypes.oledll.ole32
        ole32.CoInitialize(None)
        pTaskbarList = ctypes.POINTER(ITaskbarList)()
        hr = ole32.CoCreateInstance(ctypes.byref(CLSID_TaskbarList), None, 1, ctypes.byref(IID_ITaskbarList), ctypes.byref(pTaskbarList))
        if hr == 0 and pTaskbarList:
            pTaskbarList.contents.lpVtbl.contents.AddTab(pTaskbarList, hwnd)
            pTaskbarList.contents.lpVtbl.contents.Release(pTaskbarList)
    except Exception:
        pass

def get_root_console_hwnd():
    """Returns the top-level root window for the console (Windows Terminal or ConHost)."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return 0
        root = user32.GetAncestor(hwnd, GA_ROOT)
        return root if root else hwnd
    except Exception:
        return 0

def hide_console():
    """Hides the top-level console window from desktop and removes its button from the taskbar."""
    hwnd = get_root_console_hwnd()
    if hwnd:
        # Apply WS_EX_TOOLWINDOW to forcibly remove from taskbar (works on Windows Terminal)
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        try:
            style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass
        user32.ShowWindow(hwnd, SW_HIDE)
        delete_taskbar_tab(hwnd)

def show_console():
    """Restores and brings the top-level console window to the foreground with full history intact."""
    hwnd = get_root_console_hwnd()
    if hwnd:
        # Restore WS_EX_APPWINDOW so the window reappears on the taskbar normally
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        try:
            style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass
        add_taskbar_tab(hwnd)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)

def is_console_visible():
    """Checks if the console window is currently visible."""
    hwnd = get_root_console_hwnd()
    if hwnd:
        return bool(user32.IsWindowVisible(hwnd))
    return False

def toggle_console():
    """Toggles console window visibility."""
    if is_console_visible():
        hide_console()
    else:
        show_console()

class SystemTrayManager:
    """
    Lightweight Win32 System Tray Icon manager using native ctypes.
    Runs a message pump in a background thread.
    """
    def __init__(self, icon_path=None, tooltip="Shockwave v1.0.1", on_quit=None, on_show_widget=None):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_quit = on_quit
        self.on_show_widget = on_show_widget
        
        self.hwnd = None
        self.hicon = None
        self.nid = None
        self.thread = None
        self.is_running = False
        self._wndproc = WNDPROC(self._window_proc)

    def _load_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                self.hicon = user32.LoadImageW(
                    None,
                    self.icon_path,
                    IMAGE_ICON,
                    0, 0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE
                )
            except Exception:
                self.hicon = None
                
        if not self.hicon:
            # Fallback to system default application icon
            self.hicon = user32.LoadIconW(0, 32512)

    def _show_context_menu(self):
        hmenu = user32.CreatePopupMenu()
        
        # Menu options: bring widget above all windows
        user32.AppendMenuW(hmenu, MF_STRING, ID_SHOW_WIDGET, "Показать виджет поверх всех окон")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_SHOW_CONSOLE, "Показать панель управления")
        user32.AppendMenuW(hmenu, MF_STRING, ID_HIDE_CONSOLE, "Скрыть панель в трей")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_QUIT, "Выход из Shockwave")
        
        pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pos))
        
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(
            hmenu,
            TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
            pos.x, pos.y,
            0,
            self.hwnd,
            None
        )
        user32.DestroyMenu(hmenu)
        
        if cmd == ID_SHOW_WIDGET:
            if self.on_show_widget:
                self.on_show_widget()
        elif cmd == ID_SHOW_CONSOLE:
            show_console()
        elif cmd == ID_HIDE_CONSOLE:
            hide_console()
        elif cmd == ID_QUIT:
            if self.on_quit:
                self.on_quit()
            else:
                self.stop()
                sys.exit(0)

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY_CALLBACK:
            if lparam in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                if self.on_show_widget:
                    self.on_show_widget()
                else:
                    toggle_console()
                return 0
            elif lparam == WM_RBUTTONUP:
                self._show_context_menu()
                return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_message_loop(self):
        kernel32 = ctypes.windll.kernel32
        
        class_name = f"ShockwaveTrayClass_{os.getpid()}"
        hinstance = kernel32.GetModuleHandleW(None)
        
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinstance
        wc.lpszClassName = class_name
        
        user32.RegisterClassW(ctypes.byref(wc))
        
        self.hwnd = user32.CreateWindowExW(
            0, class_name, "ShockwaveTrayMsgWindow",
            0, 0, 0, 0, 0,
            0, 0, hinstance, None
        )
        
        self._load_icon()
        
        self.nid = NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1
        self.nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self.nid.uCallbackMessage = WM_TRAY_CALLBACK
        self.nid.hIcon = self.hicon
        self.nid.szTip = self.tooltip[:127]
        
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self.nid))
        self.is_running = True
        
        msg = wintypes.MSG()
        while self.is_running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def start(self):
        """Starts the tray icon message loop in a background daemon thread."""
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run_message_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Removes the tray icon and terminates the message pump."""
        self.is_running = False
        if self.nid and self.hwnd:
            try:
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
            except Exception:
                pass
        if self.hwnd:
            try:
                user32.PostMessageW(self.hwnd, WM_DESTROY, 0, 0)
            except Exception:
                pass
