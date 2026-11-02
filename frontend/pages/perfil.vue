<script setup lang="ts">
import type { Perfil } from '~/types/perfil'

/**
 * Z01 / M11 «Mi perfil»: your data, your photo and your password. You change your photo and your
 * password; your name and other personal data are changed by Coordinación or Gerencia («Usuarios»),
 * and every change is logged.
 */
useHead({ title: 'Mi perfil · Casa Dolce Casa' })

const auth = useAuth()
const api = usePerfil()
const { foto, cargar } = useMiFoto()
const { data, refresh } = await useAsyncData('perfil', () => api.ver())
const P = computed(() => data.value as Perfil)
onMounted(() => cargar())
const home = computed(() => {
  const c = auth.user.value?.cargo
  return c === 'gerencia' || c === 'coordinacion' ? '/coordinacion' : '/'
})

// ---- photo
const fileIn = ref<HTMLInputElement | null>(null)
const fotoMsg = ref<{ t: string; ok: boolean } | null>(null)
function elegir(ev: Event) {
  const f = (ev.target as HTMLInputElement).files?.[0]
  ;(ev.target as HTMLInputElement).value = ''
  if (!f) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(f.type)) return (fotoMsg.value = { t: 'La foto debe ser JPG, PNG o WebP.', ok: false })
  if (f.size > 290_000) return (fotoMsg.value = { t: 'La foto es muy pesada: usa una de menos de 300 KB.', ok: false })
  const r = new FileReader()
  r.onload = () => guardarFoto(String(r.result))
  r.readAsDataURL(f)
}
async function guardarFoto(v: string | null) {
  try {
    foto.value = (await api.cambiarFoto(v)).foto
    fotoMsg.value = { t: v ? '✓ Foto actualizada' : 'Foto quitada: se muestran tus iniciales.', ok: true }
    await refresh()
  } catch (e) {
    fotoMsg.value = { t: apiErrorMessage(e), ok: false }
  }
}

// ---- password
const pw = reactive({ on: false, actual: '', nueva: '', repetir: '', err: '', ok: false, busy: false })
async function cambiarClave() {
  pw.err = ''
  if (!pw.actual || !pw.nueva) return (pw.err = 'Escribe tu contraseña actual y la nueva.')
  if (pw.nueva !== pw.repetir) return (pw.err = 'La nueva contraseña no coincide en los dos campos.')
  pw.busy = true
  try {
    await api.password(pw.actual, pw.nueva)
    Object.assign(pw, { on: false, actual: '', nueva: '', repetir: '', ok: true })
  } catch (e) {
    pw.err = apiErrorMessage(e)
  } finally {
    pw.busy = false
  }
}

// ---- logout and data policy
const conf = ref(false)
async function aceptar() {
  data.value = await api.politica()
}
const fPol = computed(() => (P.value?.politica_aceptada_at ? fmtFecha(new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date(P.value.politica_aceptada_at))) : ''))
</script>

<template>
  <PageBar title="Mi perfil" subtitle="Tus datos, tu foto y tu contraseña" :back="home" />

  <div v-if="P" class="cnt">
    <div class="g2b">
      <div class="card yo">
        <img v-if="foto" :src="foto" alt="Tu foto" class="foto">
        <span v-else class="av big">{{ initials(P.full_name) }}</span>
        <b class="t20">{{ P.full_name }}</b>
        <span class="mut">{{ P.cargo_txt }}</span>
        <div v-if="P.actividades.length" class="row fw gp6 center">
          <span v-for="a in P.actividades" :key="a" class="act on1">✓ {{ a }}</span>
        </div>
        <div class="row fw gp8 center">
          <button type="button" class="btn bs" @click="fileIn?.click()">Cambiar foto</button>
          <button v-if="foto" type="button" class="btn bs" @click="guardarFoto(null)">Quitar foto</button>
          <input ref="fileIn" type="file" accept="image/png,image/jpeg,image/webp" class="sr-only" aria-label="Archivo de la foto" @change="elegir">
        </div>
        <span v-if="fotoMsg" class="chip" :class="fotoMsg.ok ? 'ok' : 'bad'">{{ fotoMsg.t }}</span>
        <div class="mut tiny">Tu foto la puedes cambiar tú. {{ P.regla_nombre }}</div>
      </div>
      <div class="card col6">
        <div class="lbl">Mis datos</div>
        <div v-for="d in P.datos" :key="d.k" class="sb dato">
          <span class="mut">{{ d.k }}</span><b>{{ d.v }}</b>
        </div>
      </div>
    </div>

    <NuxtLink v-if="P.resultados" :to="P.resultados.href" class="card res">
      <div>
        <div class="lbl">Mis resultados · {{ P.resultados.mes }}</div>
        <div class="mut small">{{ P.resultados.txt }}</div>
      </div>
      <span class="btn bp h40">Ver mis resultados ›</span>
    </NuxtLink>

    <div class="card">
      <div class="lbl">Accesos rápidos</div>
      <NuxtLink v-for="a in P.accesos" :key="a.href" :to="a.href" class="li"><b>{{ a.t }}</b><span class="go">›</span></NuxtLink>
    </div>

    <div class="card seg">
      <div class="lbl full">Seguridad</div>
      <button type="button" class="btn bs" @click="pw.on = !pw.on; pw.ok = false">{{ pw.on ? 'Cancelar' : 'Cambiar contraseña' }}</button>
      <button type="button" class="btn br" @click="conf = true">Cerrar sesión</button>
      <span v-if="pw.ok" class="chip ok">✓ Contraseña cambiada. Úsala la próxima vez que entres.</span>
      <div v-if="pw.on" class="full g3">
        <div class="fld"><label for="pw1">Contraseña actual <span class="req">*</span></label><input id="pw1" v-model="pw.actual" class="in" type="password" autocomplete="current-password"></div>
        <div class="fld"><label for="pw2">Nueva contraseña <span class="req">*</span></label><input id="pw2" v-model="pw.nueva" class="in" type="password" autocomplete="new-password" minlength="8"></div>
        <div class="fld"><label for="pw3">Repite la nueva <span class="req">*</span></label><input id="pw3" v-model="pw.repetir" class="in" type="password" autocomplete="new-password"></div>
      </div>
      <div v-if="pw.on" class="full row fw gp8">
        <button type="button" class="btn bp" :disabled="pw.busy" @click="cambiarClave">Guardar contraseña</button>
        <span class="mut tiny">Mínimo 8 caracteres, distinta de la actual y de tu correo.</span>
      </div>
      <div v-if="pw.err" class="note bad full"><b>{{ pw.err }}</b></div>
      <div class="mut tiny full">
        <template v-if="P.politica_aceptada_at">Política de tratamiento de datos aceptada el {{ fPol }}.</template>
        <template v-else>
          No has aceptado la política de tratamiento de datos.
          <button type="button" class="btn bs xs" @click="aceptar">Aceptar la política</button>
        </template>
      </div>
    </div>
  </div>

  <ConfirmDialog v-if="conf" title="¿Cerrar sesión?" confirm-label="Sí, cerrar sesión" @confirm="auth.logout()" @cancel="conf = false">
    Tendrás que volver a entrar con tu correo y tu contraseña.
  </ConfirmDialog>
</template>

<style scoped>
.yo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
}
.big {
  width: 96px;
  height: 96px;
  font-size: 32px;
  margin: 0;
}
.foto {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--cdc-green-lime);
}
.t20 {
  font-size: 20px;
}
.fw {
  flex-wrap: wrap;
}
.gp6 {
  gap: 6px;
}
.gp8 {
  gap: 8px;
}
.center {
  justify-content: center;
}
.col6 {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dato {
  font-size: 13.5px;
  padding: 7px 0;
  border-bottom: 1px solid var(--cdc-border-soft);
  gap: 12px;
}
.dato b {
  text-align: right;
}
.res {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--cdc-text);
  flex-wrap: wrap;
}
.h40 {
  min-height: 40px;
}
.go {
  font-weight: 800;
  color: var(--cdc-green);
}
.seg {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.full {
  width: 100%;
}
.small {
  font-size: 12.5px;
}
.tiny {
  font-size: 12px;
}
.xs {
  min-height: 28px;
  padding: 0 10px;
  font-size: 12px;
  margin-left: 6px;
}
</style>
