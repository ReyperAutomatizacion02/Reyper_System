-- SOLUCIÓN DE PERMISOS ADMIN
-- Ejecutar en Supabase SQL Editor

-- 1. Mejorar función is_admin para manejar nulos y arrays vacíos correctamente
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
DECLARE
  _roles text[];
BEGIN
  -- Obtener roles del usuario actual
  SELECT roles INTO _roles FROM public.profiles WHERE id = auth.uid();
  
  -- Si no tiene roles o es nulo, retornar falso
  IF _roles IS NULL THEN
    RETURN FALSE;
  END IF;
  
  -- Verificar si 'Admin' está en el array
  RETURN 'Admin' = ANY(_roles);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Asegurar políticas de lectura
DROP POLICY IF EXISTS "Admins pueden ver todos los perfiles" ON public.profiles;

CREATE POLICY "Admins pueden ver todos los perfiles" ON public.profiles
  FOR SELECT TO authenticated
  USING (
    public.is_admin() OR auth.uid() = id -- Admin ve todo OR Usuario ve lo suyo
  );

-- 3. Asegurar políticas de edición
DROP POLICY IF EXISTS "Admins pueden actualizar cualquier perfil" ON public.profiles;

CREATE POLICY "Admins pueden actualizar cualquier perfil" ON public.profiles
  FOR UPDATE TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());
