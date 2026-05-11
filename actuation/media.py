"""Control de medios del SO: play/pause/next/prev/volumen/brillo (Windows)."""
from __future__ import annotations

import subprocess

from core.logger import logger


class Media:
    @staticmethod
    def play_pause() -> bool:
        return Media._press_vk(0xB3)

    @staticmethod
    def next_track() -> bool:
        return Media._press_vk(0xB0)

    @staticmethod
    def prev_track() -> bool:
        return Media._press_vk(0xB1)

    @staticmethod
    def stop() -> bool:
        return Media._press_vk(0xB2)

    @staticmethod
    def vol_up(steps: int = 2) -> bool:
        return all(Media._press_vk(0xAF) for _ in range(steps))

    @staticmethod
    def vol_down(steps: int = 2) -> bool:
        return all(Media._press_vk(0xAE) for _ in range(steps))

    @staticmethod
    def mute() -> bool:
        return Media._press_vk(0xAD)

    @staticmethod
    def _press_vk(vk: int) -> bool:
        try:
            import ctypes

            KEYEVENTF_KEYUP = 0x0002
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            logger.warning(f"media key {hex(vk)}: {e}")
            return False


class Brightness:
    @staticmethod
    def set_percent(pct: int) -> bool:
        pct = max(0, min(100, pct))
        try:
            cmd = (
                f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)."
                f"WmiSetBrightness(1,{pct})"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, timeout=8,
            )
            return r.returncode == 0
        except Exception as e:
            logger.warning(f"brillo {pct}: {e}")
            return False
