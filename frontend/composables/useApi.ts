/**
 * Authenticated fetch against the API (adds the bearer token, refreshes on 401).
 *
 *   const api = useApi()
 *   const items = await api<Item[]>('/items')
 */
export const useApi = () => useNuxtApp().$api
