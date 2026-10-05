<template>
  <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
    <div>
      <div class="text-base font-semibold">Create your account</div>
      <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">
        Get a personal workspace and start tracking tasks.
      </div>
    </div>

    <BaseInput v-model="name" label="Full name" autocomplete="name" placeholder="Your name" :error="fieldErrors.name" />
    <BaseInput v-model="email" label="Email" autocomplete="email" placeholder="you@company.com" :error="fieldErrors.email" />
    <BaseInput
      v-model="password"
      label="Password"
      type="password"
      autocomplete="new-password"
      placeholder="At least 6 characters"
      :error="fieldErrors.password"
      hint="Use at least 6 characters."
    />

    <BaseButton type="submit" :loading="auth.loading" full>
      Create account
    </BaseButton>

    <div class="text-center text-sm text-slate-600 dark:text-slate-300">
      Already have an account?
      <RouterLink class="font-semibold text-slate-900 hover:underline dark:text-slate-50" to="/auth/login">
        Sign in
      </RouterLink>
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

const name = ref('')
const email = ref('')
const password = ref('')

const fieldErrors = reactive<{ name?: string; email?: string; password?: string }>({})

function validate() {
  fieldErrors.name = undefined
  fieldErrors.email = undefined
  fieldErrors.password = undefined

  if (!name.value.trim()) fieldErrors.name = 'Name is required.'
  if (!email.value.trim()) fieldErrors.email = 'Email is required.'
  if (password.value.trim().length < 6) fieldErrors.password = 'Password must be at least 6 characters.'

  return !fieldErrors.name && !fieldErrors.email && !fieldErrors.password
}

async function onSubmit() {
  if (!validate()) return

  const ok = await auth.register(name.value, email.value, password.value)
  if (ok) {
    await auth.refreshMe()
    toasts.success('Account created successfully.')
    router.push({ name: 'projects' })
  }
}
</script>
