"""Run on YOUR computer. Reports hardware/tools, never reads credentials."""

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

result = {
    "os": platform.platform(),
    "processor": platform.processor(),
    "logical_cpus": os.cpu_count(),
    "python": platform.python_version(),
    "docker_installed": bool(shutil.which("docker")),
    "git_installed": bool(shutil.which("git")),
}
if result["docker_installed"]:
    try:
        p = subprocess.run(
            ["docker", "info", "--format", "{{.MemTotal}}"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        result["docker_running"] = p.returncode == 0
        if p.returncode == 0:
            result["docker_memory_gib"] = round(int(p.stdout.strip()) / (1024**3), 1)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        result["docker_running"] = False
if Path("/proc/meminfo").exists():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            result["host_memory_gib"] = round(int(line.split()[1]) / 1024**2, 1)
if platform.system() == "Windows":
    try:
        p = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[PSCustomObject]@{Memory=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; CPU=(Get-CimInstance Win32_Processor).Name} | ConvertTo-Json -Compress",
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )
        if p.returncode == 0:
            hardware = json.loads(p.stdout)
            result["host_memory_gib"] = round(int(hardware["Memory"]) / (1024**3), 1)
            result["processor"] = hardware["CPU"]
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
elif platform.system() == "Darwin":
    try:
        result["host_memory_gib"] = round(
            int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=5))
            / (1024**3),
            1,
        )
        result["processor"] = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=5
        ).strip()
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
elif Path("/proc/cpuinfo").exists():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            result["processor"] = line.split(":", 1)[1].strip()
            break
print(json.dumps(result, indent=2))
