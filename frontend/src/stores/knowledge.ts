import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  createKnowledgeBase,
  deleteDocument,
  deleteKnowledgeBase,
  getKnowledgeBase,
  listDocuments,
  listKnowledgeBases,
  updateKnowledgeBase,
  uploadDocument,
} from '@/api/knowledge'
import { getApiErrorMessage } from '@/api/http'
import type {
  DocumentItem,
  KnowledgeBase,
  KnowledgeBasePayload,
} from '@/types/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const items = ref<KnowledgeBase[]>([])
  const current = ref<KnowledgeBase | null>(null)
  const documents = ref<DocumentItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadKnowledgeBases(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await listKnowledgeBases()
      items.value = response.items
      total.value = response.total
    } catch (requestError) {
      error.value = getApiErrorMessage(requestError, 'Unable to load knowledge bases.')
    } finally {
      loading.value = false
    }
  }

  async function create(payload: KnowledgeBasePayload): Promise<KnowledgeBase> {
    const created = await createKnowledgeBase(payload)
    items.value = [created, ...items.value]
    total.value += 1
    return created
  }

  async function update(id: string, payload: Partial<KnowledgeBasePayload>): Promise<KnowledgeBase> {
    const updated = await updateKnowledgeBase(id, payload)
    items.value = items.value.map((item) => (item.id === id ? updated : item))
    if (current.value?.id === id) current.value = updated
    return updated
  }

  async function remove(id: string): Promise<void> {
    await deleteKnowledgeBase(id)
    items.value = items.value.filter((item) => item.id !== id)
    total.value = Math.max(0, total.value - 1)
    if (current.value?.id === id) current.value = null
  }

  async function loadDetail(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const [knowledgeBase, documentResponse] = await Promise.all([getKnowledgeBase(id), listDocuments(id)])
      current.value = knowledgeBase
      documents.value = documentResponse.items
    } catch (requestError) {
      error.value = getApiErrorMessage(requestError, 'Unable to load this knowledge base.')
      throw requestError
    } finally {
      loading.value = false
    }
  }

  async function upload(id: string, file: File): Promise<DocumentItem> {
    const document = await uploadDocument(id, file)
    documents.value = [document, ...documents.value]
    return document
  }

  async function removeDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
    await deleteDocument(knowledgeBaseId, documentId)
    documents.value = documents.value.filter((document) => document.id !== documentId)
  }

  return {
    items,
    current,
    documents,
    total,
    loading,
    error,
    loadKnowledgeBases,
    create,
    update,
    remove,
    loadDetail,
    upload,
    removeDocument,
  }
})
