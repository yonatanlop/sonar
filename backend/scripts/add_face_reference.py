"""
Script para agregar fotos de referencia facial para el Módulo 7 — Reconocimiento Visual.

Las fotos se usan para identificar visualmente a personas en imágenes de menciones
de Twitter/X, YouTube y noticias RSS.

Uso (desde la carpeta sonar/):

  Con URL pública:
    docker compose exec backend python scripts/add_face_reference.py \\
        --entity-id <UUID> \\
        --person "Ana Paola Agudelo" \\
        --photo-url https://ejemplo.com/foto.jpg

  Con archivo local (copiar primero al contenedor):
    docker compose cp mi_foto.jpg backend:/app/storage/mi_foto.jpg
    docker compose exec backend python scripts/add_face_reference.py \\
        --entity-id <UUID> \\
        --person "Carlos Guevara" \\
        --photo-path /app/storage/mi_foto.jpg

  Listar fotos configuradas para una entidad:
    docker compose exec backend python scripts/add_face_reference.py \\
        --entity-id <UUID> --list

  Eliminar fotos de una persona:
    docker compose exec backend python scripts/add_face_reference.py \\
        --entity-id <UUID> \\
        --person "Nombre" --delete

Consejos para mejores resultados:
  - Usa fotos con el rostro bien visible, de frente o tres cuartos
  - Agrega 3-5 fotos por persona con diferentes ángulos/iluminación
  - Resolución mínima recomendada: 200x200 px
  - Evita fotos grupales donde el rostro es pequeño
"""
import argparse
import sys

sys.path.insert(0, "/app")


def main():
    parser = argparse.ArgumentParser(
        description="Gestión de fotos de referencia facial — Módulo 7 SONAR"
    )
    parser.add_argument("--entity-id",   required=True,  help="UUID de la entidad")
    parser.add_argument("--person",      default="",     help="Nombre de la persona")
    parser.add_argument("--photo-url",   default="",     help="URL pública de la foto")
    parser.add_argument("--photo-path",  default="",     help="Ruta local de la foto (dentro del contenedor)")
    parser.add_argument("--list",        action="store_true", help="Listar fotos de referencia de la entidad")
    parser.add_argument("--delete",      action="store_true", help="Eliminar todas las fotos de la persona")
    args = parser.parse_args()

    from app.core.config import settings

    if not settings.FACE_RECOGNITION_ENABLED:
        print("\n⚠️  FACE_RECOGNITION_ENABLED=false en .env")
        print("   Agrega FACE_RECOGNITION_ENABLED=true al .env y reinicia el backend.\n")
        sys.exit(1)

    from app.workers.nlp.visual import (
        add_face_reference, delete_face_reference, list_face_references,
    )

    entity_id = args.entity_id.strip()

    # ── Listar ──
    if args.list:
        refs = list_face_references(entity_id)
        if not refs:
            print(f"\nNo hay fotos de referencia para la entidad {entity_id}")
        else:
            print(f"\nFotos de referencia para entidad {entity_id}:")
            for r in refs:
                print(f"  👤 {r['person_name']} — {r['photo_count']} foto(s)")
        return

    # ── Eliminar ──
    if args.delete:
        if not args.person:
            print("ERROR: --person es obligatorio para --delete")
            sys.exit(1)
        ok = delete_face_reference(entity_id, args.person)
        if ok:
            print(f"✅ Fotos de '{args.person}' eliminadas.")
        else:
            print(f"❌ No se encontraron fotos de '{args.person}' para esta entidad.")
        return

    # ── Agregar ──
    if not args.person:
        print("ERROR: --person es obligatorio")
        sys.exit(1)

    source = args.photo_url or args.photo_path
    if not source:
        print("ERROR: debes proporcionar --photo-url o --photo-path")
        sys.exit(1)

    print(f"\nAgregando foto de referencia para '{args.person}'...")
    ok = add_face_reference(entity_id, args.person, source)
    if ok:
        print(f"✅ Foto agregada correctamente para '{args.person}'.")
        print(f"   El reconocimiento visual se activará en el próximo ciclo de Celery (30 min).")
        print(f"   Para análisis inmediato: docker compose exec backend python -c \"")
        print(f"   from app.database import SessionLocal")
        print(f"   from app.workers.nlp.visual import run_visual_analysis")
        print(f"   db = SessionLocal(); run_visual_analysis(db); db.close()\"")
    else:
        print(f"❌ No se pudo agregar la foto. Revisa que:")
        print(f"   - La URL sea accesible desde el servidor")
        print(f"   - La foto tenga un rostro visible y bien iluminado")
        print(f"   - La imagen no supere 5 MB")
        sys.exit(1)


if __name__ == "__main__":
    main()
