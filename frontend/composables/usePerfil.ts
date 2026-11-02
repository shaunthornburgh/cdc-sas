import type { Perfil } from '~/types/perfil'

/** Z01 / M11 «Mi perfil» API. */
export function usePerfil() {
  const api = useApi()
  return {
    ver: () => api<Perfil>('/perfil'),
    foto: () => api<{ foto: string | null }>('/perfil/foto'),
    cambiarFoto: (foto: string | null) => api<{ foto: string | null }>('/perfil/foto', { method: 'PUT', body: { foto } }),
    password: (actual: string, nueva: string) => api('/perfil/password', { method: 'POST', body: { actual, nueva } }),
    politica: () => api<Perfil>('/perfil/politica', { method: 'POST' }),
  }
}

/**
 * The signed-in person's photo, shared by the sidebar, the mobile bar and «Mi perfil». Loaded once
 * on demand (it can be large, so it isn't part of /auth/me).
 */
export function useMiFoto() {
  const foto = useState<string | null | undefined>('mi-foto', () => undefined)
  const api = usePerfil()
  async function cargar(forzar = false) {
    if (foto.value !== undefined && !forzar) return
    try {
      foto.value = (await api.foto()).foto
    } catch {
      foto.value = null
    }
  }
  return { foto, cargar }
}
