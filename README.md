# 🎬 CineMatch — Sistema de Recomendación de Películas

## 🎯 Objetivo
Desarrollar un sistema de recomendación escalable que genere sugerencias personalizadas de películas a partir del historial de valoraciones de los usuarios, mejorando la experiencia de descubrimiento y retención del contenido.

---

## 👥 Equipo — Grupo E-12
- **Badr Lahrarti** –  Data Engineer & Coordinador Técnico
- **Alejandro Miguel González Mateos** – Machine Learning Engineer
- **Daniel Ruiz González** –  Backend & API Developer
- **Francisco López Fenoll** –  Frontend & Visualización Developer

---

## 🗂 Estructura del proyecto
```
repo/
├── data/
│   ├── raw/              ← datos crudos de MovieLens (no en git)
│   └── processed/        ← datos limpios generados por ingest.py (no en git)
├── src/
│   └── pipeline/
│       ├── ingest.py     ← script reproducible del pipeline
│       └── notebooks/
│           └── eda.ipynb ← exploración y análisis de datos
├── docs/                 ← documentación del proyecto
├── environment/          ← entorno virtual (no en git)
├── requirements.txt      ← dependencias del proyecto
├── README.md
└── .gitignore
```
---

## ⚙️ Tecnologías previstas
- Python 3.x  
- scikit-learn / pandas / numpy  
- PostgreSQL
- Streamlit (interfaz de usuario)  
- FastAPI
- Pytest
- GitHub, Trello, VS Code 
---

## 🚀 Nota inicial
Este repositorio es la base para la **Fase 1 del proyecto**, con estructura mínima operativa.  
A medida que avancemos, se irán añadiendo:

- Código de procesamiento de datos  
- Modelos de recomendación  
- API y mini-interfaz para mostrar resultados  
- Documentación adicional y métricas del sistema  

## 🚀 Instalación y uso (en proceso)

```bash
git clone https://github.com/badrlah9/CineMatch-Sistema-de-recomendacion-peliculas.git
cd CineMatch-Sistema-de-recomendacion-peliculas
```

## 2. Crear y activar el entorno virtual
```bash
# Crear el entorno virtual dentro de environment/
python -m venv environment/venv

# Activar en Mac/Linux
source environment/venv/bin/activate

# Activar en Windows
environment\venv\Scripts\activate
```

## 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

## 4. Descargar el dataset

Descarga el archivo `ml-32m.zip` desde la URL oficial :```https://grouplens.org/datasets/movielens/32m/```

Descomprime el zip y copia los 4 archivos CSV dentro de `data/raw/` :
```
data/raw/
├── ratings.csv
├── movies.csv
├── links.csv
└── tags.csv
```
OJO :
⚠️ Los datos NO están en el repositorio por su tamaño (~1GB descomprimidos).
⚠️ Nunca subas los datos al repo — están en el .gitignore.

## 5. Ejecutar el pipeline de datos
```bash : 
python src/pipeline/ingest.py```

Esto genera automáticamente los datos limpios en `data/processed/` :
```
Si los datos procesados ya existen y necesitas reprocesar desde cero :
```bash
python src/pipeline/ingest.py --force
```

## Orden de arranque del proyecto completo
```
1. Pipeline datos  → python src/pipeline/ingest.py
2. Backend API     → (pendiente Daniel)
3. Frontend        → (pendiente Fran)
```
## Reglas del equipo

- No se sube nada a `main` sin Pull Request aprobado
- Todo trabajo tiene issue asignada en Trello
- Las decisiones técnicas importantes se documentan
- Se respeta el reparto de roles pero se ayuda si hay bloqueo