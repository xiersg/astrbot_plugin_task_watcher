@echo off
chcp 65001 >nul
echo ========================================
echo TaskWatcher 快速修复脚本
echo ========================================
echo.

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python
    pause
    exit /b 1
)
echo [OK] Python 环境正常
echo.

echo [2/3] 安装/更新依赖...
echo 正在安装: aiohttp, PyYAML...
python -m pip install --upgrade aiohttp>=3.8.0 PyYAML>=6.0
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [OK] 依赖安装成功
echo.

echo [3/3] 验证模块导入...
python -c "import aiohttp; print(f'aiohttp version: {aiohttp.__version__}')"
python -c "import yaml; print(f'PyYAML version: {yaml.__version__}')"
if %errorlevel% neq 0 (
    echo [错误] 模块验证失败
    pause
    exit /b 1
)
echo [OK] 模块导入成功
echo.

echo ========================================
echo 修复完成！
echo ========================================
echo.
echo 下一步:
echo 1. 重启 AstrBot
echo 2. 尝试加载 TaskWatcher 插件
echo 3. 查看日志确认是否加载成功
echo.
pause