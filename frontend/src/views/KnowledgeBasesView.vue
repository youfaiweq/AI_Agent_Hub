<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage } from '@/api/http'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { KnowledgeBase, KnowledgeBasePayload } from '@/types/knowledge'

const store = useKnowledgeStore()
const router = useRouter()
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const form = reactive<KnowledgeBasePayload>({ name: '', description: '' })
const formError = ref<string | null>(null)
const saving = ref(false)

function openCreate(): void {
  editingId.value = null
  form.name = ''
  form.description = ''
  formError.value = null
  dialogVisible.value = true
}

function openEdit(item: KnowledgeBase): void {
  editingId.value = item.id
  form.name = item.name
  form.description = item.description ?? ''
  formError.value = null
  dialogVisible.value = true
}

async function save(): Promise<void> {
  if (!form.name.trim()) {
    formError.value = 'Knowledge base name is required.'
    return
  }
  saving.value = true
  formError.value = null
  try {
    if (editingId.value) {
      await store.update(editingId.value, { name: form.name, description: form.description || null })
      ElMessage.success('Knowledge base updated.')
    } else {
      await store.create({ name: form.name, description: form.description || null })
      ElMessage.success('Knowledge base created.')
    }
    dialogVisible.value = false
  } catch (error) {
    formError.value = getApiErrorMessage(error, 'Unable to save the knowledge base.')
  } finally {
    saving.value = false
  }
}

async function remove(item: KnowledgeBase): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Delete “${item.name}”? Documents in this knowledge base will also be removed.`,
      'Delete knowledge base',
      { type: 'warning', confirmButtonText: 'Delete', cancelButtonText: 'Cancel' },
    )
    await store.remove(item.id)
    ElMessage.success('Knowledge base deleted.')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, 'Unable to delete the knowledge base.'))
    }
  }
}

function openDetail(id: string): void {
  void router.push({ name: 'knowledge-base-detail', params: { id } })
}

function openRow(item: KnowledgeBase): void {
  openDetail(item.id)
}

onMounted(() => {
  void store.loadKnowledgeBases()
})
</script>

<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div>
        <p class="page-eyebrow">Knowledge foundation</p>
        <h2>Your knowledge bases</h2>
        <p class="page-copy">Organize source documents into private workspaces ready for future retrieval.</p>
      </div>
      <el-button type="primary" @click="openCreate">New knowledge base</el-button>
    </section>

    <el-alert v-if="store.error" :title="store.error" type="error" show-icon />

    <el-card shadow="never" class="content-card" v-loading="store.loading">
      <el-empty v-if="!store.loading && store.items.length === 0" description="No knowledge bases yet">
        <el-button type="primary" @click="openCreate">Create your first one</el-button>
      </el-empty>
      <el-table v-else-if="!store.loading" :data="store.items" row-class-name="clickable-row" @row-click="openRow">
        <el-table-column prop="name" label="Name" min-width="220">
          <template #default="{ row }">
            <div class="table-primary">{{ row.name }}</div>
            <div class="table-secondary">{{ row.description || 'No description' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="Documents" width="130">
          <template #default>—</template>
        </el-table-column>
        <el-table-column label="Updated" width="190">
          <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openEdit(row)">Edit</el-button>
            <el-button link type="danger" @click.stop="remove(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? 'Edit knowledge base' : 'New knowledge base'" width="520px">
      <el-alert v-if="formError" :title="formError" type="error" show-icon class="dialog-alert" />
      <el-form label-position="top" @submit.prevent="save">
        <el-form-item label="Name">
          <el-input v-model="form.name" maxlength="200" show-word-limit placeholder="e.g. Product documentation" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="5000" show-word-limit placeholder="What belongs in this knowledge base?" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>
