#!/bin/bash

# Crevis - Python 依赖安装脚本
# 安装项目所需的第三方 Python 包

set -e

echo "=================================================="
echo "   Installing Crevis Python Dependencies..."
echo "=================================================="
echo ""

# 检查虚拟环境
if [ -z "$VIRTUAL_ENV" ]; then
    # 尝试自动检测项目根目录的 .venv
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        echo "Auto-detected virtual environment at $PROJECT_ROOT/.venv"
        source "$PROJECT_ROOT/.venv/bin/activate"
    else
        echo "Warning: No active virtual environment detected."
        echo "It's recommended to activate .venv first:"
        echo "  source .venv/bin/activate"
        echo ""
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# 确保虚拟环境有 pip
if ! python -m pip --version > /dev/null 2>&1; then
    echo "Installing pip into virtual environment..."
    python -m ensurepip --upgrade
fi

# 安装依赖
echo "Installing dependencies..."
python -m pip install "volcengine-python-sdk[ark]" "PyYAML"

echo ""
echo "=================================================="
echo "   Dependencies installed successfully!"
echo "=================================================="