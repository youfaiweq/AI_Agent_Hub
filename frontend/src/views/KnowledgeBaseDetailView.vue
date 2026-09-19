<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage } from '@/api/http'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { DocumentItem } from '@/types/knowledge'

const route = useRoute()
const router = useRouter()
const store = useKnowledgeStore()
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const pageError = ref<string | null>(null)
const knowledgeBaseId = computed(() => String(route.params.id))
const allowedExtensions = ['.pdf', '.txt', '.md', '.markdown']

function triggerUpload(): void {
  fileInput.value?.click()
}

async function handleFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
  if (!allowedExtensions.includes(extension)) {
    ElMessage.error('Only PDF, TXT, and Markdown files are supported.')
    return
  }
  uploading.value = true
  try {
    await store.upload(knowledgeBaseId.value, file)
    ElMessage.success('Document uploaded.')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, 'Unable to upload the document.'))
  } finally {
    uploading.value = false
  }
}

async function removeDocument(document: DocumentItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`Delete “${document.filename}”?`, 'Delete document', {
      type: 'warning',
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
    })
    await store.removeDocument(knowledgeBaseId.value, document.id)
    ElMessage.success('Document deleted.')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, 'Unable to delete the document.'))
    }
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function statusType(status: DocumentItem['status']): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'uploaded' || status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

onMounted(async () => {
  try {
    await store.loadDetail(knowledgeBaseId.value)
  } catch (error) {
    pageError.value = getApiErrorMessage(error, 'Unable to load this knowledge base.')
  }
})
</script>

<template>
  <div class="workspace-page">
    <div class="breadcrumb-row">
      <el-button link @click="router.push('/knowledge-bases')">← Knowledge bases</el-button>
    </div>
    <el-alert v-if="pageError || store.error" :title="pageError || store.error || ''" type="error" show-icon />

    <section v-if="store.current" class="detail-hero">
      <div>
        <p class="page-eyebrow">Knowledge base</p>
        <h2>{{ store.current.name }}</h2>
        <p class="page-copy">{{ store.current.description || 'No description provided.' }}</p>
      </div>
      <div class="detail-actions">
        <el-button :loading="uploading" type="primary" @click="triggerUpload">Upload document</el-button>
        <input ref="fileInput" class="visually-hidden" type="file" accept=".pdf,.txt,.md,.markdown" @change="handleFileChange" />
      </div>
    </section>

    <el-card shadow="never" class="content-card" v-loading="store.loading">
      <div class="section-heading compact-heading">
        <div>
          <p class="page-eyebrow">Source files</p>
          <h3>Documents <span class="count-badge">{{ store.documents.length }}</span></h3>
        </div>
        <el-button :loading="uploading" @click="triggerUpload">Add document</el-button>
      </div>
      <el-empty v-if="!store.loading && store.documents.length === 0" description="No documents uploaded yet" />
      <el-table v-else :data="store.documents">
        <el-table-column prop="filename" label="File" min-width="250">
          <template #default="{ row }">
            <div class="table-primary">{{ row.filename }}</div>
            <div class="table-secondary">{{ row.content_type }}</div>
          </template>
        </el-table-column>
        <el-table-column label="Size" width="120">
          <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="Status" width="140">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Uploaded" width="190">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeDocument(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
