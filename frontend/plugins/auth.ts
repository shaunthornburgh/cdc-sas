import type { FetchError } from 'ofetch'
import type { LoginResponse, TokenPair, User } from '~/types/auth'

type FetchOptions = NonNullable<Parameters<typeof $fetch>[1]>
export type ApiOptions = Omit<FetchOptions, 'baseURL' | 'headers'> & {
  headers?: Record<string, string>
}

// Matches the backend's JWT_REFRESH_TTL_DAYS. The access token's own expiry is checked
// by the API; when it lapses we refresh transparently.
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7

const isUnauthorized = (e: unknown) => (e as FetchError)?.response?.status === 401

/**
 * Auth state and an authenticated fetch, created once per app (per request on the server).
 * Tokens live in cookies so server-side rendering and route middleware can see the session.
 * Access them with useAuth() / useApi().
 */
export default defineNuxtPlugin(() => {
  const baseURL = useRuntimeConfig().public.apiBase
  const cookieOpts = {
    sameSite: 'lax' as const,
    secure: !import.meta.dev,
    maxAge: COOKIE_MAX_AGE,
    default: () => null,
  }
  const accessToken = useCookie<string | null>('cdc_access', cookieOpts)
  const refreshToken = useCookie<string | null>('cdc_refresh', cookieOpts)
  const user = useState<User | null>('auth:user', () => null)

  let refreshing: Promise<boolean> | null = null

  function setTokens(tokens: TokenPair) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
  }

  function clear() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
  }

  /** Swap the refresh token for a new pair. Concurrent callers share one request. */
  function refresh(): Promise<boolean> {
    if (!refreshToken.value) return Promise.resolve(false)
    refreshing ??= $fetch<TokenPair>('/auth/refresh', {
      baseURL,
      method: 'POST',
      body: { refresh_token: refreshToken.value },
    })
      .then((tokens) => {
        setTokens(tokens)
        return true
      })
      .catch((e) => {
        if (isUnauthorized(e)) clear()
        return false
      })
      .finally(() => {
        refreshing = null
      })
    return refreshing
  }

  /** $fetch against the API with the access token; retries once after a refresh on 401. */
  async function api<T>(url: string, opts: ApiOptions = {}): Promise<T> {
    const call = () =>
      $fetch<T>(url, {
        ...opts,
        baseURL,
        headers: {
          ...opts.headers,
          ...(accessToken.value ? { Authorization: `Bearer ${accessToken.value}` } : {}),
        },
      } as FetchOptions) as Promise<T>

    try {
      return await call()
    } catch (e) {
      if (isUnauthorized(e) && (await refresh())) return await call()
      throw e
    }
  }

  async function login(email: string, password: string): Promise<User> {
    const res = await $fetch<LoginResponse>('/auth/login', {
      baseURL,
      method: 'POST',
      body: { email, password },
    })
    setTokens(res)
    user.value = res.user
    return res.user
  }

  async function fetchMe(): Promise<User | null> {
    try {
      user.value = await api<User>('/auth/me')
    } catch (e) {
      if (isUnauthorized(e)) clear()
      else throw e
    }
    return user.value
  }

  /** The current user, loading it from the API if we have tokens but no user yet. */
  async function ensureUser(): Promise<User | null> {
    if (user.value) return user.value
    if (!accessToken.value && !refreshToken.value) return null
    try {
      return await fetchMe()
    } catch {
      return null // API unreachable: treat as logged out for this navigation, keep tokens
    }
  }

  async function logout() {
    const token = refreshToken.value
    await api('/auth/logout', { method: 'POST', body: { refresh_token: token } }).catch(() => {})
    clear()
    await navigateTo('/login')
  }

  return {
    provide: {
      auth: {
        user: readonly(user),
        isLoggedIn: computed(() => !!user.value),
        login,
        logout,
        refresh,
        fetchMe,
        ensureUser,
      },
      api,
    },
  }
})
