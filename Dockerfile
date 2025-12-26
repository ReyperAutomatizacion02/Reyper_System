# Usar una imagen base oficial de Python ligera
FROM python:3.11-slim

# Establecer el directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de requisitos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto en el que correrá la aplicación (5000 es el default de Flask)
EXPOSE 5000

# Comando para correr la aplicación usando Gunicorn (servidor de producción)
# Se asume que tu objeto Flask se llama 'app' dentro del archivo 'app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
