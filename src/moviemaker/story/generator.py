"""One-prompt story generation via local Ollama."""

from __future__ import annotations

import json
import re
from typing import Any

import aiohttp

from moviemaker.core.project import Project
from moviemaker.core.scene import Scene
from moviemaker.settings import AppSettings

SYSTEM = """You are a film writer for an AI video editor.
Return ONLY valid JSON with this shape:
{
  "title": "short title",
  "mood": "mood words",
  "storyline": "2-4 sentence story",
  "scenes": [
    {
      "title": "scene title",
      "plot_summary": "what happens, no camera jargon",
      "duration_seconds": 5,
      "prompt": "visual prompt for generation",
      "negative_prompt": "",
      "camera_motion": "static",
      "suggested_assets": ["subject_1"]
    }
  ]
}
Rules:
- Scene durations must sum close to target_length_seconds.
- Each duration between 3 and 12 seconds.
- camera_motion must be one of: static, dolly_in, pull_back, orbit, pan_left, pan_right, tilt_up, tilt_down, tracking, crane_up, handheld, push_in.
- Prompts are visual, concrete, present tense.
"""


async def generate_story(idea: str, project: Project, settings: AppSettings) -> dict[str, Any]:
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Idea: {idea}\n"
                    f"Existing mood: {project.mood}\n"
                    f"Existing storyline: {project.base_storyline}\n"
                    f"Aspect ratio: {project.aspect_ratio}\n"
                    f"Target length seconds: {project.target_length_seconds}\n"
                    f"Preset: {project.preset}\n"
                ),
            },
        ],
    }
    url = settings.ollama_host.rstrip("/") + "/api/chat"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {text[:400]}")
            data = await resp.json()
    content = data.get("message", {}).get("content") or data.get("response") or "{}"
    return _extract_json(content)


def apply_story(project: Project, story: dict[str, Any], default_model_id: str) -> list[Scene]:
    if story.get("mood"):
        project.mood = str(story["mood"])
    if story.get("storyline"):
        project.base_storyline = str(story["storyline"])
    if story.get("title") and project.name in {"Untitled", "New project", ""}:
        project.name = str(story["title"])
    scenes: list[Scene] = []
    cursor = 0.0
    for item in story.get("scenes") or []:
        duration = float(item.get("duration_seconds") or 5)
        duration = min(12.0, max(3.0, duration))
        scene = Scene(
            title=str(item.get("title") or f"Scene {len(scenes) + 1}"),
            plot_summary=str(item.get("plot_summary") or ""),
            prompt=str(item.get("prompt") or item.get("plot_summary") or ""),
            negative_prompt=str(item.get("negative_prompt") or ""),
            camera_motion=str(item.get("camera_motion") or "static"),
            duration_seconds=duration,
            start_time_seconds=cursor,
            model_id=default_model_id,
        )
        scenes.append(scene)
        cursor += duration
    project.scenes = scenes
    project.sync_timeline()
    return scenes


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return json.loads(match.group(0))
    raise RuntimeError("Story generator did not return JSON")
