// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },
  typescript: { strict: true },

  css: ['~/assets/css/tokens.css', '~/assets/css/main.css'],

  // Components in subfolders keep their own name (components/users/UserCard.vue -> <UserCard>).
  components: [{ path: '~/components', pathPrefix: false }],

  routeRules: {
    '/': { ssr: false },
    '/coordinacion': { ssr: false },
    '/asesor': { ssr: false },
    '/preoperacional': { ssr: false },
    '/preoperacionales': { ssr: false },
    '/pedidos': { ssr: false },
    '/resultados': { ssr: false },
    '/resultados/**': { ssr: false },
    '/equipo': { ssr: false },
    '/rendimiento': { ssr: false },
    '/rendimiento-empresa': { ssr: false },
    '/compensacion': { ssr: false },
    '/salarios': { ssr: false },
    '/mis-pagos': { ssr: false },
    '/inmuebles': { ssr: false },
    '/inmuebles/**': { ssr: false },
    '/novedades': { ssr: false },
    '/movimientos': { ssr: false },
    '/plataformas': { ssr: false },
    '/configuracion': { ssr: false },
    '/avisos': { ssr: false },
    '/agenda': { ssr: false },
    '/perfil': { ssr: false },
    '/trazabilidad': { ssr: false },
    '/integraciones': { ssr: false },
    '/polizas': { ssr: false },
    '/rutas': { ssr: false },
    '/usuarios': { ssr: false },
    '/leads': { ssr: false },
    '/leads/**': { ssr: false },
    '/citas': { ssr: false },
    '/mis-citas': { ssr: false },
    '/captaciones': { ssr: false },
    '/login': { ssr: false },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'es' },
      title: 'Casa Dolce Casa',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'theme-color', content: '#0B3D23' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Montserrat:wght@400;500;600;700;800&display=swap',
        },
      ],
    },
  },

  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },
})
