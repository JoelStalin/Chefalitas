# Chefalitas Odoo Deployment

Este repositorio prepara una instancia de **Odoo 18** junto con PostgreSQL, pgAdmin y un *reverse proxy* **Nginx + Certbot**. El objetivo es poder desplegar `chefalitas.com.do` (y su alias `www.chefalitas.com.do`), comenzando con HTTP puro para emitir los certificados y luego activando HTTPS.

## Servicios incluidos

- **Odoo 18.0** – aplicación principal
- **PostgreSQL 15** – base de datos
- **pgAdmin 4** – administración de PostgreSQL
- **Nginx** – *reverse proxy* para publicar Odoo
- **Certbot** – emisión y renovación automática de certificados SSL

## Estructura relevante

```
nginx/
├── conf.d/
│   └── chefalitas.com.do.conf   # Configuración activa de Nginx (fase HTTP por defecto)
├── html/                             # Webroot para los retos HTTP-01 de Let's Encrypt
└── templates/
    └── chefalitas.com.do.https.conf  # Versión HTTPS para usar después de emitir el certificado
```

Los archivos en `nginx/` se montan como volúmenes dentro del contenedor, por lo que cualquier cambio se refleja tras recargar Nginx.

## Nota sobre la imagen de Odoo

El servicio `odoo` ahora se construye con `odoo/Dockerfile` para aplicar un fix reproducible en el archivo
`/usr/lib/python3/dist-packages/odoo/addons/base/data/res_lang_data.xml`. Este patch ajusta el `url_code`
de `base.lang_es_419` a `es-419` y evita el choque con `es` durante la carga del modulo `base` en bases nuevas.
Ademas instala `addons/requirements.txt` en build para evitar `pip install` en runtime.

## Puesta en marcha básica

1. Copia el `.env` correspondiente y define las variables para Odoo, PostgreSQL y pgAdmin.
2. Levanta los servicios base:

   ```bash
   docker compose up -d db odoo pgadmin nginx certbot
   ```

3. (Firewall opcional) Si el servidor utiliza **UFW**, abre HTTP y HTTPS para Nginx:

   ```bash
   sudo ufw allow 'Nginx Full'
   sudo ufw reload
   ```

## Fase 1 – Servir únicamente HTTP

La configuración por defecto `nginx/conf.d/chefalitas.com.do.conf` expone Odoo en HTTP y permite que Certbot valide el reto `HTTP-01`.

1. Confirma que el contenedor Nginx está corriendo y que la configuración es válida:

   ```bash
   docker compose up -d nginx
   docker compose exec nginx nginx -t
   docker compose exec nginx nginx -s reload
   ```

2. Comprueba desde el servidor que el dominio responde por el puerto 80:

   ```bash
   curl -I http://chefalitas.com.do/
   ```

## Emitir el certificado para `chefalitas.com.do`

Con la fase HTTP operativa, ejecuta el siguiente comando una sola vez para emitir el certificado inicial:

```bash
docker compose run --rm \
  --entrypoint certbot \
  certbot \
  certonly \
    --webroot -w /var/www/certbot \
    --email administecion@chefalitas.com.do \
    --agree-tos --no-eff-email \
    -d chefalitas.com.do \
    -d www.chefalitas.com.do
```

> Ajusta el correo si es necesario. Tras un resultado exitoso verás el mensaje `Successfully received certificate` y los archivos se guardarán en `nginx/ssl/`.

Puedes confirmar que el certificado quedó registrado dentro del volumen ejecutando:

```bash
docker compose run --rm \
  --entrypoint certbot \
  certbot \
  certificates
```

En la salida deberías ver `Certificate Name: chefalitas.com.do` junto con las rutas `fullchain.pem` y `privkey.pem`.

## Fase 2 – Activar HTTPS

1. Copia la versión final de la configuración desde `nginx/templates/chefalitas.com.do.https.conf` y reemplaza el contenido de `nginx/conf.d/chefalitas.com.do.conf`. Esta versión usa la sintaxis moderna `http2 on;` y **no** incluye archivos externos como `options-ssl-nginx.conf` para evitar errores de arranque dentro del contenedor base.
2. Recarga Nginx para aplicar los cambios:

   ```bash
   docker compose exec nginx nginx -t
   docker compose exec nginx nginx -s reload
   ```

En esta fase Nginx redirige todo el tráfico HTTP a HTTPS y usa los certificados emitidos por Certbot para `chefalitas.com.do` y `www.chefalitas.com.do`.

## Renovación automática

El contenedor `certbot` ejecuta `certbot renew` cada 12 horas. Mientras los puertos 80/443 sigan accesibles y los dominios apunten al servidor, la renovación será automática. Los certificados renovados se guardan nuevamente bajo `nginx/ssl/`.

## Respaldos y restauración

En el directorio `backups/` encontrarás dos scripts para crear y recuperar respaldos completos de la instancia:

- `backup_odoo18.sh` genera tres archivos comprimidos con los volúmenes de PostgreSQL y Odoo, además de un `pg_dumpall` lógico. Solo mantiene la copia más reciente para evitar acumular archivos.
- `restore_odoo18.sh` toma el respaldo más nuevo disponible y restaura los volúmenes y la base de datos.

### Crear un respaldo manual

```bash
cd ~/odoo18/backups
./backup_odoo18.sh
```

> Asegúrate de que el contenedor de base de datos se llame `odoo18-db-1` (o ajusta `PG_CONTAINER` en el script) y que los volúmenes definidos coincidan con tu despliegue.

### Restaurar el último respaldo disponible

```bash
cd ~/odoo18/backups
./restore_odoo18.sh
```

El script detendrá los servicios, limpiará los volúmenes y aplicará el `pg_dumpall` comprimido. Verifica nuevamente el nombre del contenedor de PostgreSQL (`PG_CONTAINER`) y el usuario (`PG_USER`) si difieren de la configuración por defecto.

## Deploy automático con GitHub Actions

El workflow `.github/workflows/deploy.yml` sincroniza el repositorio con `~/odoo18/` en el servidor remoto y ejecuta `restart.sh` para recrear los contenedores tras cada *push* a la rama `main`.

Configura los siguientes **secrets** en GitHub:

- `PROD_SSH_HOST` – IP o dominio del servidor
- `PROD_SSH_USER` – Usuario SSH con permisos suficientes
- `PROD_SSH_KEY` – Llave privada (formato PEM) para la conexión

## Reinicio manual

En el servidor puedes reiniciar la pila en cualquier momento:

```bash
cd ~/odoo18/
./restart.sh
```

El script detiene y vuelve a crear los contenedores, instala dependencias Python de los módulos personalizados y aplica los cambios pendientes.
