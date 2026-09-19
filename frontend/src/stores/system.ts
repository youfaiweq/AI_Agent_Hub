import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getHealth, getSystemInfo } from '@/api/system'
import type { HealthResponse, SystemInfo } from '@/types/system'

export const useSystemStore = defineStore('system', () => {
  const info = ref<SystemInfo | null>(null)
  const health = ref<HealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isHealthy = computed(() => health.value?.status === 'healthy')

  async function loadRuntimeStatus(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const [systemInfo, healthStatus] = await Promise.all([getSystemInfo(), getHealth()])
      info.value = systemInfo
      health.value = healthStatus
    } catch {
      error.value = 'Unable to connect to the AgentHub API.'
    } finally {
      loading.value = false
    }
  }

  return { info, health, loading, error, isHealthy, loadRuntimeStatus }
})
