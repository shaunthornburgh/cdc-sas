/** Current user + login/logout. State is created once in plugins/auth.ts. */
export const useAuth = () => useNuxtApp().$auth
