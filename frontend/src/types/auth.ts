export interface AuthUser {
  id: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface RegisterResponse {
  user: AuthUser
  token: TokenResponse
}
