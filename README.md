# Movie Maker

Desktop-style AI video editor. NiceGUI in the front, **Wan2GP** in the back, plugins in between.

## What it is

A file-based project tool for movies, ads, and other short-form video. Each project is a folder with `project.json`, assets, generated clips, logs, and exports. Generation goes through Wan2GP's headless CLI (`wgp.py --process`) in Wan2GP's own venv. If Wan2GP is missing, a mock backend still lets you walk the full UI.

## Run

```bash
uv sync
uv run moviemaker
```

Force the mock backend (no GPU / no Wan2GP):

```bash
uv run moviemaker --mock
```

Open http://127.0.0.1:8088 (or the port in Settings).

## First-run settings

Gear icon in the header:

- **Wan2GP path** — auto-detected from Pinokio (`…/pinokio/api/wan.git/app`). Must contain `wgp.py` and `env/bin/python`.
- **Ollama** — host + model for the one-prompt story writer (default `qwen2.5:7b`).
- **Hardware** — VRAM / RAM / Low-VRAM mode. Plugins pick bf16 / INT8 / pruned / GGUF from this.

App settings live in `~/.config/moviemaker/settings.json`. They are not stored in the project.

## Workflow

1. **New project** in an empty folder (mood, storyline, aspect, length, preset).
2. **Story** — one idea → Ollama writes scene cards (title, plot, duration, draft prompt).
3. **Assets** — upload stills, or generate/edit in Asset Studio (Flux / Qwen Image Edit / any image catalog entry).
4. **Scene panel** — pick a Wan2GP model from the live catalog, override quantization, camera, first/last frame, steps.
5. **Generate** — scenes that share `(architecture, model_type, quantization)` are batched so the model stays hot.
6. **Timeline** — video / audio / overlay layers. Player plays a scene or a full export.
7. **Export movie** — FFmpeg concat + optional cross-fade + audio mix.

## Plugins

| Plugin | Kind | Architectures (Wan2GP) |
| --- | --- | --- |
| `minimax_h3` | video | `minimax_h3_fl2va`, pruned, ref2va |
| `wan` | video | `t2v`, `t2v_2_2`, `i2v_2_2`, … |
| `ltx2` | video | `ltx2_22B`, distilled, GGUF |
| `flux` | image | Flux / Kontext / Krea / Klein |
| `qwen_image_edit` | image | Qwen Image + Edit Plus |
| `generic` | both | anything else in `defaults/*.json` |

Drop a new package under `src/moviemaker/plugins/` with `plugin.py`, `prompt_builder.py`, `settings_map.py`, and `references/`, then register it in `plugins/registry.py`.

## Layout of a project folder

```
my_film/
  project.json
  assets/
  clips/
  export/
  logs/
  tmp/
```
