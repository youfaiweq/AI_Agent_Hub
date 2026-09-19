<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useSystemStore } from '@/stores/system'
import type { ServiceHealth } from '@/types/system'

const systemStore = useSystemStore()
const services = computed((): Array<[string, ServiceHealth]> => {
  return Object.entries(systemStore.health?.services ?? {})
})

function formatServiceName(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function formatLatency(latency: number | null): string {
  return latency === null ? '—' : `${latency} ms`
}

onMounted(() => {
  void systemStore.loadRuntimeStatus()
})
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-panel">
      <div>
        <p class="page-eyebrow">Foundation layer</p>
        <h2>Build reliable AI workflows.</h2>
        <p class="hero-copy">
          AgentHub brings enterprise knowledge, data tools, and observable agent runs into one
          modular workspace.
        </p>
      </div>
      <div class="hero-badge">v0.1</div>
    </section>

    <el-alert v-if="systemStore.error" :title="systemStore.error" type="warning" show-icon />

    <section class="summary-grid" aria-label="Runtime summary">
      <el-card shadow="never" class="summary-card">
        <div class="card-label">Application</div>
        <div class="card-value">{{ systemStore.info?.name ?? 'Loading…' }}</div>
        <div class="card-meta">Version {{ systemStore.info?.version ?? '—' }}</div>
      </el-card>
      <el-card shadow="never" class="summary-card">
        <div class="card-label">Runtime status</div>
        <div class="card-value status-value">
          <span :class="['status-dot', systemStore.isHealthy ? 'is-healthy' : 'is-degraded']" />
          {{ systemStore.health?.status ?? (systemStore.loading ? 'Checking…' : 'Unknown') }}
        </div>
        <div class="card-meta">Environment: {{ systemStore.info?.environment ?? '—' }}</div>
      </el-card>
      <el-card shadow="never" class="summary-card">
        <div class="card-label">Next milestone</div>
        <div class="card-value">Knowledge foundation</div>
        <div class="card-meta">Auth and knowledge base are next</div>
      </el-card>
    </section>

    <section class="section-heading">
      <div>
        <p class="page-eyebrow">Infrastructure</p>
        <h3>Service health</h3>
      </div>
      <el-button :loading="systemStore.loading" @click="systemStore.loadRuntimeStatus">
        Refresh
      </el-button>
    </section>

    <el-card shadow="never" class="service-card">
      <div v-if="systemStore.loading && services.length === 0" class="empty-state">
        Checking infrastructure services…
      </div>
      <div v-else-if="services.length === 0" class="empty-state">
        No service data available.
      </div>
      <div v-else class="service-list">
        <div v-for="[name, service] in services" :key="name" class="service-row">
          <div class="service-name">
            <span :class="['status-dot', service.status === 'healthy' ? 'is-healthy' : 'is-degraded']" />
            {{ formatServiceName(name) }}
          </div>
          <div class="service-latency">{{ formatLatency(service.latency_ms) }}</div>
          <el-tag :type="service.status === 'healthy' ? 'success' : 'warning'" size="small">
            {{ service.status }}
          </el-tag>
        </div>
      </div>
    </el-card>
  </div>
</template>
