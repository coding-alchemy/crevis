#!/bin/bash

# Volcengine Ark - Modern Development Environment Setup (macOS/Linux)
# Uses uv to manage Python and dependencies automatically.

set -e

# Ensure we are working in the script directory context
cd "$(dirname "$0")"

echo "=================================================="
echo "   Initializing Ark Development Environment..."
echo "=================================================="
echo ""

# 1. Setup uv (Download if not present)
UV_CMD="uv"

if command -v uv &> /dev/null; then
    echo "[1/4] uv tool found in system PATH."
elif [ -f "./uv" ]; then
    echo "[1/4] uv tool found in current directory."
    UV_CMD="./uv"
else
    echo "[1/4] Downloading uv tool..."
    echo ""
    echo "Official installation guide: https://docs.astral.sh/uv/getting-started/installation/"
    echo ""
    
    # Install using official script
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Try to find where it was installed
    if [ -f "$HOME/.local/bin/uv" ]; then
        UV_CMD="$HOME/.local/bin/uv"
    elif [ -f "$HOME/.cargo/bin/uv" ]; then
        UV_CMD="$HOME/.cargo/bin/uv"
    else
        # Fallback: try to find it in path again (maybe added by script?)
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        if command -v uv &> /dev/null; then
            UV_CMD="uv"
        else
            echo "Error: uv installed but not found in common locations. Please restart your terminal."
            exit 1
        fi
    fi
fi

# 2. Create Virtual Environment
echo "[2/4] Creating virtual environment (.venv)..."
# Create .venv in project root (two levels up)
"$UV_CMD" venv ../../.venv --python 3.12

# 3. Install Dependencies
echo "[3/4] Installing SDK (volcengine-python-sdk[ark])..."
# Install into the specific venv
"$UV_CMD" pip install "volcengine-python-sdk[ark]" --python ../../.venv

# 4. Generate Launch Script
echo "[4/4] Generating run_demo.sh..."
cat <<EOF > ../../run_demo.sh
#!/bin/bash
cd "\$(dirname "\$0")"
# Activate the virtual environment
source .venv/bin/activate
python python/demo_standard.py
EOF

chmod +x ../../run_demo.sh

echo ""
echo "=================================================="
echo "   Setup Complete!"
echo "=================================================="
echo ""
echo "You can now run './run_demo.sh' in the project root to start."
echo "Or open this project in your preferred IDE (e.g., VS Code, PyCharm, Trae) and select '.venv' as your Python interpreter."
echo ""
