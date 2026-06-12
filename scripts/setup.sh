#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="document_extract"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODE=""
ASSUME_YES=0
SKIP_SYSTEM_INSTALL=0
TESSDATA_FAST_REF="87416418657359cb625c412a48b6e1d6d41c29bd"

log() { printf '\033[1;34m[document-extract]\033[0m %s\n' "$*"; }
ok() { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Hermes Document Extract Plugin setup

Usage:
  bash scripts/setup.sh              # interactive mode chooser
  bash scripts/setup.sh --basic      # documents only, no OCR
  bash scripts/setup.sh --full       # documents + OCR with Tesseract

Options:
  --basic                 Install Python dependencies only.
  --full                  Install Python dependencies + Tesseract OCR + eng/rus/osd language data.
  -y, --yes               Accept default yes answers for install/download prompts.
  --skip-system-install   Do not install Tesseract with a package manager; only use an existing binary.
  -h, --help              Show this help.

Environment overrides:
  HERMES_PYTHON=/path/to/python       Hermes Agent Python interpreter.
  HERMES_HOME=/path/to/hermes-home    Hermes home/profile directory.
  TESSERACT_CMD=/path/to/tesseract    Tesseract executable.
  TESSDATA_PREFIX=/path/to/tessdata   Existing Tesseract language-data directory.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --basic) MODE="basic" ;;
    --full) MODE="full" ;;
    -y|--yes) ASSUME_YES=1 ;;
    --skip-system-install) SKIP_SYSTEM_INSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

confirm() {
  local prompt="$1"
  local default="${2:-Y}"
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    warn "Non-interactive shell: refusing to auto-confirm '$prompt'. Rerun with -y to approve."
    return 1
  fi
  local suffix="[Y/n]"
  [[ "$default" =~ ^[Nn]$ ]] && suffix="[y/N]"
  local answer
  read -r -p "$prompt $suffix " answer || answer=""
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$ ]]
}

detect_os() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null || printf unknown)"
  case "$uname_s" in
    MINGW*|MSYS*|CYGWIN*) printf 'windows' ;;
    Darwin*) printf 'macos' ;;
    Linux*) printf 'linux' ;;
    *) printf 'unknown' ;;
  esac
}

OS_TYPE="$(detect_os)"

to_unix_path() {
  local path="$1"
  if [[ "$OS_TYPE" == "windows" ]] && command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$path" 2>/dev/null || printf '%s' "$path"
  else
    printf '%s' "$path"
  fi
}

canonical_cmd() {
  local cmd="$1"
  if command -v readlink >/dev/null 2>&1; then
    readlink -f "$cmd" 2>/dev/null || printf '%s' "$cmd"
  else
    printf '%s' "$cmd"
  fi
}

is_hermes_python() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  "$py" - <<'PY' >/dev/null 2>&1
import importlib.util, sys
mods = ("hermes_cli", "run_agent")
sys.exit(0 if any(importlib.util.find_spec(m) for m in mods) else 1)
PY
}

find_hermes_python() {
  local candidates=()

  [[ -n "${HERMES_PYTHON:-}" ]] && candidates+=("$(to_unix_path "$HERMES_PYTHON")")
  [[ -n "${HERMES_PY:-}" ]] && candidates+=("$(to_unix_path "$HERMES_PY")")

  if command -v hermes >/dev/null 2>&1; then
    local hermes_bin hermes_dir
    hermes_bin="$(canonical_cmd "$(command -v hermes)")"
    hermes_dir="$(dirname "$hermes_bin")"
    candidates+=(
      "$hermes_dir/python"
      "$hermes_dir/python3"
      "$hermes_dir/python.exe"
      "$hermes_dir/../bin/python"
      "$hermes_dir/../Scripts/python.exe"
    )
  fi

  [[ -n "${VIRTUAL_ENV:-}" ]] && candidates+=("$VIRTUAL_ENV/bin/python" "$VIRTUAL_ENV/Scripts/python.exe")

  if [[ "$OS_TYPE" == "windows" ]]; then
    if [[ -n "${LOCALAPPDATA:-}" ]]; then
      local local_appdata
      local_appdata="$(to_unix_path "$LOCALAPPDATA")"
      candidates+=("$local_appdata/hermes/hermes-agent/venv/Scripts/python.exe")
    fi
    candidates+=("$HOME/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe")
  else
    candidates+=(
      "${XDG_DATA_HOME:-$HOME/.local/share}/hermes/hermes-agent/venv/bin/python"
      "$HOME/.hermes/hermes-agent/venv/bin/python"
      "$HOME/.local/share/hermes/hermes-agent/venv/bin/python"
    )
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if is_hermes_python "$candidate"; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  return 1
}

infer_hermes_home() {
  if [[ -n "${HERMES_HOME:-}" ]]; then
    to_unix_path "$HERMES_HOME"
    return 0
  fi
  if [[ "$REPO_DIR" == *"/plugins/$PLUGIN_NAME" ]]; then
    printf '%s' "${REPO_DIR%/plugins/$PLUGIN_NAME}"
  else
    printf '%s' "$HOME/.hermes"
  fi
}

choose_mode() {
  if [[ -n "$MODE" ]]; then
    return 0
  fi
  cat <<'CHOICES'

Choose setup mode:

  1) Basic — documents only: PDF/DOCX/XLSX/PPTX/HTML/TXT via MarkItDown
  2) Full  — Basic + image/screenshot OCR via Tesseract (eng/rus/osd)

CHOICES
  local answer
  read -r -p "Select 1 or 2 [1]: " answer || true
  answer="${answer:-1}"
  case "$answer" in
    1|basic|Basic|BASIC) MODE="basic" ;;
    2|full|Full|FULL) MODE="full" ;;
    *) die "Invalid setup mode: $answer" ;;
  esac
}

install_uv_if_needed() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  warn "uv is not installed or not on PATH."
  if ! confirm "Install uv now with the official Astral installer?" "Y"; then
    die "uv is required when Hermes Python has no pip. Install uv or set HERMES_PYTHON."
  fi
  command -v curl >/dev/null 2>&1 || die "curl is required to install uv automatically."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv install finished, but uv is still not on PATH. Open a new shell and rerun setup."
}

install_python_deps() {
  local hermes_py="$1"
  log "Installing Python dependencies into Hermes Python: $hermes_py"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$hermes_py" -r "$REPO_DIR/requirements.txt"
  elif "$hermes_py" -m pip --version >/dev/null 2>&1; then
    "$hermes_py" -m pip install -r "$REPO_DIR/requirements.txt"
  else
    install_uv_if_needed
    uv pip install --python "$hermes_py" -r "$REPO_DIR/requirements.txt"
  fi
}

verify_python_deps() {
  local hermes_py="$1"
  log "Checking Python dependencies"
  "$hermes_py" - <<'PY'
import importlib.util, sys
missing = []
for module in ("markitdown", "PIL"):
    if importlib.util.find_spec(module) is None:
        missing.append(module)
if missing:
    raise SystemExit("Missing Python modules: " + ", ".join(missing))
print("MarkItDown: OK")
print("Pillow: OK")
PY
}

find_tesseract() {
  local candidates=()
  [[ -n "${TESSERACT_CMD:-}" ]] && candidates+=("$(to_unix_path "$TESSERACT_CMD")")
  if command -v tesseract >/dev/null 2>&1; then
    candidates+=("$(command -v tesseract)")
  fi
  candidates+=(
    "/c/Program Files/Tesseract-OCR/tesseract.exe"
    "/c/Program Files (x86)/Tesseract-OCR/tesseract.exe"
    "C:/Program Files/Tesseract-OCR/tesseract.exe"
    "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"
    "/opt/homebrew/bin/tesseract"
    "/usr/local/bin/tesseract"
    "/usr/bin/tesseract"
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    printf '%s' "$candidate"
    return 0
  done
  return 1
}

sudo_prefix() {
  if [[ "${EUID:-$(id -u)}" == "0" ]]; then
    printf ''
  elif command -v sudo >/dev/null 2>&1; then
    printf 'sudo '
  else
    return 1
  fi
}

install_tesseract() {
  if find_tesseract >/dev/null 2>&1; then
    ok "Tesseract already installed: $(find_tesseract)"
    return 0
  fi

  if [[ "$SKIP_SYSTEM_INSTALL" == "1" ]]; then
    die "Tesseract is not installed and --skip-system-install was used."
  fi

  warn "Tesseract is not installed."
  if ! confirm "Install Tesseract OCR with the system package manager?" "Y"; then
    die "Full setup requires Tesseract. Rerun with --basic to skip OCR."
  fi

  case "$OS_TYPE" in
    windows)
      if command -v winget >/dev/null 2>&1; then
        winget install --id tesseract-ocr.tesseract --accept-source-agreements --accept-package-agreements
      elif command -v choco >/dev/null 2>&1; then
        choco install tesseract -y
      elif command -v scoop >/dev/null 2>&1; then
        scoop install tesseract
      else
        die "No supported Windows package manager found. Install winget, Chocolatey, or Scoop."
      fi
      ;;
    macos)
      command -v brew >/dev/null 2>&1 || die "Homebrew is required to install Tesseract automatically on macOS."
      brew install tesseract
      ;;
    linux)
      local sudo_cmd
      sudo_cmd="$(sudo_prefix)" || die "sudo is required to install Tesseract automatically."
      if command -v apt-get >/dev/null 2>&1; then
        ${sudo_cmd}apt-get update
        ${sudo_cmd}apt-get install -y tesseract-ocr
      elif command -v dnf >/dev/null 2>&1; then
        ${sudo_cmd}dnf install -y tesseract
      elif command -v yum >/dev/null 2>&1; then
        ${sudo_cmd}yum install -y tesseract
      elif command -v pacman >/dev/null 2>&1; then
        ${sudo_cmd}pacman -Sy --noconfirm tesseract
      elif command -v zypper >/dev/null 2>&1; then
        ${sudo_cmd}zypper --non-interactive install tesseract-ocr
      elif command -v apk >/dev/null 2>&1; then
        ${sudo_cmd}apk add tesseract-ocr
      else
        die "No supported Linux package manager found. Install Tesseract manually, then rerun setup."
      fi
      ;;
    *)
      die "Unsupported OS for automatic Tesseract install: $OS_TYPE"
      ;;
  esac

  find_tesseract >/dev/null 2>&1 || die "Tesseract install command completed, but tesseract was not found. Open a new shell or set TESSERACT_CMD."
  ok "Tesseract installed: $(find_tesseract)"
}

system_tessdata_dirs() {
  [[ -n "${TESSDATA_PREFIX:-}" ]] && {
    printf '%s\n' "$(to_unix_path "$TESSDATA_PREFIX")"
    printf '%s\n' "$(to_unix_path "$TESSDATA_PREFIX")/tessdata"
  }

  local tess="$1"
  local tess_dir
  tess_dir="$(dirname "$tess")"
  printf '%s\n' \
    "$tess_dir/tessdata" \
    "$tess_dir/../share/tessdata" \
    "/c/Program Files/Tesseract-OCR/tessdata" \
    "/c/Program Files (x86)/Tesseract-OCR/tessdata" \
    "C:/Program Files/Tesseract-OCR/tessdata" \
    "C:/Program Files (x86)/Tesseract-OCR/tessdata" \
    "/opt/homebrew/share/tessdata" \
    "/usr/local/share/tessdata" \
    "/usr/share/tessdata" \
    "/usr/share/tesseract-ocr/5/tessdata" \
    "/usr/share/tesseract-ocr/4.00/tessdata"
}

find_langdata() {
  local tess="$1"
  local lang="$2"
  local dir
  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    if [[ -f "$dir/$lang.traineddata" ]]; then
      printf '%s' "$dir/$lang.traineddata"
      return 0
    fi
  done < <(system_tessdata_dirs "$tess")
  return 1
}

download_file() {
  local url="$1"
  local dest="$2"
  local hermes_py="$3"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 -o "$dest" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$dest" "$url"
  else
    "$hermes_py" - "$url" "$dest" <<'PY'
import sys, urllib.request
url, dest = sys.argv[1], sys.argv[2]
urllib.request.urlretrieve(url, dest)
PY
  fi
}

expected_langdata_sha256() {
  case "$1" in
    eng) printf '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2' ;;
    osd) printf '9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff' ;;
    rus) printf 'e16e5e036cce1d9ec2b00063cf8b54472625b9e14d893a169e2b0dedeb4df225' ;;
    *) return 1 ;;
  esac
}

verify_sha256() {
  local file="$1"
  local expected="$2"
  local hermes_py="$3"
  "$hermes_py" - "$file" "$expected" <<'PY'
import hashlib, sys
path, expected = sys.argv[1], sys.argv[2].lower()
with open(path, 'rb') as f:
    actual = hashlib.sha256(f.read()).hexdigest()
if actual != expected:
    raise SystemExit(f"SHA256 mismatch for {path}: expected {expected}, got {actual}")
PY
}

ensure_langdata() {
  local tess="$1"
  local lang="$2"
  local tessdata_dir="$3"
  local hermes_py="$4"
  local dest="$tessdata_dir/$lang.traineddata"

  if [[ -f "$dest" ]]; then
    ok "$lang.traineddata already present"
    return 0
  fi

  local src=""
  if src="$(find_langdata "$tess" "$lang" 2>/dev/null)" && [[ -n "$src" ]]; then
    cp "$src" "$dest"
    ok "Copied $lang.traineddata from system tessdata"
    return 0
  fi

  local checksum
  checksum="$(expected_langdata_sha256 "$lang")" || die "No pinned checksum for language data: $lang"
  local url="https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$TESSDATA_FAST_REF/$lang.traineddata"
  warn "$lang.traineddata not found locally. Downloading from official tesseract-ocr/tessdata_fast at pinned commit $TESSDATA_FAST_REF."
  if [[ "$lang" == "rus" ]]; then
    if ! confirm "Download Russian OCR data (rus.traineddata)?" "Y"; then
      die "Russian OCR data is required for Full setup."
    fi
  fi
  download_file "$url" "$dest" "$hermes_py"
  [[ -s "$dest" ]] || die "Downloaded $dest is empty."
  verify_sha256 "$dest" "$checksum" "$hermes_py"
  ok "Downloaded and verified $lang.traineddata"
}

ensure_tessdata() {
  local tess="$1"
  local hermes_home="$2"
  local hermes_py="$3"
  local tessdata_dir="$hermes_home/tessdata"
  mkdir -p "$tessdata_dir"

  log "Preparing OCR language data in: $tessdata_dir"
  ensure_langdata "$tess" eng "$tessdata_dir" "$hermes_py"
  ensure_langdata "$tess" osd "$tessdata_dir" "$hermes_py"
  ensure_langdata "$tess" rus "$tessdata_dir" "$hermes_py"

  log "Checking Tesseract languages"
  local output
  output="$("$tess" --list-langs --tessdata-dir "$tessdata_dir" 2>&1 || true)"
  printf '%s\n' "$output"
  for lang in eng osd rus; do
    printf '%s\n' "$output" | grep -qx "$lang" || die "Tesseract cannot see language: $lang"
  done
  ok "OCR languages available: eng, osd, rus"
}

smoke_check() {
  local hermes_py="$1"
  local mode="$2"
  log "Running plugin smoke check"
  "$hermes_py" - "$REPO_DIR" "$mode" <<'PY'
import json, sys
from pathlib import Path
repo = Path(sys.argv[1])
mode = sys.argv[2]
sys.path.insert(0, str(repo))
import tools
status = json.loads(tools.handle_document_extract_status({}))
deps = status.get("dependencies", {})
if not deps.get("markitdown_available"):
    raise SystemExit("MarkItDown is not available")
if not deps.get("pillow_available"):
    raise SystemExit("Pillow is not available")
print("Plugin version:", status.get("plugin_version"))
print("MarkItDown:", deps.get("markitdown_version") or "OK")
if mode == "full":
    if not deps.get("tesseract_available"):
        raise SystemExit("Tesseract is not available")
    langs = set(deps.get("tesseract_languages") or [])
    missing = {"eng", "rus", "osd"} - langs
    if missing:
        raise SystemExit("Missing Tesseract languages: " + ", ".join(sorted(missing)))
    print("Tesseract:", deps.get("tesseract_version"))
    print("OCR languages:", ", ".join(sorted(langs)))
else:
    print("Tesseract: skipped in Basic mode")
PY
}

main() {
  choose_mode
  local hermes_home hermes_py
  hermes_home="$(infer_hermes_home)"
  export HERMES_HOME="$hermes_home"

  hermes_py="$(find_hermes_python)" || die "Could not find Hermes Python. Set HERMES_PYTHON=/path/to/hermes/python and rerun setup."

  log "Mode: $MODE"
  log "OS: $OS_TYPE"
  log "Plugin directory: $REPO_DIR"
  log "Hermes home: $HERMES_HOME"
  log "Hermes Python: $hermes_py"

  install_python_deps "$hermes_py"
  verify_python_deps "$hermes_py"

  if [[ "$MODE" == "full" ]]; then
    install_tesseract
    local tess
    tess="$(find_tesseract)" || die "Tesseract was not found after install."
    ok "Tesseract: $("$tess" --version 2>&1 | head -n 1)"
    ensure_tessdata "$tess" "$HERMES_HOME" "$hermes_py"
  else
    ok "Basic mode selected; OCR/Tesseract setup skipped."
  fi

  smoke_check "$hermes_py" "$MODE"

  cat <<DONE

Setup complete.

Next step:
  /reset

If you run Hermes Gateway:
  hermes gateway restart
DONE
}

main "$@"
