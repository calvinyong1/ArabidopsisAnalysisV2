#!/bin/bash

# ============================================================================
#  ChronoRoot macOS Installer (Conda-based)
# ============================================================================

set -e

# --- Visual Styling ---
BOLD='\033[1m'
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

section_title() { echo -e "\n${BOLD}--- $1 ---${NC}"; }
print_status()  { echo -e "${BLUE}[STATUS]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# --- Configuration ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_DIR="$HOME/Applications"
ENV_NAME="ChronoRoot"
ENV_FILE="$SCRIPT_DIR/environment.yml"

main() {
    clear
    echo -e "${BOLD}ChronoRoot macOS Installer${NC}"
    echo "============================================"
    echo ""

    # 1. System Info
    section_title "1. System Check"

    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        print_success "Apple Silicon (M-series) detected."
    else
        print_success "Intel Mac detected."
    fi
    print_warning "NVIDIA GPU acceleration is not available on macOS."
    print_status  "Segmentation will run on CPU. All analysis tools work normally."

    # 2. Conda Check / Auto-Install
    section_title "2. Conda Setup"

    if command_exists conda; then
        print_success "Conda already installed."
        CONDA_BASE=$(conda info --base)
    else
        print_warning "Conda not found. Installing Miniconda automatically..."

        if [ "$ARCH" = "arm64" ]; then
            MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
        else
            MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
        fi

        TMP_INSTALLER="/tmp/Miniconda3-installer.sh"
        print_status "Downloading Miniconda..."
        curl -fsSL "$MINICONDA_URL" -o "$TMP_INSTALLER"

        print_status "Installing Miniconda to ~/miniconda3 (silent)..."
        bash "$TMP_INSTALLER" -b -p "$HOME/miniconda3"
        rm -f "$TMP_INSTALLER"

        CONDA_BASE="$HOME/miniconda3"
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        conda init zsh bash >/dev/null 2>&1 || true

        print_success "Miniconda installed at $CONDA_BASE"
        print_warning "Restart your terminal after installation to use 'conda' globally."
    fi

    # Make conda available for the rest of this script
    source "$CONDA_BASE/etc/profile.d/conda.sh"

    # 3. Homebrew / libzbar
    section_title "3. System Dependencies"

    if command_exists brew; then
        print_success "Homebrew detected."
        if brew list zbar &>/dev/null; then
            print_success "libzbar already installed."
        else
            print_status "Installing libzbar (required for QR code detection)..."
            brew install zbar
        fi
    else
        print_warning "Homebrew not found — QR code reading (pyzbar) will not work."
        print_warning "Install Homebrew from https://brew.sh, then run: brew install zbar"
        read -p "Continue without QR support? [Y/n]: " proceed
        [[ $proceed =~ ^[Nn]$ ]] && exit 1
    fi

    # 4. Conda Environment
    section_title "4. Conda Environment Setup"

    if [ ! -f "$ENV_FILE" ]; then
        print_error "environment.yml not found at: $ENV_FILE"
        exit 1
    fi

    if conda env list | grep -q "$ENV_NAME"; then
        print_status "Updating existing environment ($ENV_NAME)..."
        conda env update -n "$ENV_NAME" -f "$ENV_FILE" --prune
    else
        print_status "Creating environment ($ENV_NAME) — this may take several minutes..."
        conda env create -n "$ENV_NAME" -f "$ENV_FILE"
    fi

    print_success "Environment '$ENV_NAME' is ready."

    # 5. Download Model Weights
    section_title "5. Downloading Segmentation Weights"

    WEIGHTS_SCRIPT="$SCRIPT_DIR/segmentationApp/download_weights.sh"

    if [ -f "$WEIGHTS_SCRIPT" ]; then
        chmod +x "$WEIGHTS_SCRIPT"
        print_status "Syncing models from Hugging Face..."
        conda run --no-capture-output -n "$ENV_NAME" /bin/bash "$WEIGHTS_SCRIPT"
        print_success "Model weights downloaded."
    else
        print_warning "download_weights.sh not found at expected path. Skipping."
    fi

    # 6. Create macOS .app Launchers
    section_title "6. Creating App Launchers"

    mkdir -p "$APP_DIR"

    # Resolve the Python binary directly — avoids conda activate issues in .app context
    PYTHON_BIN="$CONDA_BASE/envs/$ENV_NAME/bin/python"

    create_mac_app() {
        local display_name="$1"   # e.g. "ChronoRoot Analysis"
        local app_script_dir="$2" # Directory containing run.py
        local exec_name="${display_name// /}"  # Strip spaces for the macOS executable
        local bundle_id="com.chronoroot.$(echo "$display_name" | tr ' ' '.' | tr '[:upper:]' '[:lower:]')"
        local app_path="$APP_DIR/${display_name}.app"
        local macos_dir="$app_path/Contents/MacOS"

        mkdir -p "$macos_dir"

        # Executable: sets up env vars and launches the Python GUI
        cat > "$macos_dir/$exec_name" << EXECEOF
#!/bin/bash
# Make Homebrew libraries findable (libzbar, etc.)
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:\${DYLD_LIBRARY_PATH}"
export QT_LOGGING_RULES='*=false'

cd "$app_script_dir"
exec "$PYTHON_BIN" run.py
EXECEOF
        chmod +x "$macos_dir/$exec_name"

        # Info.plist — tells macOS this is a GUI app
        cat > "$app_path/Contents/Info.plist" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$display_name</string>
    <key>CFBundleDisplayName</key>
    <string>$display_name</string>
    <key>CFBundleExecutable</key>
    <string>$exec_name</string>
    <key>CFBundleIdentifier</key>
    <string>$bundle_id</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLISTEOF

        # Desktop alias — symlink so the app appears on the Desktop
        ln -sf "$app_path" "$HOME/Desktop/${display_name}.app"

        print_success "Created: ${display_name}.app → $APP_DIR"
        print_success "Desktop shortcut: ~/Desktop/${display_name}.app"
    }

    create_mac_app "ChronoRoot Analysis"     "$SCRIPT_DIR/singlePlantAnalysis"
    create_mac_app "ChronoRoot Segmentation" "$SCRIPT_DIR/segmentationApp"

    # 7. Done
    section_title "Installation Complete"
    print_success "ChronoRoot is ready!"
    echo ""
    echo "  Apps installed in: $APP_DIR"
    echo "  - ChronoRoot Analysis.app"
    echo "  - ChronoRoot Segmentation.app"
    echo ""
    echo "  Desktop shortcuts added to: ~/Desktop"
    echo ""
    echo -e "${YELLOW}First launch — Gatekeeper:${NC}"
    echo "  macOS will block unsigned apps. To open:"
    echo "  Right-click the app → Open → Open"
    echo ""
    echo -e "${YELLOW}Note on GPU:${NC}"
    echo "  Segmentation runs on CPU on macOS (no CUDA support)."
    echo "  For GPU-accelerated segmentation, use the Linux installer on a CUDA machine."
}

main "$@"
