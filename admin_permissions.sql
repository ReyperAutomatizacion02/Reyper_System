-- PERMISOS DE ADMINISTRADOR
-- Ejecutar en Supabase SQL Editor

-- 1. Función auxiliar para verificar si soy admin (evita repetir lógica)
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid()
    AND 'Admin' = ANY(roles)
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Política: Admins pueden VER todos los perfiles
CREATE POLICY "Admins pueden ver todos los perfiles" ON public.profiles
  FOR SELECT TO authenticated
  USING (public.is_admin());

-- 3. Política: Admins pueden ACTUALIZAR cualquier perfil
CREATE POLICY "Admins pueden actualizar cualquier perfil" ON public.profiles
  FOR UPDATE TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- Nota: Ya existen políticas que permiten al usuario ver/editar SU propio perfil. 
-- Supabase aplica permisos aditivos (OR), así que esto añade el poder a los Admins.
