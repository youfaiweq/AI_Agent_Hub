<script setup lang="ts">
import { reactive } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const form = reactive({ email: '', password: '' })

async function submit(): Promise<void> {
  if (!form.email || !form.password) {
    ElMessage.warning('Enter your email and password.')
    return
  }
  try {
    await authStore.loginWithCredentials(form)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.push(redirect)
  } catch {
    // The store exposes the safe API error to the form.
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card">
      <div class="auth-brand">
        <div class="brand-mark">A</div>
        <div>
          <div class="brand-name">AgentHub</div>
          <div class="brand-caption">AI application platform</div>
        </div>
      </div>
      <p class="page-eyebrow">Welcome back</p>
      <h1>Sign in to your workspace</h1>
      <p class="auth-copy">Manage enterprise knowledge and prepare reliable AI workflows.</p>

      <el-alert v-if="authStore.error" :title="authStore.error" type="error" show-icon />

      <el-form class="auth-form" label-position="top" @submit.prevent="submit">
        <el-form-item label="Email">
          <el-input v-model="form.email" type="email" autocomplete="email" placeholder="you@company.com" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
            placeholder="Your password"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="authStore.loading">
          Sign in
        </el-button>
      </el-form>

      <p class="auth-footer">New to AgentHub? <RouterLink to="/register">Create an account</RouterLink></p>
    </section>
  </main>
</template>
