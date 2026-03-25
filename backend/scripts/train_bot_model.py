"""
Script de entrenamiento del clasificador de bots — SONAR v2

Genera un dataset sintético basado en patrones reales de cuentas bot
documentados en investigaciones (Botometer, Twitter bot studies 2018-2023)
y entrena un GradientBoostingClassifier.

Uso:
    docker compose exec backend python scripts/train_bot_model.py

El modelo se guarda en /app/storage/models/bot_model.pkl
El backend lo carga automáticamente en el siguiente ciclo de análisis.

Nota: solo necesitas correr este script UNA VEZ después del primer arranque.
Si no lo corres, el clasificador usará el fallback heurístico que también funciona.
"""
import os
import pickle
import sys

import numpy as np

MODEL_PATH   = "/app/storage/models/bot_model.pkl"
N_REAL       = 1200   # ejemplos de cuentas reales
N_BOT        = 600    # ejemplos de cuentas bot
RANDOM_STATE = 42


def generate_real_accounts(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Genera features de cuentas humanas reales.
    Basado en estadísticas de usuarios típicos de Twitter/Reddit.
    """
    rows = []
    for _ in range(n):
        age_days       = rng.lognormal(6.5, 1.2)          # 1 año promedio
        age_days       = float(np.clip(age_days, 30, 3650))
        post_count     = rng.lognormal(5, 1.5)             # ~150 posts
        posts_per_day  = min(post_count / age_days, 200)
        followers      = rng.lognormal(4, 2)               # ~55 followers
        following      = rng.lognormal(4, 1.5)             # ~55 following
        ff_ratio       = min(followers / max(following, 1), 500)
        has_photo      = rng.choice([0, 1], p=[0.08, 0.92])
        has_bio        = rng.choice([0, 1], p=[0.25, 0.75])
        is_verified    = rng.choice([0, 1], p=[0.97, 0.03])
        name_len       = float(np.clip(rng.normal(11, 4), 3, 30))
        digit_ratio    = float(np.clip(rng.beta(1.2, 12), 0, 1))

        rows.append([ff_ratio, posts_per_day, has_photo, has_bio,
                     is_verified, digit_ratio, name_len, age_days])
    return np.array(rows, dtype=float)


def generate_bot_accounts(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Genera features de cuentas bot.
    Cuatro arquetipos documentados:
      A. Amplificadores (muchos seguidores, alto post rate)
      B. Seguidores (ratio ff bajo, recientes)
      C. Spam simples (sin foto, sin bio, muchos dígitos)
      D. Coordinados (similares entre sí)
    """
    rows = []
    archetype_probs = [0.30, 0.30, 0.25, 0.15]   # A, B, C, D

    for _ in range(n):
        archetype = rng.choice(["A", "B", "C", "D"], p=archetype_probs)

        if archetype == "A":   # Amplificadores
            age_days      = float(np.clip(rng.lognormal(4, 1.5), 7, 730))
            posts_per_day = min(float(rng.exponential(80)), 200)
            followers     = rng.lognormal(8, 1.5)      # muchos seguidores inflados
            following     = rng.lognormal(4, 1)
            ff_ratio      = min(followers / max(following, 1), 500)
            has_photo     = rng.choice([0, 1], p=[0.3, 0.7])
            has_bio       = rng.choice([0, 1], p=[0.5, 0.5])
            digit_ratio   = float(np.clip(rng.beta(3, 5), 0, 1))
            name_len      = float(np.clip(rng.normal(14, 5), 5, 30))

        elif archetype == "B":   # Seguidores
            age_days      = float(np.clip(rng.exponential(45), 1, 180))
            posts_per_day = min(float(rng.exponential(15)), 200)
            followers     = float(rng.exponential(10))   # pocos seguidores
            following     = rng.lognormal(6, 1)           # siguen a muchos
            ff_ratio      = min(followers / max(following, 1), 500)
            has_photo     = rng.choice([0, 1], p=[0.55, 0.45])
            has_bio       = rng.choice([0, 1], p=[0.65, 0.35])
            digit_ratio   = float(np.clip(rng.beta(4, 4), 0, 1))
            name_len      = float(np.clip(rng.normal(18, 6), 8, 30))

        elif archetype == "C":   # Spam simples
            age_days      = float(np.clip(rng.exponential(20), 1, 90))
            posts_per_day = min(float(rng.exponential(100)), 200)
            followers     = float(rng.exponential(5))
            following     = float(rng.exponential(50))
            ff_ratio      = min(followers / max(following, 1), 500)
            has_photo     = rng.choice([0, 1], p=[0.75, 0.25])
            has_bio       = rng.choice([0, 1], p=[0.85, 0.15])
            digit_ratio   = float(np.clip(rng.beta(7, 3), 0, 1))   # muchos dígitos
            name_len      = float(np.clip(rng.normal(20, 4), 12, 30))

        else:   # Coordinados (D)
            age_days      = float(np.clip(rng.normal(120, 60), 7, 400))
            posts_per_day = min(float(rng.exponential(30)), 200)
            followers     = float(rng.lognormal(3, 1))
            following     = float(rng.lognormal(4, 1))
            ff_ratio      = min(followers / max(following, 1), 500)
            has_photo     = rng.choice([0, 1], p=[0.4, 0.6])
            has_bio       = rng.choice([0, 1], p=[0.6, 0.4])
            digit_ratio   = float(np.clip(rng.beta(4, 6), 0, 1))
            name_len      = float(np.clip(rng.normal(15, 5), 6, 28))

        rows.append([ff_ratio, posts_per_day, has_photo, has_bio,
                     0.0, digit_ratio, name_len, age_days])   # is_verified=0 para todos los bots

    return np.array(rows, dtype=float)


def train_and_save() -> None:
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        from sklearn.metrics import classification_report, roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError:
        print("ERROR: scikit-learn no instalado. Ejecuta primero: pip install scikit-learn")
        sys.exit(1)

    print(f"Generando dataset sintético ({N_REAL} reales, {N_BOT} bots)...")
    rng = np.random.default_rng(RANDOM_STATE)

    X_real = generate_real_accounts(N_REAL, rng)
    X_bot  = generate_bot_accounts(N_BOT, rng)

    X = np.vstack([X_real, X_bot])
    y = np.array([0] * N_REAL + [1] * N_BOT)

    # Shuffle
    idx = rng.permutation(len(y))
    X, y = X[idx], y[idx]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    print("Entrenando GradientBoostingClassifier...")
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            random_state=RANDOM_STATE,
        )),
    ])
    model.fit(X_train, y_train)

    # Evaluación
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc     = roc_auc_score(y_test, y_proba)

    print("\n── Métricas de evaluación ──────────────────")
    print(classification_report(y_test, y_pred, target_names=["real", "bot"]))
    print(f"AUC-ROC: {auc:.4f}")

    # Guardar modelo
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    size_kb = os.path.getsize(MODEL_PATH) / 1024
    print(f"\n✓ Modelo guardado en {MODEL_PATH} ({size_kb:.1f} KB)")
    print("  El backend lo cargará automáticamente en el próximo ciclo de análisis.")


if __name__ == "__main__":
    train_and_save()
