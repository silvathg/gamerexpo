from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import gamerexpo


REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _first(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return items[0] if items else {}


def _safe(value: Any, fallback: str = "N/D") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _collect_errors(result: Dict[str, Any], label: str, errors: List[str]) -> Any:
    if result.get("error"):
        errors.append(f"{label}: {result['error']}")
    return result.get("data")


def _primary_gpu(gpus: List[Dict[str, Any]]) -> Dict[str, Any]:
    for gpu in gpus:
        name = _safe(gpu.get("Name")).lower()
        if "microsoft basic display adapter" not in name:
            return gpu
    return _first(gpus)


def collect_diagnostic() -> Dict[str, Any]:
    collection_errors: List[str] = []

    os_result = gamerexpo.collect_os_info()
    computer_result = gamerexpo.collect_computer_info()
    cpu_result = gamerexpo.collect_cpu_info()
    gpu_result = gamerexpo.collect_gpu_info()
    ram_result = gamerexpo.collect_ram_modules()
    motherboard_result = gamerexpo.collect_motherboard()
    disks_result = gamerexpo.collect_disks()
    directx_result = gamerexpo.collect_directx_version()

    bundle: Dict[str, Any] = {
        "os": _collect_errors(os_result, "Sistema operacional", collection_errors) or {},
        "computer": _collect_errors(computer_result, "Computador", collection_errors) or {},
        "cpus": _collect_errors(cpu_result, "Processador", collection_errors) or [],
        "gpus": _collect_errors(gpu_result, "GPU", collection_errors) or [],
        "ram_modules": _collect_errors(ram_result, "RAM", collection_errors) or [],
        "motherboard": _collect_errors(motherboard_result, "Placa-mae", collection_errors) or {},
        "disks": _collect_errors(disks_result, "Armazenamento", collection_errors) or {"fisicos": [], "logicos": []},
    }

    directx_version: Optional[str] = directx_result.get("data") if directx_result.get("success") else None
    if directx_result.get("error"):
        collection_errors.append(f"DirectX: {directx_result['error']}")

    analysis = gamerexpo.build_analysis(bundle, collection_errors)
    report_text = gamerexpo.render_report(bundle, analysis, directx_version, collection_errors)

    cpu = _first(bundle["cpus"])
    gpu = _primary_gpu(bundle["gpus"])
    disks = bundle["disks"]
    physical_disks = disks.get("fisicos", []) if isinstance(disks, dict) else []
    logical_disks = disks.get("logicos", []) if isinstance(disks, dict) else []

    generated_at = datetime.now().isoformat()
    payload = {
        "app": gamerexpo.APP_NAME,
        "version": gamerexpo.APP_VERSION,
        "generated_at": generated_at,
        "directx_version": directx_version,
        "hardware": bundle,
        "analysis": analysis,
        "collection_errors": collection_errors,
        "report_text": report_text,
        "summary": {
            "processor": {
                "name": _safe(cpu.get("Name")),
                "cores": cpu.get("NumberOfCores"),
                "threads": cpu.get("NumberOfLogicalProcessors"),
                "clock_ghz": gamerexpo.mhz_to_ghz(cpu.get("MaxClockSpeed")),
                "tier": analysis.get("cpu_tier"),
            },
            "gpu": {
                "name": _safe(gpu.get("Name")),
                "type": analysis.get("gpu_tipo"),
                "vram_gb": analysis.get("gpu_vram_gb_estimada"),
                "driver": _safe(gpu.get("DriverVersion")),
            },
            "ram": {
                "total_gb": analysis.get("ram_total_gb"),
                "modules": len(bundle["ram_modules"]),
            },
            "storage": {
                "physical_count": len(physical_disks),
                "logical_count": len(logical_disks),
                "has_ssd": analysis.get("storage_traits", {}).get("tem_ssd"),
                "has_hdd": analysis.get("storage_traits", {}).get("tem_hdd"),
                "items": physical_disks,
            },
            "directx": directx_version or "N/D",
            "profile": analysis.get("perfil_gamer", {}),
            "bottlenecks": analysis.get("pontos_de_atencao", []),
            "upgrades": analysis.get("upgrades_prioritarios", []),
            "strengths": analysis.get("pontos_fortes", []),
        },
    }
    return payload


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def save_report_files(payload: Dict[str, Any]) -> Dict[str, str]:
    reports_dir = ensure_reports_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"gamerexpo_diagnostico_{stamp}.json"
    txt_path = reports_dir / f"gamerexpo_diagnostico_{stamp}.txt"

    json_payload = {key: value for key, value in payload.items() if key != "report_text"}
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(payload.get("report_text", ""), encoding="utf-8")

    return {"json": str(json_path), "txt": str(txt_path)}

