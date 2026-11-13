import type { Marca } from '~/types/configuracion'

/**
 * Loads the brand (public endpoint) during server rendering and applies its greens to the whole
 * app. The client reuses the hydrated state; Configuración updates it when Gerencia saves.
 */
export default defineNuxtPlugin(async () => {
  const marca = useMarca()
  
  useHead({ htmlAttrs: { style: computed(() => marcaVars(marca.value)) } })
})

