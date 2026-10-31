<template>
  <div class="auth-shell">
    <div class="auth-col">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  background: var(--cdc-bg);
  padding: 16px;
}
.auth-col {
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 12px 0 40px;
}
</style>
