<script setup lang="ts">
/**
 * «Agenda» (Coordinación, K19: yours and your team's) · «Mi agenda» (asesor M17, Atención C07,
 * Auxiliar X06). Gerencia has it inside «Avisos y agenda» (G-089), and can open this page too.
 */
useHead({ title: 'Agenda · Casa Dolce Casa' })
const auth = useAuth()
const me = computed(() => auth.user.value!)
const coord = computed(() => me.value.cargo === 'coordinacion')
const amplia = computed(() => ['coordinacion', 'gerencia', 'auxiliar_administrativa'].includes(me.value.cargo))
const route = useRoute()
const sub = computed(() =>
  coord.value
    ? `${me.value.full_name} · arriba eliges de quién ver la agenda: la tuya o la de cualquier persona de tu equipo`
    : amplia.value
      ? `${me.value.full_name} · arriba eliges de quién ver la agenda`
      : `${me.value.full_name} · citas, seguimientos, vencimientos y lo que te asignan`,
)
</script>

<template>
  <PageBar :title="coord ? 'Agenda' : 'Mi agenda'" :subtitle="sub" back="/" />
  <div class="cnt">
    <AgendaView :inicial="(route.query.persona as string) || null" />
    <div class="note">Lo que te asignan llega también a {{ me.cargo === 'gerencia' ? '«Avisos y agenda»' : '«Notificaciones»' }}, con el botón para verlo aquí.</div>
  </div>
</template>
