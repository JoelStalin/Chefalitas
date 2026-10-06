FROM odoo:20.0
USER root
# Python deps of the Chefalitas addons (l10n_do_accounting_report needs pycountry).
# No "|| true": a failed install must fail the build instead of shipping a broken image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    && pip3 install --no-cache-dir --break-system-packages pycountry phonenumbers requests \
    && rm -rf /var/lib/apt/lists/*
USER odoo
