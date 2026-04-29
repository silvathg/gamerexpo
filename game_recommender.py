from __future__ import annotations

from typing import Any, Dict, List


GAME_CATALOG = [
    {
        "title": "League of Legends",
        "weight": "leve",
        "quality": "1080p alto",
        "fps": "60+",
        "note": "Otimo para maquinas de entrada e GPUs integradas.",
    },
    {
        "title": "Valorant",
        "weight": "leve",
        "quality": "1080p medio/alto",
        "fps": "60+",
        "note": "Prioriza CPU e costuma escalar bem em notebooks.",
    },
    {
        "title": "Minecraft",
        "weight": "leve",
        "quality": "1080p medio",
        "fps": "45-60",
        "note": "Evite shaders pesados em GPU integrada.",
    },
    {
        "title": "The Sims 4",
        "weight": "leve",
        "quality": "1080p medio",
        "fps": "45-60",
        "note": "Mods e expansoes podem aumentar uso de RAM.",
    },
    {
        "title": "GTA V",
        "weight": "medio",
        "quality": "900p/1080p baixo",
        "fps": "35-50",
        "note": "Reduzir sombras e distancia de populacao ajuda bastante.",
    },
    {
        "title": "Fortnite",
        "weight": "medio",
        "quality": "1080p baixo com modo desempenho",
        "fps": "45-60",
        "note": "Modo Performance e FSR podem estabilizar o jogo.",
    },
    {
        "title": "Forza Horizon 5",
        "weight": "pesado",
        "quality": "1080p baixo/medio",
        "fps": "30-45",
        "note": "Texturas dependem bastante de VRAM.",
    },
    {
        "title": "Cyberpunk 2077",
        "weight": "pesado",
        "quality": "720p/900p baixo",
        "fps": "25-35",
        "note": "Use FSR e mantenha ray tracing desligado.",
    },
    {
        "title": "Red Dead Redemption 2",
        "weight": "pesado",
        "quality": "900p baixo",
        "fps": "25-35",
        "note": "Exige GPU dedicada para uma experiencia mais confortavel.",
    },
]


def _score_machine(profile: Dict[str, Any]) -> int:
    analysis = profile.get("analysis", {})
    gpu_type = str(analysis.get("gpu_tipo", "")).lower()
    cpu_tier = str(analysis.get("cpu_tier", "")).lower()
    ram_gb = analysis.get("ram_total_gb") or 0
    vram_gb = analysis.get("gpu_vram_gb_estimada") or 0

    score = 1
    if ram_gb >= 16:
        score += 1
    if ram_gb >= 32:
        score += 1
    if gpu_type == "dedicada":
        score += 2
    if vram_gb >= 4:
        score += 1
    if vram_gb >= 8:
        score += 1
    if cpu_tier in {"intermediario", "intermediário", "alto", "entusiasta"}:
        score += 1
    if cpu_tier in {"alto", "entusiasta"}:
        score += 1
    return score


def _likely_bottleneck(profile: Dict[str, Any]) -> str:
    analysis = profile.get("analysis", {})
    gpu_type = str(analysis.get("gpu_tipo", "")).lower()
    ram_gb = analysis.get("ram_total_gb") or 0

    if gpu_type == "integrada":
        return "GPU"
    if ram_gb < 16:
        return "RAM"
    return "equilibrio CPU/GPU"


def recommend_games(profile: Dict[str, Any]) -> Dict[str, Any]:
    score = _score_machine(profile)
    bottleneck = _likely_bottleneck(profile)

    allowed_weights = {"leve"}
    if score >= 4:
        allowed_weights.add("medio")
    if score >= 6:
        allowed_weights.add("pesado")

    recommendations: List[Dict[str, str]] = []
    for game in GAME_CATALOG:
        if game["weight"] not in allowed_weights:
            continue

        quality = game["quality"]
        fps = game["fps"]
        if score <= 3 and game["weight"] == "medio":
            quality = "720p/900p baixo"
            fps = "30-45"
        elif score >= 7 and game["weight"] == "pesado":
            quality = "1080p medio/alto"
            fps = "45-60"

        recommendations.append(
            {
                "title": game["title"],
                "quality": quality,
                "resolution": quality.split(" ")[0],
                "fps": fps,
                "bottleneck": bottleneck,
                "note": game["note"],
            }
        )

    return {
        "machine_score": score,
        "probable_bottleneck": bottleneck,
        "recommendations": recommendations[:8],
    }

