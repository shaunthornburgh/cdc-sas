/**
 * Every page requires login unless it sets definePageMeta({ public: true }).
 * Pages can also limit access by cargo: definePageMeta({ cargos: ['gerencia'] }).
 * Logged-in users visiting /login are sent on to the app.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()
  const user = await auth.ensureUser()

  if (to.meta.public) {
    if (user && to.path === '/login') return navigateTo(safeRedirect(to.query.redirect))
    return
  }

  if (!user) {
    return navigateTo({
      path: '/login',
      query: to.fullPath === '/' ? {} : { redirect: to.fullPath },
    })
  }

  const moduleDenied =
    (to.meta.module === 'leads' && !canUseLeads(user)) ||
    (to.meta.module === 'captaciones' && !canUseCaptaciones(user)) ||
    (to.meta.module === 'asesor' && !(hasCommercialActivity(user) || isManager(user))) ||
    (to.meta.module === 'pedidos' && !canUsePedidos(user)) ||
    (to.meta.module === 'resultados' && !perfilRendimiento(user)) ||
    (to.meta.module === 'inmuebles' && !canUseInmuebles(user)) ||
    (to.meta.module === 'movimientos' && !canUseMovimientos(user))
  if (moduleDenied || (to.meta.cargos && !to.meta.cargos.includes(user.cargo))) {
    return abortNavigation(
      createError({ statusCode: 403, message: 'No tienes acceso a esta página.' }),
    )
  }
})
