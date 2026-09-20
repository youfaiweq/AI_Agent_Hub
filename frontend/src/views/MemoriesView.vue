<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createMemory,
  deleteMemory,
  extractMemories,
  listMemories,
  updateMemory,
} from '@/api/memories'
import { getApiErrorMessage } from '@/api/http'
import type { LongTermMemory, MemoryCandidate, MemoryPayload, MemoryType } from '@/types/memory'

const memories = ref<LongTermMemory[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref('')
const extractionText = ref('')
const extracting = ref(false)
const candidate = ref<MemoryCandidate | null>(null)
const dialogVisible = ref(false)
const saving = ref(false)
const formError = ref<string | null>(null)
const editingId = ref<string | null>(null)
const form = reactive<MemoryPayload>({
  content: '',
  memory_type: 'fact',
  source: 'explicit_user',
  confidence: 1,
})
const memoryTypes: { label: string; value: MemoryType }[] = [
  { label: 'Fact', value: 'fact' },
  { label: 'Preference', value: 'preference' },
  { label: 'Instruction', value: 'instruction' },
  { label: 'Metric', value: 'metric' },
]

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const response = await listMemories(search.value.trim() || undefined)
    memories.value = response.items
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Unable to load memories.')
  } finally {
    loading.value = false
  }
}

function openCreate(initial?: MemoryCandidate, confirmed = false): void {
  editingId.value = null
  form.content = initial?.content ?? ''
  form.memory_type = initial?.memory_type ?? 'fact'
  form.source = confirmed ? 'user_confirmed' : initial?.source ?? 'explicit_user'
  form.confidence = initial?.confidence ?? 1
  formError.value = null
  dialogVisible.value = true
}

function openEdit(memory: LongTermMemory): void {
  editingId.value = memory.id
  form.content = memory.content
  form.memory_type = memory.memory_type
  form.source = memory.source
  form.confidence = memory.confidence
  formError.value = null
  dialogVisible.value = true
}

async function extract(): Promise<void> {
  if (!extractionText.value.trim()) return
  extracting.value = true
  error.value = null
  try {
    const response = await extractMemories(extractionText.value)
    candidate.value = response.candidates[0] ?? null
    if (!candidate.value) error.value = 'No explicit remember instruction was detected.'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Unable to extract a memory candidate.')
  } finally {
    extracting.value = false
  }
}

async function save(): Promise<void> {
  if (!form.content.trim()) {
    formError.value = 'Memory content is required.'
    return
  }
  saving.value = true
  formError.value = null
  try {
    if (editingId.value) {
      await updateMemory(editingId.value, {
        content: form.content.trim(),
        memory_type: form.memory_type,
        source: form.source,
        confidence: form.confidence,
      })
      ElMessage.success('Memory updated.')
    } else {
      await createMemory({
        content: form.content.trim(),
        memory_type: form.memory_type,
        source: form.source,
        confidence: form.confidence,
      })
      ElMessage.success('Memory saved.')
    }
    dialogVisible.value = false
    candidate.value = null
    extractionText.value = ''
    await load()
  } catch (requestError) {
    formError.value = getApiErrorMessage(requestError, 'Unable to save the memory.')
  } finally {
    saving.value = false
  }
}

async function remove(memory: LongTermMemory): Promise<void> {
  try {
    await ElMessageBox.confirm(`Delete “${memory.content}”?`, 'Delete memory', {
      type: 'warning',
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
    })
    await deleteMemory(memory.id)
    memories.value = memories.value.filter((item) => item.id !== memory.id)
    ElMessage.success('Memory deleted.')
  } catch (requestError) {
    if (requestError !== 'cancel' && requestError !== 'close') {
      ElMessage.error(getApiErrorMessage(requestError, 'Unable to delete the memory.'))
    }
  }
}

function sourceLabel(source: string): string {
  return source === 'user_confirmed' ? 'Confirmed' : 'Explicit'
}

onMounted(() => void load())
</script>

<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div>
        <p class="page-eyebrow">Personal context</p>
        <h2>Long-term memory</h2>
        <p class="page-copy">Save only facts and preferences you explicitly ask AgentHub to remember.</p>
      </div>
      <el-button type="primary" @click="openCreate()">New memory</el-button>
    </section>

    <el-card shadow="never" class="content-card memory-extractor">
      <div class="section-heading compact-heading">
        <div>
          <p class="page-eyebrow">Explicit extraction</p>
          <h3>Find a remember request</h3>
        </div>
      </div>
      <el-input
        v-model="extractionText"
        type="textarea"
        :rows="3"
        maxlength="20000"
        show-word-limit
        placeholder="Example: Remember that I prefer concise status updates."
      />
      <div class="run-actions">
        <el-button :loading="extracting" :disabled="!extractionText.trim()" @click="extract">Extract candidate</el-button>
      </div>
      <el-alert v-if="candidate" title="Candidate requires your confirmation before it is saved." type="info" show-icon>
        <template #default>
          <div>{{ candidate.content }}</div>
          <el-button type="primary" size="small" class="memory-confirm" @click="openCreate(candidate, true)">Confirm and save</el-button>
        </template>
      </el-alert>
    </el-card>

    <el-alert v-if="error" :title="error" type="error" show-icon />
    <el-card shadow="never" class="content-card" v-loading="loading">
      <div class="retrieval-controls">
        <el-input v-model="search" class="retrieval-query" clearable placeholder="Search memory content" @keyup.enter="load" />
        <el-button :loading="loading" @click="load">Search</el-button>
      </div>
      <el-empty v-if="!loading && memories.length === 0" description="No long-term memories yet" />
      <el-table v-else-if="!loading" :data="memories">
        <el-table-column prop="content" label="Memory" min-width="360" />
        <el-table-column label="Type" width="130">
          <template #default="{ row }"><el-tag size="small">{{ row.memory_type }}</el-tag></template>
        </el-table-column>
        <el-table-column label="Source" width="130">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column label="Updated" width="190">
          <template #default="{ row }">{{ new Date(row.updated_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">Edit</el-button>
            <el-button link type="danger" @click="remove(row)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? 'Edit memory' : 'New memory'" width="560px">
      <el-alert v-if="formError" :title="formError" type="error" show-icon class="dialog-alert" />
      <el-form label-position="top">
        <el-form-item label="Content">
          <el-input v-model="form.content" type="textarea" :rows="4" maxlength="4000" show-word-limit />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="Type">
            <el-select v-model="form.memory_type">
              <el-option v-for="item in memoryTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="Confidence">
            <el-input-number v-model="form.confidence" :min="0" :max="1" :step="0.1" />
          </el-form-item>
        </div>
        <div class="table-secondary">Source: {{ sourceLabel(form.source ?? 'explicit_user') }}. Only explicit or confirmed memories can be saved.</div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="save">Save memory</el-button>
      </template>
    </el-dialog>
  </div>
</template>
