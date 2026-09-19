<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { createAgent, listAgents } from '@/api/agents'
import { getApiErrorMessage } from '@/api/http'
import type { Agent, AgentCreatePayload, AgentToolName } from '@/types/agent'

const router = useRouter()
const agents = ref<Agent[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const dialogVisible = ref(false)
const saving = ref(false)
const formError = ref<string | null>(null)
const form = reactive<AgentCreatePayload>({
  name: '',
  description: '',
  system_prompt: '',
  model_name: 'qwen-plus',
  max_steps: 5,
  timeout_seconds: 60,
  tool_names: ['knowledge_search', 'calculator'],
})
const toolOptions: { label: string; value: AgentToolName }[] = [
  { label: 'Knowledge search', value: 'knowledge_search' },
  { label: 'Calculator', value: 'calculator' },
  { label: 'Read-only SQL', value: 'sql_query' },
  { label: 'Web search', value: 'web_search' },
]

function openCreate(): void {
  form.name = ''
  form.description = ''
  form.system_prompt = ''
  form.model_name = 'qwen-plus'
  form.max_steps = 5
  form.timeout_seconds = 60
  form.tool_names = ['knowledge_search', 'calculator']
  formError.value = null
  dialogVisible.value = true
}

async function save(): Promise<void> {
  if (!form.name.trim()) {
    formError.value = 'Agent name is required.'
    return
  }
  saving.value = true
  formError.value = null
  try {
    const created = await createAgent({ ...form, name: form.name.trim() })
    agents.value = [created, ...agents.value]
    dialogVisible.value = false
    ElMessage.success('Agent created.')
  } catch (requestError) {
    formError.value = getApiErrorMessage(requestError, 'Unable to create the Agent.')
  } finally {
    saving.value = false
  }
}

function openAgent(agent: Agent): void {
  void router.push({ name: 'agent-detail', params: { id: agent.id } })
}

onMounted(async () => {
  loading.value = true
  try {
    agents.value = await listAgents()
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError, 'Unable to load Agents.')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="workspace-page">
    <section class="page-intro">
      <div>
        <p class="page-eyebrow">Agent workspace</p>
        <h2>Your Agents</h2>
        <p class="page-copy">Configure bounded, observable Agents that can use the read-only tool layer.</p>
      </div>
      <el-button type="primary" @click="openCreate">New Agent</el-button>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon />
    <el-card shadow="never" class="content-card" v-loading="loading">
      <el-empty v-if="!loading && agents.length === 0" description="No Agents configured yet">
        <el-button type="primary" @click="openCreate">Create your first Agent</el-button>
      </el-empty>
      <el-table v-else :data="agents" row-class-name="clickable-row" @row-click="openAgent">
        <el-table-column prop="name" label="Agent" min-width="230">
          <template #default="{ row }">
            <div class="table-primary">{{ row.name }}</div>
            <div class="table-secondary">{{ row.description || 'No description' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="Model" width="150">
          <template #default="{ row }">{{ row.model_name }}</template>
        </el-table-column>
        <el-table-column label="Tools" min-width="250">
          <template #default="{ row }">
            <el-tag v-for="tool in row.tool_names" :key="tool" size="small" class="tool-tag">{{ tool }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Limits" width="150">
          <template #default="{ row }">{{ row.max_steps }} steps · {{ row.timeout_seconds }}s</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="New Agent" width="620px">
      <el-alert v-if="formError" :title="formError" type="error" show-icon class="dialog-alert" />
      <el-form label-position="top">
        <el-form-item label="Name">
          <el-input v-model="form.name" maxlength="200" placeholder="e.g. Research assistant" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="5000" />
        </el-form-item>
        <el-form-item label="System prompt">
          <el-input v-model="form.system_prompt" type="textarea" :rows="3" maxlength="20000" placeholder="Optional behavior guidance" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="Model">
            <el-input v-model="form.model_name" />
          </el-form-item>
          <el-form-item label="Max steps">
            <el-input-number v-model="form.max_steps" :min="1" :max="20" />
          </el-form-item>
          <el-form-item label="Timeout seconds">
            <el-input-number v-model="form.timeout_seconds" :min="1" :max="300" />
          </el-form-item>
        </div>
        <el-form-item label="Allowed tools">
          <el-checkbox-group v-model="form.tool_names">
            <el-checkbox v-for="tool in toolOptions" :key="tool.value" :label="tool.value">{{ tool.label }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="save">Create Agent</el-button>
      </template>
    </el-dialog>
  </div>
</template>
