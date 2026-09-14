import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { installRouter } from './router'
import { installMockApi } from './api/mock'
import { setUnauthorizedHandler } from './api/http'
import { useAuthStore } from './modules/auth/store'
import { useThemeStore } from './store/theme'
import { useToastsStore } from './store/toasts'

import './styles/main.css'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()

  pinia.use(({ store }) => {
    if (!('error' in store)) return

    let lastErrorKey: string | null = null

    store.$subscribe((_mutation, state) => {
      if (!state || typeof state !== 'object') return
      const next = (state as Record<string, unknown>).error

      if (!next) {
        lastErrorKey = null
        return
      }

      const nextKey = serializeError(next)
      if (nextKey && nextKey === lastErrorKey) return
      lastErrorKey = nextKey

      const toasts = useToastsStore(pinia)
      toasts.error(next)
    })
  })

  app.use(pinia)

  app.config.errorHandler = (err) => {
    const toasts = useToastsStore(pinia)
    toasts.error(err)
  }

  window.addEventListener('unhandledrejection', (evt) => {
    const toasts = useToastsStore(pinia)
    toasts.error(evt.reason)
  })

  const themeStore = useThemeStore(pinia)
  themeStore.init()

  const authStore = useAuthStore(pinia)
  authStore.hydrate()

  installMockApi(() => authStore.user)

  const router = installRouter(app)
  setUnauthorizedHandler(() => {
    authStore.logout()
    if (router.currentRoute.value.name !== 'login') {
      void router.replace({ name: 'login' })
    }
  })

  await authStore.refreshMe()
  await router.isReady()

  app.mount('#app')
}

bootstrap()

function serializeError(err: unknown) {
  try {
    return JSON.stringify(err)
  } catch {
    return String(err)
  }
}
