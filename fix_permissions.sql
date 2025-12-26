-- Ejecutar en Supabase SQL Editor para corregir el error 42501

-- 1. Permitir a los usuarios ACTUALIZAR su propio perfil (necesario para guardar nombre y username tras registro)
CREATE POLICY "Usuarios pueden actualizar su propio perfil" ON public.profiles
  FOR UPDATE TO authenticated 
  USING (auth.uid() = id) 
  WITH CHECK (auth.uid() = id);

-- 2. Permitir a los usuarios INSERTAR su propio perfil (por si falla el trigger automático)
CREATE POLICY "Usuarios pueden crear su propio perfil" ON public.profiles
  FOR INSERT TO authenticated 
  WITH CHECK (auth.uid() = id);

-- Si usas la clave ANON pública en tu backend, esto es suficiente.
-- El usuario se registra, obtiene un token, y con ese token la app actualiza la fila.
