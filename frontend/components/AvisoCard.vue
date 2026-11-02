<script setup lang="ts">
import type { Aviso } from '~/types/avisos'

/**
 * One aviso (C05 / G09): what happened, what to do and until when, with the button to do it.
 * Actions: add a note, schedule it in «Mi agenda», mark as attended (or reopen).
 */
const props = defineProps<{ a: Aviso }>()
const emit = defineEmits<{ changed: [msg: string] }>()
const api = useAvisos()

const panel = ref<'' | 'nota' | 'agenda'>('')
const f = reactive({ nota: '', titulo: '', fecha: localDate(1), hora: '09:00', obs: '', err: '', busy: false })
const ACCIONES = ['Reunión con Coordinación', 'Revisar estrategia del área', 'Hablar con un empleado', 'Revisar resultados de nuevo']
const abierto = computed(() => props.a.estado === 'por_atender')
const borde = computed(() => abierto.value && props.a.nivel === 'bad')
const big = computed(() => props.a.datos.length > 0)

function toggle(p: 'nota' | 'agenda') {
  panel.value = panel.value === p ? '' : p
  Object.assign(f, { err: '', titulo: p === 'agenda' ? '' : f.titulo })
}
async function run(fn: () => Promise<unknown>, msg: string) {
  f.err = ''
  f.busy = true
  try {
    await fn()
    panel.value = ''
    emit('changed', msg)
  } catch (e) {
    f.err = apiErrorMessage(e)
  } finally {
    f.busy = false
  }
}
const guardarNota = () => run(() => api.nota(props.a.id, f.nota), 'Nota guardada en el aviso. Queda en el historial.')
const agendar = () =>
  run(
    () => api.agendar(props.a.id, { titulo: f.titulo || ACCIONES[0], fecha: f.fecha, hora: f.hora || null, nota: f.obs || null }),
    `Agendado en tu agenda: ${fmtFecha(f.fecha)}${f.hora ? ` ${f.hora}` : ''}.`,
  )
const atender = () => run(() => api.atender(props.a.id), 'Aviso marcado como atendido. Queda en el historial con tus notas y acciones.')
const reabrir = () => run(() => api.reabrir(props.a.id), 'Aviso abierto de nuevo.')
const CHIP: Record<string, string> = { bad: 'bad', warn: 'warn', info: 'info', gray: 'gray' }
</script>

<template>
  <div class="card aviso" :class="{ rojo: borde }">
    <div class="sb fw g8">
      <div class="row fw g8">
        <span class="chip" :class="CHIP[a.nivel]">{{ a.tipo_txt }}</span>
        <span class="mut tiny">{{ fmtCuando(a.created_at) }}{{ a.enviado_por ? ` · ${a.enviado_por}` : '' }}</span>
      </div>
      <span v-if="a.requiere_accion" class="chip" :class="abierto ? 'warn' : 'ok'">
        {{ abierto ? 'Por atender' : a.resuelto_auto ? '✓ Resuelto' : '✓ Atendido' }}
      </span>
    </div>
    <b :class="big ? 't17' : 't145'">{{ a.titulo }}</b>
    <div v-if="a.datos.length" class="g3">
      <div v-for="d in a.datos" :key="d.lbl" class="dato" :class="{ drojo: d.rojo }">
        <div class="lbl">{{ d.lbl }}</div>
        <div v-if="d.val" class="kn num">{{ d.val }}</div>
        <div class="small">{{ d.sub }}</div>
      </div>
    </div>
    <div v-if="a.detalle" class="mut small pre">{{ a.detalle }}</div>
    <div v-if="a.que_hacer && abierto" class="small">
      <b>Qué debes hacer:</b> {{ a.que_hacer }}<template v-if="a.limite_at"> · <b>Límite:</b> {{ fmtCuando(a.limite_at) }}</template>
    </div>
    <div v-if="!abierto && a.requiere_accion" class="mut tiny">
      {{ a.resuelto_auto ? 'Se resolvió solo: ya no hay nada pendiente' : `Atendido${a.atendido_por_name ? ` por ${a.atendido_por_name}` : ''}` }}
      {{ a.atendido_at ? ` · ${fmtCuando(a.atendido_at)}` : '' }}
    </div>

    <div class="row fw g8">
      <NuxtLink v-if="a.link && a.accion_txt" :to="a.link" class="btn" :class="abierto ? 'bp' : 'bs'">{{ a.accion_txt }}</NuxtLink>
      <template v-if="a.requiere_accion">
        <button type="button" class="opt" :class="{ on: panel === 'nota' }" @click="toggle('nota')">Agregar nota</button>
        <button v-if="abierto" type="button" class="opt" :class="{ on: panel === 'agenda' }" @click="toggle('agenda')">Agendar en mi agenda</button>
        <button v-if="abierto" type="button" class="btn bs" :disabled="f.busy" @click="atender">Marcar como atendido</button>
        <button v-else-if="!a.resuelto_auto" type="button" class="btn bs" :disabled="f.busy" @click="reabrir">Abrir de nuevo</button>
      </template>
    </div>

    <div v-if="panel === 'nota'" class="pnl">
      <div class="fld"><label :for="`n-${a.id}`">Nota o estrategia</label><textarea :id="`n-${a.id}`" v-model="f.nota" class="in ta" placeholder="Ej.: reunión con Coordinación para reforzar captación en Belén y Laureles" /></div>
      <div><button type="button" class="btn bp" :disabled="f.busy" @click="guardarNota">Guardar nota</button></div>
    </div>
    <div v-if="panel === 'agenda'" class="pnl">
      <div class="g4">
        <div class="fld">
          <label :for="`ac-${a.id}`">Acción <span class="req">*</span></label>
          <input :id="`ac-${a.id}`" v-model="f.titulo" class="in" :list="`acs-${a.id}`" :placeholder="ACCIONES[0]">
          <datalist :id="`acs-${a.id}`"><option v-for="x in ACCIONES" :key="x" :value="x" /></datalist>
        </div>
        <div class="fld"><label :for="`fe-${a.id}`">Fecha <span class="req">*</span></label><input :id="`fe-${a.id}`" v-model="f.fecha" class="in" type="date" :min="localDate(0)"></div>
        <div class="fld"><label :for="`ho-${a.id}`">Hora</label><input :id="`ho-${a.id}`" v-model="f.hora" class="in" type="time" step="900"></div>
        <div class="fld"><label :for="`ob-${a.id}`">Observación</label><input :id="`ob-${a.id}`" v-model="f.obs" class="in" placeholder="Qué vas a hacer"></div>
      </div>
      <div><button type="button" class="btn bp" :disabled="f.busy" @click="agendar">Agendar</button></div>
    </div>
    <div v-if="f.err" class="note bad"><b>{{ f.err }}</b></div>

    <div v-if="a.notas.length" class="col4">
      <div class="lbl">Notas del aviso</div>
      <div v-for="n in a.notas" :key="n.id" class="note small">{{ n.autor_name }} · {{ fmtCuando(n.created_at) }}: {{ n.texto }}</div>
    </div>
  </div>
</template>

<style scoped>
.aviso {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rojo {
  border: 2px solid #a3271b;
}
.fw {
  flex-wrap: wrap;
}
.g8 {
  gap: 8px;
}
.t17 {
  font-size: 17px;
}
.t145 {
  font-size: 14.5px;
}
.small {
  font-size: 13px;
}
.tiny {
  font-size: 12px;
}
.pre {
  white-space: pre-line;
}
.dato {
  background: var(--cdc-bg);
  border-radius: 12px;
  padding: 12px;
}
.drojo {
  background: #fbe4e0;
}
.drojo .kn {
  color: #a3271b;
}
.pnl {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--cdc-border-soft);
  padding-top: 10px;
}
.col4 {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
