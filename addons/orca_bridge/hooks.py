import hashlib
import logging
import secrets

_logger = logging.getLogger(__name__)

# SHA-256 of the token that was committed to the public repository (commit b36ff86).
LEAKED_TOKEN_SHA256 = "4794eff7912b2f31da9ae91dabe9dffbfdeebb9ff6e8daa44ea13431735e41cd"


def ensure_api_token(env):
    """Give orca.api_token a random value if it is missing or is the leaked public token."""
    params = env["ir.config_parameter"].sudo()
    current = params.get_str("orca.api_token") or ""
    if current and hashlib.sha256(current.encode()).hexdigest() != LEAKED_TOKEN_SHA256:
        return False
    params.set_str("orca.api_token", secrets.token_urlsafe(32))
    _logger.warning(
        "orca_bridge: orca.api_token %s; a new random token was generated. "
        "Update the ORCA client configuration (Settings > Technical > System Parameters).",
        "was the leaked public token" if current else "was not set",
    )
    return True


def post_init_hook(env):
    ensure_api_token(env)
