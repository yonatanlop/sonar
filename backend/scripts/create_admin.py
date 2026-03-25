"""
Script de primer arranque: crea el usuario administrador inicial.

Uso (desde la carpeta sonar/):
    docker compose exec backend python scripts/create_admin.py

O con variables de entorno custom:
    ADMIN_USERNAME=admin ADMIN_PASSWORD=cambiar123 \
    docker compose exec backend python scripts/create_admin.py
"""
import os
import sys

sys.path.insert(0, "/app")

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User


def create_admin():
    username  = os.getenv("ADMIN_USERNAME", "admin")
    email     = os.getenv("ADMIN_EMAIL",    "admin@sonar.local")
    full_name = os.getenv("ADMIN_NAME",     "Administrador SONAR")
    password  = os.getenv("ADMIN_PASSWORD", "sonar2024!")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            print(f"El usuario '{username}' ya existe. No se creo nada.")
            return

        admin = User(
            username      = username,
            email         = email,
            full_name     = full_name,
            password_hash = hash_password(password),
            role          = "admin",
            active        = True,
        )
        db.add(admin)
        db.commit()

        print("=" * 50)
        print("Usuario administrador creado exitosamente")
        print(f"   Usuario:    {username}")
        print(f"   Contrasena: {password}")
        print(f"   Email:      {email}")
        print("=" * 50)
        print("Cambia la contrasena despues del primer login.")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
