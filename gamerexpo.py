"""
GamerExpo v1
Diagnóstico e análise básica de hardware para jogos. 

Recursos:
- Coleta de CPU, GPU, RAM, placa-mãe, discos, sistema operacional e DirectX;
- Geração de relatório em .txt e .json;
- Progresso em porcentagem durante a execução;
- Exibição explícita de erros de coleta; e
- Análise gamer – se imperfeita, vai assumir que é!

Observação:
- A leitura de VRAM no Windows pode ser aproximada em alguns hardwares;
- A análise final é técnica e NÃO substitui benchmarks reais por jogo.
"""

from __future__ import annotations

import io
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


APP_NAME = "GamerExpo v1"
APP_VERSION = "1.1"


# ============================================================
# Utilidades
# ============================================================

def safe_str(value: Any) -> str:
    if value is None:
        return "N/D"
    text = str(value).strip()
    return text if text else "N/D"


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def bytes_to_gb(value: Any) -> Optional[float]:
    number = safe_int(value)
    if number is None:
        return None
    return round(number / (1024 ** 3), 2)


def bytes_to_human(value: Any) -> str:
    number = safe_int(value)
    if number is None:
        return "N/D"

    size = float(number)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.2f} {units[idx]}"


def mhz_to_ghz(value: Any) -> Optional[float]:
    number = safe_int(value)
    if number is None:
        return None
    return round(number / 1000, 2)


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title.upper())
    print("=" * 78)


def get_output_directory() -> Path:
    if "__file__" in globals():
        return Path(__file__).resolve().parent
    return Path.cwd()


# ============================================================
# Progresso
# ============================================================

class ProgressTracker:
    def __init__(self, total_steps: int) -> None:
        self.total_steps = max(total_steps, 1)
        self.current_step = 0

    def step(self, message: str) -> None:
        self.current_step += 1
        percent = int((self.current_step / self.total_steps) * 100)
        print(f"[{percent:>3}%] {message}")


# ============================================================
# PowerShell / Coleta
# ============================================================

def find_powershell() -> Optional[str]:
    candidates = [
        "powershell.exe",
        "powershell",
        "pwsh.exe",
        "pwsh",
    ]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def run_powershell_json(ps_script: str) -> Dict[str, Any]:
    exe = find_powershell()
    if not exe:
        return {
            "ok": False,
            "data": None,
            "error": "PowerShell não encontrado no sistema.",
            "engine": None,
            "stdout": "",
            "stderr": "",
        }

    wrapper = f"""
    $ErrorActionPreference = 'Stop'
    try {{
        $result = & {{
            {ps_script}
        }}
        $payload = [PSCustomObject]@{{
            ok = $true
            data = $result
            error = $null
            engine = '{Path(exe).name}'
        }}
    }}
    catch {{
        $payload = [PSCustomObject]@{{
            ok = $false
            data = $null
            error = $_.Exception.Message
            engine = '{Path(exe).name}'
        }}
    }}
    $payload | ConvertTo-Json -Depth 8 -Compress
    """

    completed = subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", wrapper],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    if not stdout:
        return {
            "ok": False,
            "data": None,
            "error": f"Sem saída do PowerShell. stderr: {stderr or 'vazio'}",
            "engine": Path(exe).name,
            "stdout": stdout,
            "stderr": stderr,
        }

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "data": None,
            "error": f"Falha ao interpretar JSON do PowerShell: {exc}",
            "engine": Path(exe).name,
            "stdout": stdout,
            "stderr": stderr,
        }

    payload["stdout"] = stdout
    payload["stderr"] = stderr
    return payload


def make_wmi_script(select_from_cim: str, select_from_wmi: str) -> str:
    return f"""
    if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {{
        {select_from_cim}
    }}
    elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {{
        {select_from_wmi}
    }}
    else {{
        throw 'Nem Get-CimInstance nem Get-WmiObject estão disponíveis.'
    }}
    """


def collect_with_fallback(name: str, ps_script: str, expected: str = "list") -> Dict[str, Any]:
    result = run_powershell_json(ps_script)

    output = {
        "name": name,
        "success": False,
        "data": [] if expected == "list" else {},
        "error": None,
        "engine": result.get("engine"),
    }

    if not result.get("ok"):
        output["error"] = result.get("error") or "Erro desconhecido."
        return output

    data = result.get("data")

    if expected == "list":
        output["data"] = ensure_list(data)
    elif expected == "dict":
        if isinstance(data, dict):
            output["data"] = data
        elif isinstance(data, list) and data:
            output["data"] = data[0]
        else:
            output["data"] = {}
    else:
        output["data"] = data

    output["success"] = True
    return output


def collect_os_info() -> Dict[str, Any]:
    base = {
        "sistema": platform.system(),
        "release": platform.release(),
        "versao": platform.version(),
        "arquitetura": platform.machine(),
        "python": platform.python_version(),
    }

    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_OperatingSystem |
        Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime
        """,
        """
        Get-WmiObject Win32_OperatingSystem |
        Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime
        """,
    )

    result = collect_with_fallback("os", ps_script, expected="dict")
    data = result["data"] if isinstance(result["data"], dict) else {}

    merged = {**base, **data}
    return {
        "success": result["success"],
        "data": merged,
        "error": result["error"],
        "engine": result["engine"],
    }


def collect_computer_info() -> Dict[str, Any]:
    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_ComputerSystem |
        Select-Object Manufacturer, Model, TotalPhysicalMemory
        """,
        """
        Get-WmiObject Win32_ComputerSystem |
        Select-Object Manufacturer, Model, TotalPhysicalMemory
        """,
    )
    return collect_with_fallback("computer", ps_script, expected="dict")


def collect_cpu_info() -> Dict[str, Any]:
    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_Processor |
        Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors,
                      MaxClockSpeed, L2CacheSize, L3CacheSize, ProcessorId
        """,
        """
        Get-WmiObject Win32_Processor |
        Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors,
                      MaxClockSpeed, L2CacheSize, L3CacheSize, ProcessorId
        """,
    )
    return collect_with_fallback("cpus", ps_script, expected="list")


def collect_gpu_info() -> Dict[str, Any]:
    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_VideoController |
        Select-Object Name, VideoProcessor, AdapterRAM, DriverVersion,
                      CurrentHorizontalResolution, CurrentVerticalResolution,
                      CurrentRefreshRate, VideoModeDescription, Status
        """,
        """
        Get-WmiObject Win32_VideoController |
        Select-Object Name, VideoProcessor, AdapterRAM, DriverVersion,
                      CurrentHorizontalResolution, CurrentVerticalResolution,
                      CurrentRefreshRate, VideoModeDescription, Status
        """,
    )
    return collect_with_fallback("gpus", ps_script, expected="list")


def collect_ram_modules() -> Dict[str, Any]:
    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_PhysicalMemory |
        Select-Object Manufacturer, Capacity, Speed, PartNumber, DeviceLocator, BankLabel
        """,
        """
        Get-WmiObject Win32_PhysicalMemory |
        Select-Object Manufacturer, Capacity, Speed, PartNumber, DeviceLocator, BankLabel
        """,
    )
    return collect_with_fallback("ram_modules", ps_script, expected="list")


def collect_motherboard() -> Dict[str, Any]:
    ps_script = make_wmi_script(
        """
        Get-CimInstance Win32_BaseBoard |
        Select-Object Manufacturer, Product, SerialNumber
        """,
        """
        Get-WmiObject Win32_BaseBoard |
        Select-Object Manufacturer, Product, SerialNumber
        """,
    )
    return collect_with_fallback("motherboard", ps_script, expected="dict")


def collect_disks() -> Dict[str, Any]:
    physical_script = make_wmi_script(
        """
        Get-CimInstance Win32_DiskDrive |
        Select-Object Model, InterfaceType, MediaType, Size, SerialNumber
        """,
        """
        Get-WmiObject Win32_DiskDrive |
        Select-Object Model, InterfaceType, MediaType, Size, SerialNumber
        """,
    )
    logical_script = make_wmi_script(
        """
        Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
        Select-Object DeviceID, VolumeName, FileSystem, Size, FreeSpace
        """,
        """
        Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" |
        Select-Object DeviceID, VolumeName, FileSystem, Size, FreeSpace
        """,
    )

    physical = collect_with_fallback("disks_physical", physical_script, expected="list")
    logical = collect_with_fallback("disks_logical", logical_script, expected="list")

    success = physical["success"] or logical["success"]
    errors = []
    if physical["error"]:
        errors.append(f"Físicos: {physical['error']}")
    if logical["error"]:
        errors.append(f"Lógicos: {logical['error']}")

    return {
        "name": "disks",
        "success": success,
        "data": {
            "fisicos": physical["data"],
            "logicos": logical["data"],
        },
        "error": " | ".join(errors) if errors else None,
        "engine": physical.get("engine") or logical.get("engine"),
    }


def collect_directx_version() -> Dict[str, Any]:
    exe = shutil.which("dxdiag")
    if not exe:
        return {
            "success": False,
            "data": None,
            "error": "dxdiag não encontrado no sistema.",
            "engine": None,
        }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        temp_path = Path(tmp.name)

    try:
        completed = subprocess.run(
            [exe, "/whql:off", "/t", str(temp_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if completed.returncode != 0:
            return {
                "success": False,
                "data": None,
                "error": completed.stderr.strip() or "dxdiag retornou erro sem mensagem.",
                "engine": Path(exe).name,
            }

        content = temp_path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"DirectX Version:\s*(.+)", content, re.IGNORECASE)
        if match:
            return {
                "success": True,
                "data": match.group(1).strip(),
                "error": None,
                "engine": Path(exe).name,
            }

        return {
            "success": False,
            "data": None,
            "error": "Não foi possível localizar a versão do DirectX no relatório do dxdiag.",
            "engine": Path(exe).name,
        }

    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================
# Análise
# ============================================================

def detect_storage_traits(disks: Dict[str, List[Dict[str, Any]]]) -> Dict[str, bool]:
    has_ssd = False
    has_hdd = False

    for disk in disks.get("fisicos", []):
        media = safe_str(disk.get("MediaType")).lower()
        model = safe_str(disk.get("Model")).lower()

        if any(token in media for token in ("ssd", "solid state")):
            has_ssd = True
        elif any(token in media for token in ("hdd", "hard disk")):
            has_hdd = True

        if "nvme" in model or "ssd" in model:
            has_ssd = True
        if "hdd" in model:
            has_hdd = True

    return {"tem_ssd": has_ssd, "tem_hdd": has_hdd}


def estimate_gpu_class(name: str, vram_gb: Optional[float]) -> str:
    lower = name.lower()

    integrated_signals = [
        "intel uhd",
        "intel hd",
        "iris xe",
        "iris plus",
        "radeon graphics",
        "vega",
        "microsoft basic display adapter",
    ]

    if any(sig in lower for sig in integrated_signals):
        return "integrada"
    if any(sig in lower for sig in ("rtx", "gtx", " arc ", "arc ", " rx ", "radeon rx")):
        return "dedicada"
    if vram_gb is not None and vram_gb >= 2:
        return "dedicada"
    return "indeterminada"


def estimate_cpu_tier(cpu_name: str, threads: Optional[int]) -> str:
    lower = cpu_name.lower()
    threads = threads or 0

    if any(k in lower for k in ("i9", "ryzen 9", "ultra 9")) or threads >= 20:
        return "entusiasta"
    if any(k in lower for k in ("i7", "ryzen 7", "ultra 7")) or threads >= 12:
        return "alto"
    if any(k in lower for k in ("i5", "ryzen 5", "ultra 5")) or threads >= 8:
        return "intermediário"
    if any(k in lower for k in ("i3", "ryzen 3")) or threads >= 4:
        return "entrada"
    return "básico"


def build_analysis(bundle: Dict[str, Any], collection_errors: List[str]) -> Dict[str, Any]:
    computer = bundle["computer"]
    cpus = bundle["cpus"]
    gpus = bundle["gpus"]
    disks = bundle["disks"]

    total_ram_bytes = safe_int(computer.get("TotalPhysicalMemory"))
    total_ram_gb = bytes_to_gb(total_ram_bytes)

    primary_cpu = cpus[0] if cpus else {}
    primary_gpu = {}

    for gpu in gpus:
        name = safe_str(gpu.get("Name")).lower()
        if "microsoft basic display adapter" not in name:
            primary_gpu = gpu
            break
    if not primary_gpu and gpus:
        primary_gpu = gpus[0]

    cpu_name = safe_str(primary_cpu.get("Name"))
    cpu_threads = safe_int(primary_cpu.get("NumberOfLogicalProcessors"))
    gpu_name = safe_str(primary_gpu.get("Name"))
    gpu_vram_gb = bytes_to_gb(primary_gpu.get("AdapterRAM")) if primary_gpu else None
    storage_traits = detect_storage_traits(disks)

    has_minimum_data = any(
        [
            total_ram_gb is not None,
            cpu_name != "N/D",
            gpu_name != "N/D",
        ]
    )

    if not has_minimum_data:
        return {
            "dados_suficientes": False,
            "ram_total_gb": None,
            "cpu_tier": "indisponível",
            "gpu_principal": "indisponível",
            "gpu_vram_gb_estimada": None,
            "gpu_tipo": "indisponível",
            "storage_traits": storage_traits,
            "perfil_gamer": {
                "nivel": "indeterminado",
                "tipos_de_jogos": "Não foi possível estimar por falha na coleta de hardware.",
                "preset_geral": "Não disponível",
                "observacoes": "A análise gamer foi bloqueada porque os dados mínimos de hardware não foram coletados.",
            },
            "pontos_fortes": [],
            "pontos_de_atencao": [
                "Coleta de hardware insuficiente para análise confiável.",
                "Verifique a seção 'Erros de coleta' no relatório.",
            ],
            "upgrades_prioritarios": [
                "Antes de sugerir upgrade, corrija a coleta de hardware para conhecer a máquina real."
            ],
            "collection_errors": collection_errors,
        }

    cpu_tier = estimate_cpu_tier(cpu_name, cpu_threads)
    gpu_tipo = estimate_gpu_class(gpu_name, gpu_vram_gb)

    strengths = []
    cautions = []
    upgrades = []

    if total_ram_gb is not None:
        if total_ram_gb >= 32:
            strengths.append("boa folga de RAM para jogos e multitarefa")
        elif total_ram_gb >= 16:
            strengths.append("quantidade de RAM adequada para a maioria dos jogos atuais")
        else:
            cautions.append("menos de 16 GB de RAM pode limitar jogos atuais e multitarefa")

    if storage_traits["tem_ssd"]:
        strengths.append("SSD detectado, o que ajuda em boot e carregamento")
    else:
        cautions.append("SSD não identificado; os carregamentos podem ser mais lentos")

    if cpu_tier in ("alto", "entusiasta"):
        strengths.append("processador forte para jogos e tarefas paralelas")
    elif cpu_tier == "intermediário":
        strengths.append("processador competente para jogos em 1080p")
    else:
        cautions.append("processador pode limitar desempenho em jogos mais pesados")

    if gpu_tipo == "integrada":
        cautions.append("GPU integrada tende a ser o principal gargalo em jogos pesados")
        nivel = "casual"
        tipos = "eSports leves, indies, MOBAs e jogos competitivos mais otimizados"
        preset = "720p a 1080p no baixo"
        upgrades.append("o maior salto de desempenho viria de uma placa de vídeo dedicada")
    elif gpu_tipo == "dedicada":
        if (gpu_vram_gb or 0) >= 8 and (total_ram_gb or 0) >= 16 and cpu_tier in ("intermediário", "alto", "entusiasta"):
            nivel = "intermediário-forte"
            tipos = "AAA atuais em 1080p, eSports em alto FPS e boa margem para jogos modernos"
            preset = "1080p alto / 1440p médio"
        elif (gpu_vram_gb or 0) >= 4:
            nivel = "entrada"
            tipos = "eSports, AAAs mais antigos e parte dos atuais com ajustes conservadores"
            preset = "1080p baixo/médio"
        else:
            nivel = "básico"
            tipos = "jogos leves, antigos e bem otimizados"
            preset = "720p a 1080p no baixo"
    else:
        nivel = "indeterminado"
        tipos = "Não foi possível classificar a GPU com segurança."
        preset = "Não disponível"
        cautions.append("tipo de GPU não pôde ser determinado com segurança")

    if total_ram_gb is not None and total_ram_gb < 16:
        upgrades.append("subir a RAM para pelo menos 16 GB pode melhorar a experiência")
    if not storage_traits["tem_ssd"]:
        upgrades.append("instalar um SSD pode reduzir drasticamente tempos de carregamento")

    return {
        "dados_suficientes": True,
        "ram_total_gb": total_ram_gb,
        "cpu_tier": cpu_tier,
        "gpu_principal": gpu_name,
        "gpu_vram_gb_estimada": gpu_vram_gb,
        "gpu_tipo": gpu_tipo,
        "storage_traits": storage_traits,
        "perfil_gamer": {
            "nivel": nivel,
            "tipos_de_jogos": tipos,
            "preset_geral": preset,
            "observacoes": "Análise heurística; compare sempre com os requisitos do jogo desejado.",
        },
        "pontos_fortes": strengths,
        "pontos_de_atencao": cautions,
        "upgrades_prioritarios": upgrades,
        "collection_errors": collection_errors,
    }


# ============================================================
# Renderização
# ============================================================

def print_os_info(data: Dict[str, Any]) -> None:
    print_section("Sistema operacional")
    print(f"Nome do sistema         : {safe_str(data.get('Caption', data.get('caption', data.get('sistema'))))}")
    print(f"Release                 : {safe_str(data.get('release'))}")
    print(f"Versão                  : {safe_str(data.get('Version', data.get('versao')))}")
    print(f"Build                   : {safe_str(data.get('BuildNumber', data.get('build')))}")
    print(f"Arquitetura             : {safe_str(data.get('OSArchitecture', data.get('os_arch', data.get('arquitetura'))))}")
    print(f"Python                  : {safe_str(data.get('python'))}")
    print(f"Último boot             : {safe_str(data.get('LastBootUpTime', data.get('last_boot')))}")


def print_computer_info(data: Dict[str, Any]) -> None:
    print_section("Computador")
    print(f"Fabricante              : {safe_str(data.get('Manufacturer'))}")
    print(f"Modelo                  : {safe_str(data.get('Model'))}")
    total_ram = bytes_to_gb(data.get("TotalPhysicalMemory"))
    print(f"RAM total               : {total_ram if total_ram is not None else 'N/D'} GB")


def print_cpu_info(cpus: List[Dict[str, Any]]) -> None:
    print_section("Processador")
    if not cpus:
        print("Nenhum processador identificado.")
        return

    for idx, cpu in enumerate(cpus, start=1):
        print(f"[CPU {idx}]")
        print(f"Nome                    : {safe_str(cpu.get('Name'))}")
        print(f"Fabricante              : {safe_str(cpu.get('Manufacturer'))}")
        print(f"Núcleos                 : {safe_str(cpu.get('NumberOfCores'))}")
        print(f"Threads lógicos         : {safe_str(cpu.get('NumberOfLogicalProcessors'))}")
        max_clock = mhz_to_ghz(cpu.get("MaxClockSpeed"))
        print(f"Clock máximo            : {max_clock if max_clock is not None else 'N/D'} GHz")
        print(f"Cache L2                : {safe_str(cpu.get('L2CacheSize'))} KB")
        print(f"Cache L3                : {safe_str(cpu.get('L3CacheSize'))} KB")
        print(f"Processor ID            : {safe_str(cpu.get('ProcessorId'))}")
        print()


def print_gpu_info(gpus: List[Dict[str, Any]]) -> None:
    print_section("Placa(s) de vídeo")
    if not gpus:
        print("Nenhuma GPU identificada.")
        return

    for idx, gpu in enumerate(gpus, start=1):
        print(f"[GPU {idx}]")
        print(f"Nome                    : {safe_str(gpu.get('Name'))}")
        print(f"Processador de vídeo    : {safe_str(gpu.get('VideoProcessor'))}")
        vram = bytes_to_gb(gpu.get("AdapterRAM"))
        print(f"VRAM estimada           : {vram if vram is not None else 'N/D'} GB")
        print(f"Driver                  : {safe_str(gpu.get('DriverVersion'))}")
        print(
            f"Resolução atual         : "
            f"{safe_str(gpu.get('CurrentHorizontalResolution'))} x "
            f"{safe_str(gpu.get('CurrentVerticalResolution'))}"
        )
        print(f"Refresh rate            : {safe_str(gpu.get('CurrentRefreshRate'))} Hz")
        print(f"Modo de vídeo           : {safe_str(gpu.get('VideoModeDescription'))}")
        print(f"Status                  : {safe_str(gpu.get('Status'))}")
        print()


def print_ram_info(ram_modules: List[Dict[str, Any]], total_ram_gb: Optional[float]) -> None:
    print_section("Memória RAM")
    print(f"RAM total detectada     : {total_ram_gb if total_ram_gb is not None else 'N/D'} GB\n")

    if not ram_modules:
        print("Nenhum módulo de RAM identificado.")
        return

    for idx, module in enumerate(ram_modules, start=1):
        print(f"[Módulo {idx}]")
        print(f"Fabricante              : {safe_str(module.get('Manufacturer'))}")
        print(f"Capacidade              : {bytes_to_human(module.get('Capacity'))}")
        print(f"Velocidade              : {safe_str(module.get('Speed'))} MHz")
        print(f"Part number             : {safe_str(module.get('PartNumber'))}")
        print(f"Slot                    : {safe_str(module.get('DeviceLocator'))}")
        print(f"Banco                   : {safe_str(module.get('BankLabel'))}")
        print()


def print_motherboard_info(board: Dict[str, Any]) -> None:
    print_section("Placa-mãe")
    print(f"Fabricante              : {safe_str(board.get('Manufacturer'))}")
    print(f"Produto                 : {safe_str(board.get('Product'))}")
    print(f"Serial                  : {safe_str(board.get('SerialNumber'))}")


def print_disk_info(disks: Dict[str, List[Dict[str, Any]]]) -> None:
    print_section("Armazenamento físico")
    physical = disks.get("fisicos", [])
    if not physical:
        print("Nenhum disco físico identificado.")
    else:
        for idx, disk in enumerate(physical, start=1):
            print(f"[Disco físico {idx}]")
            print(f"Modelo                  : {safe_str(disk.get('Model'))}")
            print(f"Interface               : {safe_str(disk.get('InterfaceType'))}")
            print(f"Tipo de mídia           : {safe_str(disk.get('MediaType'))}")
            print(f"Tamanho                 : {bytes_to_human(disk.get('Size'))}")
            print(f"Serial                  : {safe_str(disk.get('SerialNumber'))}")
            print()

    print_section("Unidades lógicas")
    logical = disks.get("logicos", [])
    if not logical:
        print("Nenhuma unidade lógica identificada.")
    else:
        for idx, disk in enumerate(logical, start=1):
            print(f"[Unidade {idx}]")
            print(f"Letra                   : {safe_str(disk.get('DeviceID'))}")
            print(f"Volume                  : {safe_str(disk.get('VolumeName'))}")
            print(f"Sistema de arquivos     : {safe_str(disk.get('FileSystem'))}")
            print(f"Tamanho                 : {bytes_to_human(disk.get('Size'))}")
            print(f"Espaço livre            : {bytes_to_human(disk.get('FreeSpace'))}")
            print()


def print_analysis(analysis: Dict[str, Any], directx_version: Optional[str]) -> None:
    print_section("Análise gamer")
    print(f"Tier do processador     : {safe_str(analysis.get('cpu_tier'))}")
    print(f"GPU principal           : {safe_str(analysis.get('gpu_principal'))}")
    print(
        f"VRAM estimada           : "
        f"{analysis.get('gpu_vram_gb_estimada') if analysis.get('gpu_vram_gb_estimada') is not None else 'N/D'} GB"
    )
    print(f"Tipo de GPU             : {safe_str(analysis.get('gpu_tipo'))}")
    print(f"RAM total               : {analysis.get('ram_total_gb') if analysis.get('ram_total_gb') is not None else 'N/D'} GB")
    print(f"DirectX                 : {directx_version or 'N/D'}")

    perfil = analysis.get("perfil_gamer", {})
    print(f"\nPerfil geral            : {safe_str(perfil.get('nivel'))}")
    print(f"Jogos que tende a rodar : {safe_str(perfil.get('tipos_de_jogos'))}")
    print(f"Preset sugerido         : {safe_str(perfil.get('preset_geral'))}")
    print(f"Observações             : {safe_str(perfil.get('observacoes'))}")

    print("\nPontos fortes:")
    strengths = analysis.get("pontos_fortes", [])
    if strengths:
        for item in strengths:
            print(f"  - {item}")
    else:
        print("  - Nenhum destaque confiável foi detectado.")

    print("\nPontos de atenção:")
    cautions = analysis.get("pontos_de_atencao", [])
    if cautions:
        for item in cautions:
            print(f"  - {item}")
    else:
        print("  - Nada crítico detectado.")

    print("\nUpgrades prioritários:")
    upgrades = analysis.get("upgrades_prioritarios", [])
    if upgrades:
        for item in upgrades:
            print(f"  - {item}")
    else:
        print("  - A configuração parece equilibrada no cenário geral.")


def print_collection_errors(errors: List[str]) -> None:
    print_section("Erros de coleta")
    if not errors:
        print("Nenhum erro de coleta foi registrado.")
        return

    for idx, error in enumerate(errors, start=1):
        print(f"{idx}. {error}")


def render_report(bundle: Dict[str, Any], analysis: Dict[str, Any], directx_version: Optional[str], errors: List[str]) -> str:
    buffer = io.StringIO()

    with redirect_stdout(buffer):
        print(f"{APP_NAME} {APP_VERSION} | Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("Diagnóstico de hardware com foco em entendimento de jogos que a máquina tende a rodar.")
        print("Atenção: esta análise é heurística e não substitui benchmark real por jogo.\n")

        print_os_info(bundle["os"])
        print_computer_info(bundle["computer"])
        print_cpu_info(bundle["cpus"])
        print_gpu_info(bundle["gpus"])
        print_ram_info(bundle["ram_modules"], analysis.get("ram_total_gb"))
        print_motherboard_info(bundle["motherboard"])
        print_disk_info(bundle["disks"])
        print_analysis(analysis, directx_version)
        print_collection_errors(errors)

        print_section("Observação técnica")
        print(
            "A leitura de VRAM no Windows pode ser aproximada em alguns hardwares;"
            "Para compatibilidade exata por jogo, compare também os requisitos"
            "mínimos e recomendados do título desejado."
        )

    return buffer.getvalue()


# ============================================================
# Exportação
# ============================================================

def export_json(bundle: Dict[str, Any], analysis: Dict[str, Any], directx_version: Optional[str], errors: List[str], path: Path) -> None:
    payload = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "generated_at": datetime.now().isoformat(),
        "directx_version": directx_version,
        "hardware": bundle,
        "analysis": analysis,
        "collection_errors": errors,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_txt(report_text: str, path: Path) -> None:
    path.write_text(report_text, encoding="utf-8")


# ============================================================
# Execução principal
# ============================================================

def main() -> int:
    if platform.system().lower() != "windows":
        print(f"{APP_NAME} foi pensado para Windows. O sistema atual é: {platform.system()}.")
        print("A coleta principal depende de WMI/CIM via PowerShell.")
        return 1

    tracker = ProgressTracker(total_steps=10)

    try:
        tracker.step("Iniciando diagnóstico")
        bundle: Dict[str, Any] = {}
        collection_errors: List[str] = []

        tracker.step("Coletando sistema operacional")
        os_result = collect_os_info()
        bundle["os"] = os_result["data"]
        if os_result["error"]:
            collection_errors.append(f"Sistema operacional: {os_result['error']}")

        tracker.step("Coletando dados do computador")
        computer_result = collect_computer_info()
        bundle["computer"] = computer_result["data"]
        if computer_result["error"]:
            collection_errors.append(f"Computador: {computer_result['error']}")

        tracker.step("Coletando processador")
        cpu_result = collect_cpu_info()
        bundle["cpus"] = cpu_result["data"]
        if cpu_result["error"]:
            collection_errors.append(f"Processador: {cpu_result['error']}")

        tracker.step("Coletando placas de vídeo")
        gpu_result = collect_gpu_info()
        bundle["gpus"] = gpu_result["data"]
        if gpu_result["error"]:
            collection_errors.append(f"GPU: {gpu_result['error']}")

        tracker.step("Coletando módulos de RAM")
        ram_result = collect_ram_modules()
        bundle["ram_modules"] = ram_result["data"]
        if ram_result["error"]:
            collection_errors.append(f"RAM: {ram_result['error']}")

        tracker.step("Coletando placa-mãe")
        motherboard_result = collect_motherboard()
        bundle["motherboard"] = motherboard_result["data"]
        if motherboard_result["error"]:
            collection_errors.append(f"Placa-mãe: {motherboard_result['error']}")

        tracker.step("Coletando armazenamento")
        disks_result = collect_disks()
        bundle["disks"] = disks_result["data"]
        if disks_result["error"]:
            collection_errors.append(f"Armazenamento: {disks_result['error']}")

        tracker.step("Coletando DirectX")
        directx_result = collect_directx_version()
        directx_version = directx_result["data"] if directx_result["success"] else None
        if directx_result["error"]:
            collection_errors.append(f"DirectX: {directx_result['error']}")

        tracker.step("Processando análise")
        analysis = build_analysis(bundle, collection_errors)

        tracker.step("Gerando arquivos de saída")
        report_text = render_report(bundle, analysis, directx_version, collection_errors)
        print("\n" + report_text, end="")

        output_dir = get_output_directory()
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / "gamerexpo_v1_relatorio.json"
        txt_path = output_dir / "gamerexpo_v1_relatorio.txt"

        export_json(bundle, analysis, directx_version, collection_errors, json_path)
        export_txt(report_text, txt_path)

        print(f"\nRelatório JSON exportado para: {json_path}")
        print(f"Relatório TXT exportado para : {txt_path}")
        return 0

    except KeyboardInterrupt:
        print("\nExecução cancelada pelo usuário.")
        return 130
    except Exception as exc:
        print(f"\nFalha na execução do {APP_NAME}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())