"""Light editing-suite theme: readable panels, NLE timeline, collapsible rails."""

THEME_CSS = """
:root {
  --mm-bg: #eceef2;
  --mm-panel: #ffffff;
  --mm-panel-2: #f5f7fa;
  --mm-panel-3: #eef1f5;
  --mm-border: #d3d8e0;
  --mm-border-strong: #b9c0cc;
  --mm-text: #1f2933;
  --mm-muted: #6b7583;
  --mm-accent: #c47b17;
  --mm-accent-soft: #fff4e2;
}
body, .q-page, .nicegui-content, .q-header, .q-footer, .q-drawer {
  background: var(--mm-bg) !important;
  color: var(--mm-text) !important;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}
.q-header, .q-footer { color: var(--mm-text) !important; }

.mm-header {
  background: #ffffff !important;
  border-bottom: 1px solid var(--mm-border);
  color: var(--mm-text);
}
.mm-brand { color: var(--mm-accent); letter-spacing: 0.22em; }

/* Panels behave like docked NLE panels: header bar + scrollable body */
.mm-panel {
  background: var(--mm-panel);
  border: 1px solid var(--mm-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.mm-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: var(--mm-panel-2);
  border-bottom: 1px solid var(--mm-border);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--mm-muted);
  font-weight: 600;
  flex: 0 0 auto;
}
.mm-panel-body {
  padding: 10px;
  overflow: auto;
  flex: 1 1 auto;
  min-height: 0;
}

.mm-card {
  background: var(--mm-panel);
  border: 1px solid var(--mm-border);
  border-radius: 10px;
  padding: 12px;
  color: var(--mm-text);
}
.mm-title {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--mm-muted);
  margin-bottom: 8px;
  font-weight: 600;
}

/* Scene / asset list cards */
.mm-scene-card {
  background: var(--mm-panel-2);
  border: 1px solid var(--mm-border);
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--mm-text);
  transition: border-color .12s ease, background .12s ease;
}
.mm-scene-card:hover { border-color: var(--mm-border-strong); }
.mm-scene-card.active {
  border-color: var(--mm-accent);
  background: var(--mm-accent-soft);
}
.mm-chip-num {
  width: 20px; height: 20px; border-radius: 6px;
  background: var(--mm-panel-3); border: 1px solid var(--mm-border);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--mm-muted); flex: 0 0 auto;
}

/* Program monitor */
.mm-monitor {
  background: #101418;
  border: 1px solid var(--mm-border-strong);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}

/* ---- Timeline ---- */
.mm-tl-toolbar {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 8px; color: var(--mm-muted); font-size: 12px;
}
.mm-tl-ruler {
  position: relative;
  height: 22px;
  background: var(--mm-panel-2);
  border: 1px solid var(--mm-border);
  border-radius: 6px 6px 0 0;
  overflow: hidden;
}
.mm-tl-tick {
  position: absolute; top: 0; bottom: 0;
  border-left: 1px solid var(--mm-border-strong);
  font-size: 9px; color: var(--mm-muted); padding-left: 3px;
}
.mm-tl-row { display: flex; align-items: stretch; gap: 0; }
.mm-tl-label {
  width: 120px; flex: 0 0 120px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 6px; padding: 0 8px;
  background: var(--mm-panel-2);
  border: 1px solid var(--mm-border);
  border-top: none;
  font-size: 11px; color: var(--mm-muted);
}
.mm-tl-label.muted { opacity: .5; }
.mm-track {
  position: relative;
  height: 40px;
  background:
    repeating-linear-gradient(90deg, #e9edf2 0 1px, transparent 1px 100%);
  background-color: var(--mm-panel-3);
  border: 1px solid var(--mm-border);
  border-top: none;
  border-left: none;
  overflow: hidden;
  flex: 1 1 auto;
}
.mm-clip {
  position: absolute; top: 5px; height: 30px;
  background: #f3e6d2;
  border: 1px solid #d7b07a;
  border-radius: 5px;
  color: #5a3b12;
  font-size: 11px;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  padding: 3px 6px; cursor: pointer;
  box-shadow: 0 1px 2px rgba(0,0,0,.08);
}
.mm-clip:hover { filter: brightness(0.97); }
.mm-clip.audio { background: #e4e0f7; border-color: #b3a8e0; color: #3d3470; }
.mm-clip.image { background: #dcefe4; border-color: #97c4ab; color: #1f4d35; }
.mm-clip.active { outline: 2px solid var(--mm-accent); outline-offset: -1px; }

.mm-status-dot { width: 8px; height: 8px; border-radius: 99px; display: inline-block; }
.mm-dot-done { background: #15803d; }
.mm-dot-run { background: var(--mm-accent); }
.mm-dot-idle { background: #b9c0cc; }
.mm-dot-fail { background: #b91c1c; }

.q-field, .q-input, .q-textarea, .q-select,
.q-field__label, .q-field__native, .q-field__prefix, .q-field__suffix,
.q-placeholder { color: var(--mm-text) !important; }
.q-field__control, .q-field__marginal {
  background: #ffffff !important; color: var(--mm-text) !important;
}
.q-card { background: #ffffff !important; color: var(--mm-text) !important; }
.q-btn { color: inherit; }
"""


def inject_theme() -> None:
    from nicegui import ui

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">'
        '<meta name="color-scheme" content="light">'
    )
    ui.add_css(THEME_CSS)
    ui.colors(
        primary="#c47b17",
        secondary="#4b5563",
        accent="#c47b17",
        dark="#1f2933",
        dark_page="#eceef2",
        positive="#15803d",
        negative="#b91c1c",
    )
