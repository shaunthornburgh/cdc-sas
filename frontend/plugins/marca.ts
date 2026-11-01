import type { Marca } from '~/types/configuracion'

/**
 * Loads the brand (public endpoint) during server rendering and applies its greens to the whole
 * app. The client reuses the hydrated state; Configuración updates it when Gerencia saves.
 */
export default defineNuxtPlugin(async () => {
  const marca = useMarca()
  if (import.meta.server) {
    try {
      marca.value = await $fetch<Marca>(`${useRuntimeConfig().public.apiBase}/configuracion/marca`)
    } catch {
      // API down: keep Casa Dolce Casa's brand
    }
  }
  useHead({ htmlAttrs: { style: computed(() => marcaVars(marca.value)) } })
})
