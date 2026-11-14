# Imagen base con Python 3.12
FROM python:3.12-slim

# Crear usuario no-root para ejecutar la aplicación
RUN useradd -m -u 1000 appuser

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY --chown=appuser:appuser . .

# Cambiar a usuario no-root
USER appuser

# Ejecutar uvicorn en el puerto de PORT (8000 por omisión). Forma shell para
# que se expanda la variable; exec deja a uvicorn como proceso principal.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
