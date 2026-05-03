#!/usr/bin/env bash

set -e

echo "Creando archivos .env de CineMatch..."

mkdir -p src/backend
mkdir -p src/ml

# Backend
cat > src/backend/.env <<EOF
DATABASE_URL=postgresql://cinematch_user:PASSWORD@db:5432/cinematch
SECRET_KEY=clave_larga_segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
TMDB_API_KEY=tu_api_key
ML_SERVICE_URL=http://ml:8001
EOF

# ML
cat > src/ml/.env <<EOF
CINEMATCH_MOVIES_PATH=/app/data/processed/movies_clean.csv
CINEMATCH_RATINGS_PATH=/app/data/processed/ratings_sample.csv
CINEMATCH_MODEL_PATH=/app/artifacts/tf_model/collaborative_model.keras
CINEMATCH_MAPPINGS_PATH=/app/artifacts/tf_model/mappings.pkl
CINEMATCH_METADATA_PATH=/app/artifacts/tf_model/model_metadata.json
EOF

echo "✔ Archivos creados:"
echo "   - src/backend/.env"
echo "   - src/ml/.env"
echo ""
echo "⚠ Recuerda cambiar TMDB_API_KEY en src/backend/.env"
echo "⚠ Recuerda poner la contraseña de la BBDD en /backend/.env"