"""
Script para agregar cuentas de Twitter/X al pool de twscrape.

Modo 1 — Cookies desde navegador (RECOMENDADO cuando el login por contraseña
          es bloqueado por Cloudflare desde un servidor/Docker):

    1. Entra a twitter.com en Chrome/Edge con tu cuenta
    2. Instala la extensión "Cookie-Editor"
    3. Clic en Export → "Export as JSON" → pega el resultado en twitter_cookies.json
    4. Copia el archivo al contenedor:
         docker compose cp twitter_cookies.json backend:/app/storage/twitter_cookies.json
    5. Ejecuta:
         docker compose exec backend python scripts/add_twitter_account.py \\
           --username TU_USUARIO \\
           --email TU@EMAIL.COM \\
           --password TU_CONTRASEÑA \\
           --cookies /app/storage/twitter_cookies.json

Modo 2 — Usuario y contraseña (puede ser bloqueado por Cloudflare desde Docker):

    docker compose exec backend python scripts/add_twitter_account.py \\
      --username TU_USUARIO \\
      --email TU@EMAIL.COM \\
      --password TU_CONTRASEÑA_TWITTER \\
      --email-password TU_CONTRASEÑA_EMAIL

Notas importantes:
    - Usa cuentas de Twitter/X reales (pueden ser cuentas secundarias creadas para esto)
    - Agrega 2-3 cuentas para distribuir los rate limits y mayor estabilidad
    - Las credenciales se almacenan cifradas en: /app/storage/twscrape.db
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, "/app")


async def add_account(
    username: str,
    email: str,
    password: str,
    email_password: str,
    db_path: str,
    cookies: str | None = None,
) -> bool:
    try:
        from twscrape import API
    except ImportError:
        print("ERROR: twscrape no está instalado.")
        print("Verifica que esté en requirements.txt y reconstruye la imagen:")
        print("  docker compose build backend")
        return False

    api = API(db_path)

    print(f"\nAgregando cuenta: @{username} ({email})")
    if cookies:
        print("  Modo: cookies de navegador")
    else:
        print("  Modo: usuario/contraseña")

    try:
        kwargs = dict(
            username=username,
            email=email,
            password=password,
            email_password=email_password,
        )
        if cookies:
            kwargs["cookies"] = cookies
        await api.pool.add_account(**kwargs)
        print("Cuenta agregada al pool.")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"La cuenta @{username} ya existe en el pool. Actualizando cookies...")
            # Si ya existe, intentar actualizar las cookies directamente
            if cookies:
                try:
                    accounts = await api.pool.get_all()
                    for acc in accounts:
                        if acc.username.lower() == username.lower().lstrip("@"):
                            acc.cookies = cookies
                            await api.pool.save(acc)
                            print("Cookies actualizadas en cuenta existente.")
                            break
                except Exception as ue:
                    print(f"No se pudo actualizar cookies: {ue}")
        else:
            print(f"Error al agregar cuenta: {e}")
            return False

    # Si se proveyeron cookies, no hacer login_all (ya está autenticada)
    if cookies:
        print("\nCuenta agregada con cookies — no se requiere login adicional.")
        accounts = await api.pool.get_all()
        print(f"\n{'='*50}")
        print(f"Pool de cuentas: {len(accounts)} total(es)")
        for acc in accounts:
            estado = "✓ Con cookies" if getattr(acc, "cookies", None) else "? Sin cookies"
            print(f"  {estado} — @{acc.username}")
        print(f"{'='*50}")
        return True

    # Modo contraseña: intentar login para verificar
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
        tiene_cookies = "🍪 cookies" if getattr(acc, "cookies", None) else "  sin cookies"
        estado = "✓ Activa" if getattr(acc, "active", True) else "✗ Inactiva"
        print(f"  {estado} [{tiene_cookies}] — @{acc.username} ({acc.email})")


def _load_cookies_file(path: str) -> str:
    """Lee un archivo de cookies (JSON array de Cookie-Editor) y lo devuelve como string."""
    if not os.path.exists(path):
        print(f"ERROR: No se encontró el archivo de cookies: {path}")
        print("  Cópialo al contenedor con:")
        print(f"    docker compose cp tu_cookies.json backend:{path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = f.read().strip()
    # Validar que es JSON válido
    try:
        json.loads(data)
    except json.JSONDecodeError as e:
        print(f"ERROR: El archivo de cookies no es JSON válido: {e}")
        print("  Asegúrate de exportar con 'Cookie-Editor' → 'Export as JSON'")
        sys.exit(1)
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Gestión de cuentas Twitter/X para SONAR"
    )
    parser.add_argument("--username",       default=os.getenv("TW_USERNAME",       ""))
    parser.add_argument("--email",          default=os.getenv("TW_EMAIL",          ""))
    parser.add_argument("--password",       default=os.getenv("TW_PASSWORD",       ""))
    parser.add_argument("--email-password", default=os.getenv("TW_EMAIL_PASSWORD", ""),
                        dest="email_password",
                        help="Contraseña del correo electrónico (puede ser igual a --password)")
    parser.add_argument("--cookies",        default=os.getenv("TW_COOKIES_FILE",   ""),
                        help="Ruta al archivo JSON de cookies exportado desde el navegador")
    parser.add_argument("--list",           action="store_true",
                        help="Listar cuentas configuradas")
    parser.add_argument("--db",             default="/app/storage/twscrape.db",
                        help="Ruta a la DB de cuentas")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_accounts(args.db))
        return

    if not all([args.username, args.email, args.password]):
        print("\nFaltan credenciales. Opciones disponibles:")
        print()
        print("  RECOMENDADO — Con cookies (evita bloqueo de Cloudflare):")
        print("     python scripts/add_twitter_account.py \\")
        print("       --username TU_USUARIO \\")
        print("       --email TU@EMAIL.COM \\")
        print("       --password TU_CONTRASEÑA \\")
        print("       --cookies /app/storage/twitter_cookies.json")
        print()
        print("  ALTERNATIVO — Usuario/contraseña:")
        print("     python scripts/add_twitter_account.py \\")
        print("       --username TU_USUARIO \\")
        print("       --email TU@EMAIL.COM \\")
        print("       --password TU_CONTRASEÑA_TWITTER \\")
        print("       --email-password TU_CONTRASEÑA_EMAIL")
        print()
        print("  INTERACTIVO:")
        username = input("    Username de Twitter: ").strip()
        email    = input("    Email:               ").strip()
        import getpass
        password       = getpass.getpass("    Contraseña de Twitter:                          ")
        email_password = getpass.getpass("    Contraseña del email (Enter = igual a anterior): ")
        if not email_password:
            email_password = password
        cookies_path   = input("    Ruta al archivo cookies.json (Enter = omitir): ").strip()

        if not all([username, email, password]):
            print("ERROR: Username, email y contraseña son obligatorios.")
            sys.exit(1)

        args.username       = username
        args.email          = email
        args.password       = password
        args.email_password = email_password
        args.cookies        = cookies_path

    cookies_str = None
    if args.cookies:
        cookies_str = _load_cookies_file(args.cookies)
        print(f"Cookies cargadas desde: {args.cookies}")

    email_password = getattr(args, "email_password", None) or args.password

    success = asyncio.run(add_account(
        username=args.username,
        email=args.email,
        password=args.password,
        email_password=email_password,
        db_path=args.db,
        cookies=cookies_str,
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
