"""Cadenas activas. Es la única lista: las demás (Vea, Disco, La Anónima) se descartaron, sus datos
viejos siguen en precios.db pero el catálogo, el matching y las alertas los ignoran."""
ACTIVE_CHAINS = ["carrefour", "coto", "jumbo", "lagallega", "dar"]
SQL_IN = "(" + ",".join(f"'{c}'" for c in ACTIVE_CHAINS) + ")"
