"""
Paquete principal de CineMatch.

Esta versión integra:
- modelo colaborativo TensorFlow / Keras
- perfil temporal para usuarios externos al entrenamiento
- vecinos similares en espacio de embeddings
- orquestador híbrido con rotación controlada
- servicio listo para FastAPI y simulación local

Importante:
- los usuarios de tu producto se tratan siempre como externos a MovieLens
- no se usa el `user_id` para tirar de embeddings de usuarios del train
- la señal colaborativa sale de los ratings reales del usuario actual
"""

__all__ = ["__version__"]

__version__ = "2.0.0"
