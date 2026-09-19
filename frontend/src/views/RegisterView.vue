<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const form = reactive({ email: '', password: '', confirmPassword: '' })
const validationError = ref<string | null>(null)

async function submit(): Promise<void> {
  validationError.value = null
  if (!form.email || !form.password) {
    validationError.value = 'Enter an email and password.'
    return
  }
  if (form.password.length < 8) {
    validationError.value = 'Password must be at least 8 characters.'
    return
  }
  if (form.password !== form.confirmPassword) {
    validationError.value = 'Passwords do not match.'
    return
  }
  try {
    await authStore.registerAccount({ email: form.email, password: form.password })
    ElMessage.success('Account created.')
    await router.push('/dashboard')
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
      <p class="page-eyebrow">Start your workspace</p>
      <h1>Create your account</h1>
      <p class="auth-copy">Begin with a private knowledge workspace for your team’s documents.</p>

      <el-alert v-if="validationError || authStore.error" :title="validationError || authStore.error || ''" type="error" show-icon />

      <el-form class="auth-form" label-position="top" @submit.prevent="submit">
        <el-form-item label="Email">
          <el-input v-model="form.email" type="email" autocomplete="email" placeholder="you@company.com" />
        </el-form-item>
        <el-form-item label="Password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="new-password"
            show-password
            placeholder="At least 8 characters"
          />
        </el-form-item>
        <el-form-item label="Confirm password">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            autocomplete="new-password"
            show-password
            placeholder="Repeat your password"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="authStore.loading">
          Create account
        </el-button>
      </el-form>

      <p class="auth-footer">Already have an account? <RouterLink to="/login">Sign in</RouterLink></p>
    </section>
  </main>
</template>
