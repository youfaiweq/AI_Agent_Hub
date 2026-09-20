<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const currentTitle = computed(() => String(route.meta.title ?? 'AgentHub'))

function logout(): void {
  authStore.logout()
  void router.push('/login')
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="248px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">A</div>
        <div>
          <div class="brand-name">AgentHub</div>
          <div class="brand-caption">AI application platform</div>
        </div>
      </div>

      <div class="sidebar-section-label">Workspace</div>
      <nav class="side-nav" aria-label="Main navigation">
        <RouterLink to="/dashboard" class="side-nav-item" active-class="is-active">
          <span class="nav-indicator" />
          Dashboard
        </RouterLink>
        <RouterLink to="/knowledge-bases" class="side-nav-item" active-class="is-active">
          <span class="nav-indicator" />
          Knowledge bases
        </RouterLink>
        <RouterLink to="/agents" class="side-nav-item" active-class="is-active">
          <span class="nav-indicator" />
          Agents
        </RouterLink>
        <RouterLink to="/memories" class="side-nav-item" active-class="is-active">
          <span class="nav-indicator" />
          Memory
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <span class="status-dot" />
        Job-ready v1.0
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <div class="page-eyebrow">AgentHub workspace</div>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="header-account">
          <span>{{ authStore.user?.email }}</span>
          <el-button link type="info" @click="logout">Sign out</el-button>
        </div>
      </el-header>

      <el-main class="app-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
