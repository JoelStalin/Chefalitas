docker compose down
docker compose up  -d
docker exec -it -u root odoo18-odoo-1 bash -c "
  cd /mnt/extra-addons &&
  pip3 install --break-system-packages -r requirements.txt
"
docker compose restart
