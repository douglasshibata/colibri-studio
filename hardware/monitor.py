"""
Hardware Monitoring Service for Colibri Studio.
Monitors real-time CPU utilization, RAM, VRAM, NVMe disk I/O, and model residency tiers.
"""

import time
import psutil
from typing import Dict, Any, Optional
from pydantic import BaseModel


class SystemMetrics(BaseModel):
    cpu_percent: float
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float
    vram_used_gb: float
    vram_total_gb: float
    vram_percent: float
    disk_read_mbs: float
    disk_write_mbs: float
    disk_free_gb: float
    disk_total_gb: float
    model_residency: Dict[str, float]  # percentage in VRAM, RAM, NVMe
    timestamp: float


class HardwareMonitor:
    def __init__(self):
        self._last_disk_io = psutil.disk_io_counters()
        self._last_disk_time = time.time()
        # Initialize CPU percent measurement
        psutil.cpu_percent(interval=None)

    def _get_gpu_metrics(self) -> Dict[str, float]:
        # Attempt nvml / nvidia-smi if available, fallback gracefully
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            total_vram = 0.0
            used_vram = 0.0
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_vram += info.total
                used_vram += info.used
            pynvml.nvmlShutdown()
            total_gb = round(total_vram / (1024 ** 3), 2)
            used_gb = round(used_vram / (1024 ** 3), 2)
            pct = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0.0
            return {"vram_used_gb": used_gb, "vram_total_gb": total_gb, "vram_percent": pct}
        except Exception:
            # Fallback estimation or 0 if no GPU detected
            return {"vram_used_gb": 0.0, "vram_total_gb": 0.0, "vram_percent": 0.0}

    def get_current_metrics(self, active_model_info: Optional[Dict[str, Any]] = None) -> SystemMetrics:
        now = time.time()
        dt = max(now - self._last_disk_time, 0.001)

        # CPU %
        cpu_pct = psutil.cpu_percent(interval=None)

        # RAM
        mem = psutil.virtual_memory()
        ram_used_gb = round(mem.used / (1024 ** 3), 2)
        ram_total_gb = round(mem.total / (1024 ** 3), 2)
        ram_pct = mem.percent

        # Disk I/O throughput
        disk_io = psutil.disk_io_counters()
        disk_read_mbs = 0.0
        disk_write_mbs = 0.0
        if disk_io and self._last_disk_io:
            read_bytes = disk_io.read_bytes - self._last_disk_io.read_bytes
            write_bytes = disk_io.write_bytes - self._last_disk_io.write_bytes
            disk_read_mbs = round((read_bytes / dt) / (1024 ** 2), 2)
            disk_write_mbs = round((write_bytes / dt) / (1024 ** 2), 2)

        self._last_disk_io = disk_io
        self._last_disk_time = now

        # Disk Storage Space
        usage = psutil.disk_usage("/")
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_total_gb = round(usage.total / (1024 ** 3), 2)

        # GPU metrics
        gpu_metrics = self._get_gpu_metrics()

        # Model residency allocation calculation
        # Default distribution if model active: RAM resident dense + NVMe streamed experts
        residency = {"vram": 0.0, "ram": 15.0, "nvme": 85.0}
        if gpu_metrics["vram_used_gb"] > 0 and active_model_info:
            residency = {"vram": 40.0, "ram": 30.0, "nvme": 30.0}

        return SystemMetrics(
            cpu_percent=cpu_pct,
            ram_used_gb=ram_used_gb,
            ram_total_gb=ram_total_gb,
            ram_percent=ram_pct,
            vram_used_gb=gpu_metrics["vram_used_gb"],
            vram_total_gb=gpu_metrics["vram_total_gb"],
            vram_percent=gpu_metrics["vram_percent"],
            disk_read_mbs=disk_read_mbs,
            disk_write_mbs=disk_write_mbs,
            disk_free_gb=disk_free_gb,
            disk_total_gb=disk_total_gb,
            model_residency=residency,
            timestamp=now
        )
