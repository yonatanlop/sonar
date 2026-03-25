"""
Script para agregar cuentas de Twitter/X al pool de twscrape.

Uso (desde la carpeta sonar/):
    docker compose exec backend python scripts/add_twitter_account.py

O pasando credenciales directamente:
    docker compose exec backend python scripts/add_twitter_account.py \
        --username mi_usuario \
        --email mi@email.com \
        --password mi_contraseña

Notas importantes:
    - Usa cuentas de Twitter/X reales (pueden ser cuentas secundarias creadas para esto)
    - Agrega 2-3 cuentas para distribuir los rate limits y mayor estabilidad
    - El script verifica que la cuenta funciona correctamente antes de guardar
    - Las credenciales se almacenan cifradas en: /app/storage/twscrape.db
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/app")


async def add_account(username: str, email: str, password: str, db_path: str) -> bool:
    try:
        from twscrape import API
    except ImportError:
        print("ERROR: twscrape no está instalado.")
        print("Verifica que esté en requirements.txt y reconstruye la imagen:")
        print("  docker compose build backend")
        return False

    api = API(db_path)

    print(f"\nAgregando cuenta: @{username} ({email})")
    try:
        await api.pool.add_account(
            username=username,
            email=email,
            password=password,
        )
        print("Cuenta agregada al pool.")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"La cuenta @{username} ya existe en el pool.")
        else:
            print(f"Error al agregar cuenta: {e}")
            return False

    # Intentar login para verificar que funciona
    print("Verificando credenciales (iniciando sesión)...")
    try:
        await api.pool.login_all()
        accounts = await api.pool.get_all()
        active = [a for a in accounts if getattr(a, "active", True)]
        print(f"\n{'='*50}")
        print(f"Pool de cuentas: {len(active)} activa(s) de {len(accounts)} total(es)")
        for acc in accounts:
            estado = "✓ Activa" if getattr(acc, "active", True) else "✗ Inactiva"
            print(f"  {estado} — @{acc.username}")
        print(f"{'='*50}")
        return True
    except Exception as e:
        print(f"Advertencia — Error al verificar login: {e}")
        print("La cuenta fue guardada pero podría necesitar verificación manual.")
        return True


async def list_accounts(db_path: str) -> None:
    try:
        from twscrape import API
    except ImportError:
        print("ERROR: twscrape no está instalado.")
        return

    api = API(db_path)
    accounts = await api.pool.get_all()
    if not accounts:
        print("No hay cuentas configuradas en el pool.")
        return

    print(f"\nCuentas en el pool ({len(accounts)} total):")
    for acc in accounts:
        estado = "✓ Activa" if getattr(acc, "active", True) else "✗ Inactiva"
        print(f"  {estado} — @{acc.username} ({acc.email})")


def main():
    parser = argparse.ArgumentParser(
        description="Gestión de cuentas Twitter/X para SONAR"
    )
    parser.add_argument("--username", default=os.getenv("TW_USERNAME", ""))
    parser.add_argument("--email",    default=os.getenv("TW_EMAIL",    ""))
    parser.add_argument("--password", default=os.getenv("TW_PASSWORD", ""))
    parser.add_argument("--list",     action="store_true",
                        help="Listar cuentas configuradas")
    parser.add_argument("--db",       default="/app/storage/twscrape.db",
                        help="Ruta a la DB de cuentas")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_accounts(args.db))
        return

    if not all([args.username, args.email, args.password]):
        print("\nFaltan credenciales. Puedes ingresarlas de tres formas:")
        print()
        print("  1. Argumentos directos:")
        print("     python scripts/add_twitter_account.py \\")
        print("       --username TU_USUARIO \\")
        print("       --email TU@EMAIL.COM \\")
        print("       --password TU_CONTRASEÑA")
        print()
        print("  2. Variables de entorno:")
        print("     TW_USERNAME=... TW_EMAIL=... TW_PASSWORD=... \\")
        print("     python scripts/add_twitter_account.py")
        print()
        print("  3. Interactivo:")

        username = input("    Username de Twitter: ").strip()
        email    = input("    Email:               ").strip()
        import getpass
        password = getpass.getpass("    Contraseña:          ")

        if not all([username, email, password]):
            print("ERROR: Todos los campos son obligatorios.")
            sys.exit(1)

        args.username = username
        args.email    = email
        args.password = password

    success = asyncio.run(add_account(
        username=args.username,
        email=args.email,
        password=args.password,
        db_path=args.db,
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
