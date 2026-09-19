<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const currentTitle = computed(() => String(route.meta.title ?? 'AgentHub'))
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
      </nav>

      <div class="sidebar-footer">
        <span class="status-dot" />
        Foundation v0.1
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <div class="page-eyebrow">AgentHub workspace</div>
          <h1>{{ currentTitle }}</h1>
        </div>
        <el-tag type="info" effect="plain">Development</el-tag>
      </el-header>

      <el-main class="app-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
