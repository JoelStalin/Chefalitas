#!/usr/bin/env python
"""
LocalPrinterAgent Diagnostic Tool
Verifica que el entorno esté correctamente configurado
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def check_python():
    """Verificar versión de Python"""
    print("[*] Verificando Python...")
    print(f"    Versión: {sys.version}")
    print(f"    Ejecutable: {sys.executable}")
    
    if sys.version_info < (3, 8):
        print("    ❌ ALERTA: Se requiere Python 3.8+")
        return False
    print("    ✓ OK")
    return True


def check_windows():
    """Verificar que está en Windows"""
    print("\n[*] Verificando SO...")
    if os.name != 'nt':
        print(f"    ❌ ALERTA: Este script requiere Windows (actual: {os.name})")
        return False
    print(f"    ✓ Windows ({sys.platform})")
    return True


def check_admin():
    """Verificar permisos de admin"""
    print("\n[*] Verificando permisos...")
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if is_admin:
            print("    ✓ Ejecutando como Administrador")
            return True
        else:
            print("    ⚠ Ejecutando como Usuario (se requiere admin para instalar servicio)")
            return True
    except Exception as exc:
        print(f"    ⚠ No se pudo verificar: {exc}")
        return True


def check_module(name: str, import_name: str = None) -> bool:
    """Verificar si un módulo Python está instalado"""
    if import_name is None:
        import_name = name
    
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def check_dependencies():
    """Verificar dependencias Python"""
    print("\n[*] Verificando dependencias Python...")
    
    required = [
        ("websockets", "websockets"),
        ("pywin32", "win32print"),
    ]
    
    missing = []
    for pkg, mod in required:
        if check_module(mod):
            print(f"    ✓ {pkg}")
        else:
            print(f"    ❌ {pkg} (falta)")
            missing.append(pkg)
    
    if missing:
        print(f"\n    Para instalar: python -m pip install {' '.join(missing)}")
        return False
    return True


def check_port(port: int = 9089) -> bool:
    """Verificar si el puerto está disponible"""
    print(f"\n[*] Verificando puerto {port}...")
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('127.0.0.1', port))
            if result == 0:
                print(f"    ⚠ Puerto {port} está en uso")
                return False
            else:
                print(f"    ✓ Puerto {port} disponible")
                return True
    except Exception as exc:
        print(f"    ⚠ Error verificando puerto: {exc}")
        return True


def check_firewall_rule(port: int = 9089) -> bool:
    """Verificar si existe regla de firewall"""
    print(f"\n[*] Verificando regla Firewall para puerto {port}...")
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=LocalPrinterAgent"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and "LocalPrinterAgent" in result.stdout:
            print(f"    ✓ Regla de firewall existe")
            return True
        else:
            print(f"    ⚠ Regla de firewall no encontrada (puedes crear desde GUI)")
            return True
    except Exception as exc:
        print(f"    ⚠ Error verificando firewall: {exc}")
        return True


def check_service_status() -> str:
    """Verificar estado del servicio Windows"""
    print("\n[*] Verificando servicio LocalPrinterAgent...")
    try:
        result = subprocess.run(
            ["sc", "query", "LocalPrinterAgent"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print("    ⚠ Servicio no instalado")
            return "NOT_INSTALLED"
        
        if "RUNNING" in result.stdout:
            print("    ✓ Servicio RUNNING")
            return "RUNNING"
        elif "STOPPED" in result.stdout:
            print("    ⚠ Servicio STOPPED")
            return "STOPPED"
        else:
            print("    ⚠ Estado desconocido")
            return "UNKNOWN"
    except Exception as exc:
        print(f"    ⚠ Error: {exc}")
        return "ERROR"


def check_websocket_connectivity() -> bool:
    """Intentar conectar al WebSocket"""
    print("\n[*] Verificando conectividad WebSocket...")
    try:
        import asyncio
        import websockets
        
        async def test_ws():
            try:
                async with websockets.connect('ws://127.0.0.1:9089', timeout=2) as ws:
                    await ws.send('{"command": "health"}')
                    response = await ws.recv()
                    data = json.loads(response)
                    if data.get("status") == "success":
                        print("    ✓ WebSocket respondiendo")
                        return True
            except Exception:
                return False
        
        result = asyncio.run(test_ws())
        if not result:
            print("    ⚠ WebSocket no accesible (servicio no está corriendo)")
        return True
    except Exception as exc:
        print(f"    ⚠ Advertencia: {exc}")
        return True


def check_printers() -> bool:
    """Listar impresoras disponibles"""
    print("\n[*] Impresoras disponibles...")
    try:
        import win32print
        printers = [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )]
        
        if printers:
            for printer in printers:
                print(f"    ✓ {printer}")
            return True
        else:
            print("    ⚠ No se encontraron impresoras")
            return False
    except Exception as exc:
        print(f"    ⚠ Error: {exc}")
        return True


def check_config_file() -> bool:
    """Verificar archivo de configuración"""
    print("\n[*] Verificando archivo de configuración...")
    config_path = Path(__file__).parent / "service_config.json"
    
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            print(f"    ✓ Config encontrado")
            print(f"      Host: {config.get('host', 'N/A')}")
            print(f"      Port: {config.get('port', 'N/A')}")
            return True
        except Exception as exc:
            print(f"    ⚠ Error leyendo config: {exc}")
            return False
    else:
        print(f"    ℹ Config no existe (se generará al instalar)")
        return True


def check_logs() -> bool:
    """Verificar archivos de log"""
    print("\n[*] Archivos de log...")
    agent_log = Path(__file__).parent / "agent.log"
    gui_log = Path(__file__).parent / "agent_gui.log"
    
    if agent_log.exists():
        print(f"    ✓ agent.log ({agent_log.stat().st_size} bytes)")
    else:
        print(f"    ℹ agent.log no existe")
    
    if gui_log.exists():
        print(f"    ✓ agent_gui.log ({gui_log.stat().st_size} bytes)")
    else:
        print(f"    ℹ agent_gui.log no existe")
    
    return True


def main():
    print("\n" + "="*60)
    print("LocalPrinterAgent - Herramienta de Diagnóstico")
    print("="*60)
    
    results = {
        "Python": check_python(),
        "Windows": check_windows(),
        "Permisos": check_admin(),
        "Dependencias": check_dependencies(),
        "Puerto": check_port(),
        "Firewall": check_firewall_rule(),
        "Servicio": check_service_status() in ["RUNNING", "STOPPED", "NOT_INSTALLED"],
        "WebSocket": check_websocket_connectivity(),
        "Impresoras": check_printers(),
        "Config": check_config_file(),
        "Logs": check_logs(),
    }
    
    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    
    critical = ["Python", "Windows", "Dependencias"]
    
    for check, result in results.items():
        status = "✓ OK" if result else "❌ FALLO" if check in critical else "⚠ ALERTA"
        print(f"{check:.<30} {status}")
    
    print("="*60)
    
    all_critical_ok = all(results[k] for k in critical)
    if all_critical_ok:
        print("\n✅ Diagnóstico completado. Sistema listo para usar.")
        print("\nSiguientes pasos:")
        print("1. Ejecuta: python LocalPrinterAgent.py")
        print("2. En la GUI: Instalar/Actualizar servicio")
        print("3. En la GUI: Abrir puerto (Firewall)")
        print("4. En la GUI: Iniciar")
        return 0
    else:
        print("\n❌ Se encontraron problemas críticos. Ver arriba para detalles.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
