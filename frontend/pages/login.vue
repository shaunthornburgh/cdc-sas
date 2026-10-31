<script setup lang="ts">
definePageMeta({ layout: 'auth', public: true })
useHead({ title: 'Iniciar sesión · Casa Dolce Casa' })

const auth = useAuth()
const route = useRoute()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref<string | null>(null)
const submitting = ref(false)

async function onSubmit() {
  error.value = null
  submitting.value = true
  try {
    await auth.login(email.value, password.value)
    await navigateTo(safeRedirect(route.query.redirect))
  } catch (e) {
    error.value = apiErrorMessage(e, 'No se pudo iniciar sesión.')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="hero">
    <BrandLogo :size="92" />
    <div class="hero-wm">CASA DOLCE CASA</div>
    <div class="hero-lema">Confianza que construye hogares</div>
  </div>

  <form class="card login" novalidate @submit.prevent="onSubmit">
    <div>
      <h1 class="ttl login-ttl">Iniciar sesión</h1>
      <div class="mut sub">Entra con tu correo y tu contraseña.</div>
    </div>

    <div class="fld">
      <label for="usr">Correo <span class="req">*</span></label>
      <input
        id="usr"
        v-model.trim="email"
        class="in"
        type="email"
        placeholder="nombre@correo.com"
        autocomplete="username"
        required
      >
    </div>

    <div class="fld">
      <label for="pwd">Contraseña <span class="req">*</span></label>
      <div class="row pwd-row">
        <input
          id="pwd"
          v-model="password"
          class="in"
          :type="showPassword ? 'text' : 'password'"
          placeholder="Tu contraseña"
          autocomplete="current-password"
          required
        >
        <button
          type="button"
          class="btn bs toggle"
          :aria-label="showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'"
          @click="showPassword = !showPassword"
        >
          {{ showPassword ? 'Ocultar' : 'Mostrar' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="note bad" role="alert"><b>{{ error }}</b></div>

    <button type="submit" class="btn bp submit" :disabled="submitting || !email || !password">
      {{ submitting ? 'Ingresando…' : 'Ingresar' }}
    </button>
    <div class="mut small">Al entrar, el sistema abre la pantalla que corresponde a tu cargo.</div>
  </form>

  <div class="mut small center">¿No tienes usuario? Pídelo a tu coordinador.</div>
</template>

<style scoped>
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 0 6px;
  text-align: center;
}
.hero-wm {
  font-family: var(--font-display);
  font-size: 46px;
  letter-spacing: 0.04em;
  line-height: 1;
  color: var(--cdc-green-dark);
  margin-top: 6px;
}
.hero-lema {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--cdc-muted);
}
.login {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.login-ttl {
  font-size: 30px;
}
.sub {
  font-size: 13px;
}
/* The login screen uses the larger touch sizes of the phone prototypes. */
.login .in {
  min-height: 48px;
  font-size: 15px;
}
.pwd-row {
  gap: 8px;
}
.toggle {
  flex: none;
  min-height: 48px;
  font-size: 13px;
}
.submit {
  width: 100%;
  min-height: 48px;
  border-radius: 12px;
  font-size: 15px;
}
.small {
  font-size: 12px;
}
.center {
  text-align: center;
}
</style>
