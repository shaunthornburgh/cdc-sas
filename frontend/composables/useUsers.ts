import type {
  ActividadComercial,
  ActividadEvento,
  FuncionIndependiente,
  User,
  UserCreate,
  UserUpdate,
} from '~/types/auth'

/** User management API (Gerencia / Coordinación only). */
export function useUsers() {
  const api = useApi()
  return {
    list: () => api<User[]>('/users'),
    create: (body: UserCreate) => api<User>('/users', { method: 'POST', body }),
    update: (id: string, body: UserUpdate) =>
      api<User>(`/users/${id}`, { method: 'PATCH', body }),
    setActividades: (id: string, actividades: ActividadComercial[]) =>
      api<User>(`/users/${id}/activities`, { method: 'POST', body: { actividades } }),
    setFuncion: (id: string, funcion: FuncionIndependiente | null) =>
      api<User>(`/users/${id}/funcion`, { method: 'POST', body: { funcion } }),
    history: (id: string) => api<ActividadEvento[]>(`/users/${id}/activities/history`),
  }
}
