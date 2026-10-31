// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: true },
  typescript: { strict: true },

  css: ['~/assets/css/tokens.css', '~/assets/css/main.css'],

  // Components in subfolders keep their own name (components/users/UserCard.vue -> <UserCard>).
  components: [{ path: '~/components', pathPrefix: false }],

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
      // Override with NUXT_PUBLIC_API_BASE
      apiBase: 'http://localhost:8100/api/v1',
    },
  },
})
