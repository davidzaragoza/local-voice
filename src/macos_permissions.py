"""macOS permission helpers for microphone, accessibility, and input monitoring."""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
import ctypes

logger = logging.getLogger(__name__)

PERMISSION_MICROPHONE = "Microphone"
PERMISSION_ACCESSIBILITY = "Accessibility"
PERMISSION_INPUT_MONITORING = "Input Monitoring"


def is_macos() -> bool:
    return platform.system() == "Darwin"


def _load_application_services():
    try:
        return ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
    except Exception:
        return None


def is_accessibility_trusted(request_prompt: bool = False) -> bool:
    if not is_macos():
        return True

    if request_prompt:
        try:
            from Quartz import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

            return bool(
                AXIsProcessTrustedWithOptions(
                    {kAXTrustedCheckOptionPrompt: True}
                )
            )
        except Exception:
            logger.debug("AXIsProcessTrustedWithOptions unavailable; falling back to status check")

    app_services = _load_application_services()
    if app_services is None:
        return True

    try:
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrusted())
    except Exception:
        return True


def is_input_monitoring_trusted(request_prompt: bool = False) -> bool:
    if not is_macos():
        return True

    app_services = _load_application_services()
    if app_services is None:
        return True

    try:
        preflight = getattr(app_services, "CGPreflightListenEventAccess", None)
        request = getattr(app_services, "CGRequestListenEventAccess", None)

        if request_prompt and request is not None:
            request.restype = ctypes.c_bool
            _ = bool(request())

        if preflight is None:
            return True

        preflight.restype = ctypes.c_bool
        return bool(preflight())
    except Exception:
        return True


def has_microphone_access(request_prompt: bool = False) -> bool | None:
    if not is_macos():
        return True

    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
    except Exception:
        logger.debug("AVFoundation unavailable; cannot preflight microphone permission")
        return None

    try:
        status = int(AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio))
        if status == 3:
            return True
        if status in (1, 2):
            return False

        if request_prompt and status == 0:
            done = threading.Event()
            result = {"granted": False}

            def _callback(granted):
                result["granted"] = bool(granted)
                done.set()

            AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVMediaTypeAudio,
                _callback,
            )
            done.wait(timeout=10)
            return bool(result["granted"])

        return False
    except Exception:
        return False


def open_privacy_settings(permission_name: str):
    if not is_macos():
        return

    anchors = {
        PERMISSION_MICROPHONE: "Privacy_Microphone",
        PERMISSION_ACCESSIBILITY: "Privacy_Accessibility",
        PERMISSION_INPUT_MONITORING: "Privacy_ListenEvent",
    }
    anchor = anchors.get(permission_name)
    if not anchor:
        return

    url = f"x-apple.systempreferences:com.apple.preference.security?{anchor}"
    try:
        subprocess.Popen(["open", url])
    except Exception as e:
        logger.warning("Failed opening macOS Settings pane for %s: %s", permission_name, e)
