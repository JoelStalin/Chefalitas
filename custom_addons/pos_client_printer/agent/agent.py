import json
import time

import requests
import win32print
import win32ui

CONFIG_FILE = 'C:/Program Files/PosAgent/config.json'


def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as file_handle:
        return json.load(file_handle)


def get_jobs(server_url, printer_id, token):
    response = requests.post(
        f'{server_url}/pos_client_printer/get_jobs',
        json={'printer_id': printer_id, 'token': token},
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get('jobs', [])


def print_receipt(html_content):
    printer_name = win32print.GetDefaultPrinter()
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    hdc.StartDoc('POS Ticket')
    hdc.StartPage()
    hdc.TextOut(100, 100, 'Ticket de ejemplo')
    hdc.EndPage()
    hdc.EndDoc()


def main():
    config = load_config()
    while True:
        try:
            jobs = get_jobs(config['server_url'], config['printer_id'], config['token'])
            for job in jobs:
                print_receipt(job['receipt_html'])
                requests.post(
                    f"{config['server_url']}/pos_client_printer/confirm_print",
                    json={'order_id': job['order_id']},
                    timeout=10,
                )
        except Exception as exc:  # noqa: BLE001
            with open('C:/Program Files/PosAgent/agent.log', 'a', encoding='utf-8') as log:
                log.write(f"Error: {exc}\n")
        time.sleep(5)


if __name__ == '__main__':
    main()
