# Chefalitas Odoo Deployment

Este repositorio contiene la configuración necesaria para desplegar una instancia de Odoo 18 junto con sus servicios auxiliares. Además de PostgreSQL y pgAdmin, ahora incluye un **reverse proxy Nginx** con integración de **Certbot** para gestionar certificados SSL de *chefalitas.com.do*.

## Servicios incluidos

- **Odoo** 18.0 (aplicación principal)
- **PostgreSQL** 15 con configuración personalizable en `postgres-config/`
- **pgAdmin** para la administración de la base de datos
- **Nginx** como reverse proxy para los dominios `chefalitas.com.do`, `www.chefalitas.com.do` y `test.chefalitas.com.do`
- **Certbot** para emisión y renovación automática de certificados SSL

## Estructura de carpetas relevante

```
nginx/
├── conf.d/                 # Archivos de configuración de los servidores virtuales
│   └── chefalitas.conf     # Configuración base para HTTP/HTTPS
├── html/                   # Raíz web para los desafíos HTTP-01 de Certbot
│   └── .well-known/...
└── ssl/                    # Certificados emitidos por Let's Encrypt (se genera al solicitar SSL)
```

Los archivos en `nginx/` funcionan de forma similar a los de `postgres-config/`, permitiendo modificar la configuración sin construir nuevas imágenes Docker.

## Puesta en marcha

1. Copia el archivo `.env` de ejemplo (si corresponde) y actualiza las credenciales de la base de datos y servicios.
2. Levanta la infraestructura básica:

   ```bash
   docker compose up -d db odoo pgadmin nginx certbot
   ```

   Nginx publicará Odoo en los puertos 80 y 443 del host. Por defecto, `test.chefalitas.com.do` funciona únicamente sobre HTTP.

## Configurar certificados SSL con Certbot

1. **Solicitar los certificados iniciales**. Ejecuta el siguiente comando (sustituye el correo electrónico por el tuyo):

   ```bash
   docker compose run --rm certbot certonly \
     --webroot -w /var/www/certbot \
     --email tu-correo@ejemplo.com \
     --agree-tos --no-eff-email \
     -d chefalitas.com.do -d www.chefalitas.com.do
   ```

   El dominio `test.chefalitas.com.do` no requiere SSL y queda servido solamente por HTTP.

2. **Recargar Nginx** para que tome los certificados una vez emitidos:

   ```bash
   docker compose exec nginx nginx -s reload
   ```

3. **Renovación automática**. El servicio `certbot` corre en segundo plano ejecutando `certbot renew` cada 12 horas. Asegúrate de mantener los puertos 80/443 abiertos y de que el dominio apunte al servidor.

4. (Opcional) Tras confirmar que el certificado funciona correctamente, puedes añadir redirecciones de HTTP a HTTPS en `nginx/conf.d/chefalitas.conf` según tus necesidades.

## Deploy automático con GitHub Actions

El workflow `.github/workflows/deploy.yml` copia todo el contenido del repositorio al directorio `~/odoo18/` del servidor y ejecuta `restart.sh`, que se encarga de recrear los contenedores.

Asegúrate de definir los siguientes *secrets* en el repositorio de GitHub:

- `PROD_SSH_HOST` – IP o dominio del servidor de producción
- `PROD_SSH_USER` – Usuario con permisos SSH
- `PROD_SSH_KEY` – Llave privada en formato PEM para la autenticación

## Reinicio manual

En el servidor, puedes ejecutar el script de reinicio en cualquier momento:

```bash
cd ~/odoo18
./restart.sh
```

El script detiene y levanta los contenedores, instala dependencias Python de los módulos personalizados y reinicia los servicios para aplicar cambios.
