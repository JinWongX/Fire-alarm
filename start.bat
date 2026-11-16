@echo off
chcp 65001 >nul
echo ==========================================
echo  消防报警联动控制系统 - 一键启动
echo ==========================================
cd /d "%~dp0"

start "fire-alarm-backend" cmd /k "cd backend && python -m uvicorn app.main:app --port 8000"
echo 后端已启动: http://localhost:8000/docs

cd /d "%~dp0"
if not exist frontend\node_modules ( echo 首次运行: 正在安装前端依赖... & cd frontend && call npm install & cd .. )
start "fire-alarm-frontend" cmd /k "cd frontend && npm run dev"
echo 前端已启动: http://localhost:5173

echo.
echo 演示账号(密码均为 123456):
echo   消防主管 admin | 消防值班员 duty | 维保人员 maintain
echo ==========================================
pause