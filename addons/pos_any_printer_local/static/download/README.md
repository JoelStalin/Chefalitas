
# Cómo Compilar el Instalador del Agente de Impresión Local

Este directorio está destinado a alojar el instalador final `LocalPrinterAgent-Setup.exe`.

Debido a que el proceso de compilación requiere herramientas específicas de Windows (PyInstaller e Inno Setup), no puede ser generado automáticamente por el agente de desarrollo. Siga estos pasos para compilarlo manualmente.

## Prerrequisitos

Asegúrese de tener lo siguiente instalado en su entorno de desarrollo de Windows:

1.  **Python**: [Descargar Python](https://www.python.org/downloads/)
2.  **PyInstaller**: `pip install pyinstaller`
3.  **Inno Setup**: [Descargar Inno Setup](https://jrsoftware.org/isinfo.php)

## Pasos para la Compilación

1.  **Navegue al Directorio del Agente**:
    Abra una terminal (como PowerShell o CMD) y navegue hasta el directorio `agent_local` que se encuentra en la raíz del repositorio.

2.  **Compile el Agente con PyInstaller**:
    Ejecute el siguiente comando para convertir el script `agent.py` en un ejecutable de Windows que no muestra una consola.

    ```sh
    pyinstaller --onefile --windowed --name=LocalPrinterAgent agent.py
    ```

    *   `--onefile`: Empaqueta todo en un único archivo `.exe`.
    *   `--windowed`: Evita que se abra una ventana de consola al ejecutar el agente.
    *   `--name`: Establece el nombre del archivo de salida.

    Esto creará un directorio `dist` dentro de `agent_local`, que contendrá el archivo `LocalPrinterAgent.exe`.

3.  **Compile el Instalador con Inno Setup**:
    a. Abra la aplicación **Inno Setup Compiler**.
    b. Vaya a `File > Open...` y seleccione el script `installer.iss` ubicado en el directorio `agent_local`.
    c. Vaya a `Build > Compile` (o presione `F9`).

    Inno Setup tomará el `LocalPrinterAgent.exe` del directorio `dist` y generará el instalador final, `LocalPrinterAgent-Setup.exe`, en el directorio `agent_local`.

4.  **Coloque el Instalador en este Directorio**:
    a. Copie el archivo `LocalPrinterAgent-Setup.exe` recién creado desde el directorio `agent_local`.
    b. Pegue el archivo en **este directorio** (`addons/pos_any_printer_local/static/download/`).

Una vez que el archivo esté aquí, el botón "Descargar Agente (Windows)" en la configuración del TPV de Odoo funcionará correctamente.
