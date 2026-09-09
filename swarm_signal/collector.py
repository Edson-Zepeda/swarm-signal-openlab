"""Strict Spanish/English adapter for the original WindowsWifiCollector.

RSSI must exist in the selected connected interface. No invented -80 dBm
fallback and no RSSI inferred from quality. Noise/counters in WifiSample are
unavailable placeholders, NEVER published or used as measurements.
"""
from __future__ import annotations
import ctypes
import re
import subprocess
import threading
import time
import unicodedata
from dataclasses import dataclass

from v1.src.sensing.rssi_collector import WindowsWifiCollector, WifiSample


def key(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c)).strip()


def read_netsh() -> str:
    proc = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                          capture_output=True, timeout=5,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    encoding = f'cp{ctypes.windll.kernel32.GetOEMCP()}' if hasattr(ctypes, 'windll') else 'utf-8'
    output = proc.stdout.decode(encoding, errors='replace')
    if proc.returncode:
        raise RuntimeError(f'netsh terminó con código {proc.returncode}. Revisa conexión y permisos de ubicación.')
    return output


def redact_netsh(output: str) -> str:
    """Retain RSSI/environment evidence while removing network identifiers."""
    lines = []
    for line in output.splitlines():
        k = key(line.split(':', 1)[0])
        if k in {'ssid', 'bssid', 'ap bssid', 'guid', 'perfil', 'profile',
                 'direccion', 'direccion fisica', 'physical address', 'name of profile'}:
            line = line.split(':', 1)[0] + ': [omitido: identificador de red]'
        lines.append(line)
    return '\n'.join(lines)


@dataclass(frozen=True)
class Reading:
    interface: str
    rssi_dbm: float
    quality: float | None


def parse_netsh(output: str, interface: str = 'Wi-Fi') -> Reading:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in output.splitlines():
        if ':' not in line:
            continue
        left, value = line.split(':', 1)
        field = key(left)
        if field in {'nombre', 'name'}:
            current = {'name': value.strip()}
            blocks.append(current)
        elif current is not None:
            current[field] = value.strip()
    block = next((b for b in blocks if b['name'].casefold() == interface.casefold()), None)
    if block is None:
        raise ValueError(f'No se encontró la interfaz {interface}.')
    state = key(block.get('estado', block.get('state', '')))
    if state not in {'connected', 'conectado', 'conectada'}:
        raise ValueError('La interfaz WiFi no está conectada.')
    raw = block.get('rssi', '')
    if not re.fullmatch(r'-?\d+(?:[.,]\d+)?(?:\s*dBm)?', raw, flags=re.I):
        raise ValueError('netsh no proporcionó RSSI directo en dBm; no se inventa una lectura.')
    rssi = float(re.sub(r'\s*dbm$', '', raw, flags=re.I).replace(',', '.'))
    if not -120 <= rssi <= -1:
        raise ValueError('RSSI fuera del intervalo físico admitido [-120, -1] dBm.')
    raw_quality = block.get('senal', block.get('signal'))
    quality = None
    if raw_quality is not None:
        try:
            quality = float(raw_quality.strip().rstrip('%').replace(',', '.')) / 100
        except ValueError as exc:
            raise ValueError('Porcentaje de señal inválido.') from exc
        if not 0 <= quality <= 1:
            raise ValueError('Porcentaje de señal fuera de rango.')
    return Reading(interface, rssi, quality)


class VerifiedWindowsCollector(WindowsWifiCollector):
    """Retains upstream collector interface, with strict OS validation."""
    def __init__(self, interface='Wi-Fi', sample_rate_hz=2.0, on_sample=None):
        if not 0 < sample_rate_hz <= 2:
            raise ValueError('La frecuencia debe estar entre 0 y 2 Hz.')
        super().__init__(interface, sample_rate_hz, buffer_seconds=3600)
        self.on_sample = on_sample
        self.last_error = None
        self.error_count = 0
        self.latencies: list[float] = []
        self._halt = threading.Event()

    def _validate_interface(self):
        parse_netsh(read_netsh(), self._interface)

    def _read_sample(self):
        began = time.monotonic()
        r = parse_netsh(read_netsh(), self._interface)
        self.latencies.append(time.monotonic() - began)
        # Fields below are compatibility placeholders, not observations.
        sample = WifiSample(time.time(), r.rssi_dbm, float('nan'),
                            r.quality if r.quality is not None else float('nan'),
                            0, 0, 0, r.interface)
        self.last_error = None
        return sample

    def start(self):
        self._halt.clear()
        super().start()

    def stop(self):
        self._halt.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=6)
            self._thread = None

    def _sample_loop(self):
        while self._running and not self._halt.is_set():
            began = time.monotonic()
            try:
                sample = self._read_sample()
                self._buffer.append(sample)
                if self.on_sample:
                    self.on_sample(sample)
            except Exception as exc:
                self.last_error = str(exc)
                self.error_count += 1
            self._halt.wait(max(0, 1 / self._rate - (time.monotonic() - began)))
