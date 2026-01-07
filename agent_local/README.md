# LocalPrinterAgent v4.0

WebSocket service para imprimir desde Odoo/POS en impresoras locales de Windows.

## 🚀 Inicio Rápido

### Requisitos
- Windows 7+
- Python 3.8+
- Permisos de Administrador

### Instalación en 3 pasos

1. **Abre PowerShell como Administrador** y ve a este directorio:
   ```powershell
   cd c:\Users\yoeli\Documents\Chefalitas\agent_local
   ```

2. **Ejecuta el script de instalación**:
   ```powershell
   python install.bat
   # O para PowerShell:
   .\install.ps1
   ```

3. **Sigue las instrucciones en la ventana GUI**:
   - Instalar dependencias
   - Instalar/Actualizar servicio
   - Abrir puerto (Firewall)
   - Iniciar servicio

## 📖 Documentación

- **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** - Guía completa paso a paso
- **[TECHNICAL_SUMMARY.md](TECHNICAL_SUMMARY.md)** - Detalles técnicos de las mejoras

## 🎯 Uso Desde Odoo

### WebSocket Endpoint
```
ws://127.0.0.1:9089
```

### Comandos

**Health Check**:
```json
{"command": "health"}
→ {"status": "success", "message": "Agent online"}
```

**Listar Impresoras**:
```json
{"command": "list_printers"}
→ {"status": "success", "printers": ["Impresora Térmica", "PDF"]}
```

**Imprimir Recibo**:
```json
{
  "command": "print_receipt",
  "printer_name": "Impresora Térmica",
  "data": "\x1B\x40...\x1B\x69"
}
→ {"status": "success", "message": "Print job sent."}
```

## 🔧 Controles

### Desde GUI
- Ejecuta: `python LocalPrinterAgent.py`
- Botones para: Instalar, Iniciar, Detener, Reiniciar, Eliminar servicio
- Ver logs en tiempo real

### Desde PowerShell (admin)
```powershell
python LocalPrinterAgent.py start
python LocalPrinterAgent.py stop
python LocalPrinterAgent.py remove
```

### Desde Windows Services
1. Presiona `Win + R`
2. Escribe: `services.msc`
3. Busca "LocalPrinterAgent"
4. Click derecho → Iniciar/Detener

## 📊 Monitoreo

**Ver estado**:
```powershell
sc query LocalPrinterAgent
```

**Ver logs**:
- `agent.log` - Errores del servicio
- `agent_gui.log` - Errores de la GUI

## ⚠️ Solución de Problemas

**Error 1053** (service did not respond):
→ Desinstala pywin32, reinstala y reconfigura el servicio

**Puerto en uso**:
→ Ejecuta GUI, cambia puerto a 9090, reinstala

**Impresora no listada**:
→ Verifica que esté instalada en Control Panel → Devices and Printers

Ver **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** para más opciones.

## 📝 Archivos

```
.
├── LocalPrinterAgent.py          # Servicio principal
├── install.bat                   # Script instalación (CMD)
├── install.ps1                   # Script instalación (PowerShell)
├── INSTALLATION_GUIDE.md         # Guía completa
├── TECHNICAL_SUMMARY.md          # Detalles técnicos
├── README.md                     # Este archivo
├── requirements.txt              # Dependencias Python
├── agent.log                     # Log del servicio (generado)
└── agent_gui.log                 # Log de GUI (generado)
```

## 🔐 Seguridad

- ✓ WebSocket sin SSL en red local (127.0.0.1 o LAN privada)
- ✗ NO para internet público (usar reverse proxy con SSL)

## 📞 Soporte

Revisa los archivos de documentación o los logs para más información.

---

**Versión**: 4.0 | **Status**: ✅ Listo | **Error 1053**: ✅ Resuelto
