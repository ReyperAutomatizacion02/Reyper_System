-- PASO 1: Ejecutar en Supabase SQL Editor para actualizar la tabla profiles

-- Añadir nuevas columnas
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS username TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS full_name TEXT,
ADD COLUMN IF NOT EXISTS roles TEXT[] DEFAULT '{}';

-- Si deseas dejar de usar la tabla user_roles y usar solo esta columna array:
-- DROP TABLE IF EXISTS public.user_roles; 
-- (Solo ejecútalo si estás seguro de querer borrar la relación anterior)

-- Asegurar que el username sea único (aunque la definición arriba ya lo pone, si la columna ya existía esto asegura la restricción)
-- ALTER TABLE public.profiles ADD CONSTRAINT unique_username UNIQUE (username);
