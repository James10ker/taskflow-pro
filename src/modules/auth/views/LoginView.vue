<template>
  <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
    <div>
      <div class="text-base font-semibold">Welcome back</div>
      <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
        Sign in to your workspace and keep projects moving.
      </div>
    </div>

    <BaseInput v-model="email" label="Email" autocomplete="email" placeholder="admin@taskflow.pro" :error="fieldErrors.email" />
    <BaseInput
      v-model="password"
      label="Password"
      type="password"
      autocomplete="current-password"
      placeholder="••••••••"
      :error="fieldErrors.password"
    />

    <BaseButton type="submit" :loading="auth.loading" full>
      Sign in
    </BaseButton>

    <div class="text-center text-xs text-slate-500 dark:text-slate-400">
      W1 supports the seeded admin and member demo accounts. Registration will be migrated later.
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import BaseButton from '@/components/BaseButton.vue'
import BaseInput from '@/components/BaseInput.vue'
import { useAuthStore } from '@/modules/auth/store'
import { useToastsStore } from '@/store/toasts'

const router = useRouter()
const auth = useAuthStore()
const toasts = useToastsStore()

const email = ref('admin@taskflow.pro')
const password = ref('Admin123!')

const fieldErrors = reactive<{ email?: string; password?: string }>({})

function validate() {
  fieldErrors.email = undefined
  fieldErrors.password = undefined

  if (!email.value.trim()) fieldErrors.email = 'Email is required.'
  if (!password.value.trim()) fieldErrors.password = 'Password is required.'

  return !fieldErrors.email && !fieldErrors.password
}

async function onSubmit() {
  if (!validate()) return

  const ok = await auth.login(email.value, password.value)
  if (ok) {
    await auth.refreshMe()
    toasts.success('Signed in successfully.')
    router.push({ name: 'dashboard' })
  }
}
</script>
