// API client for the Triada Network backend.
//
// The UI is served by the API on the same origin, so the base URL is empty by
// default; NEXT_PUBLIC_API_URL overrides it for split deployments.

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

// Canonical API prefix. The backend still serves the unversioned /api paths as
// aliases for older scripts; the bundled UI always talks to the current one.
const API_PREFIX = '/api/v1'

export interface BrowserSettings {
  os: string
  screen: string
  user_agent?: string | null
  languages?: string[]
  timezone?: string | null
  locale?: string | null
  window_width?: number | null
  window_height?: number | null
  geolocation?: {
    lat?: number
    lon?: number
    latitude?: number
    longitude?: number
    accuracy?: number
  } | null
  hardware_concurrency?: number | null
  device_memory?: number | null
  max_touch_points?: number
  webrtc_mode?: string
  /** Keep the canvas reproducible across launches, at the cost of cross-site unlinkability. */
  stable_canvas?: boolean
  canvas_noise?: boolean
  webgl_noise?: boolean
  audio_noise?: boolean
}

export interface ProxyConfig {
  type?: string
  server?: string
  username?: string | null
  password?: string | null
  country?: string | null
}

/** A short description of the machine a profile is pinned to. */
export interface FingerprintSummary {
  user_agent?: string | null
  platform?: string | null
  hardware_concurrency?: number | null
  screen?: string | null
  gpu?: string | null
  font_count?: number | null
  property_count?: number
  /** Firefox major version this pin claims. */
  browser_major?: number | null
  /** Firefox major version of the browser on disk. */
  installed_major?: number | null
  /** The pin claims an older browser than the one installed. */
  browser_outdated?: boolean
  /** The OS the pinned machine itself reports. */
  pinned_os?: string | null
  /** The OS the profile's settings ask for. */
  settings_os?: string | null
  /** The setting names one operating system and the pinned machine another. */
  os_mismatch?: boolean
}

export interface Profile {
  id: string
  name: string
  group?: string | null
  status: string
  browser_settings: BrowserSettings
  proxy_config?: ProxyConfig | null
  storage_path?: string | null
  notes?: string | null
  created_at: string
  updated_at?: string
  last_used?: string | null
  fingerprint?: FingerprintSummary | null
  /** Null until the proxy is checked, and again whenever the proxy changes. */
  proxy_check?: ProxyCheckRecord | null
}

export interface ProfilesResponse {
  profiles: Profile[]
  total: number
  page: number
  per_page: number
  has_next: boolean
  has_prev: boolean
}

export interface Group {
  id: string
  name: string
  description?: string | null
  created_at: string
  profile_count: number
}

export interface SystemStatus {
  total_profiles: number
  active_profiles: number
  running_browsers: number
  total_groups: number
  system_load: number
  memory_usage: number
  disk_usage: number
  uptime_seconds: number
}

const API_KEY_STORAGE = 'triada-network.api-key'

/** The key CPM_API_KEY expects, if the user has stored one. */
export function getApiKey(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(API_KEY_STORAGE) ?? ''
}

export function setApiKey(key: string): void {
  if (typeof window === 'undefined') return
  if (key) window.localStorage.setItem(API_KEY_STORAGE, key)
  else window.localStorage.removeItem(API_KEY_STORAGE)
}

export function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { 'X-API-Key': key } : {}
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    // Spread options first: putting it last let a caller's `headers` replace the
    // merged object, silently dropping Content-Type and the API key.
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options?.headers ?? {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      // Every API error carries error.message; detail is the legacy mirror,
      // kept as a fallback for anything not yet on the one error shape.
      const raw = body.error?.message ?? body.detail ?? body.message ?? detail
      detail = typeof raw === 'string' ? raw : JSON.stringify(raw)
    } catch {
      // response had no JSON body
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function toQuery(params: Record<string, unknown>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  return query.toString() ? `?${query.toString()}` : ''
}

export interface ProxyLocation {
  ip: string
  country: string | null
  timezone: string | null
  latitude: number | null
  longitude: number | null
}

export interface ProxyFinding {
  level: 'error' | 'warning' | 'info'
  field: string
  message: string
}

export interface ProxyCheck {
  reachable: boolean
  error: string | null
  latency_ms: number | null
  location: ProxyLocation | null
  findings: ProxyFinding[]
  /** Null when checking a proxy that is not saved yet, which is recorded nowhere. */
  checked_at: string | null
}

/** The last answer a profile's proxy gave, as the list shows it. */
export interface ProxyCheckRecord {
  checked_at: string
  reachable: boolean
  error: string | null
  latency_ms: number | null
  ip: string | null
  country: string | null
  timezone: string | null
  findings: ProxyFinding[]
}


export interface Workspace { id: string; name: string; workspace_type: 'personal' | 'team'; current_role?: string | null }
export interface WorkspaceMember { id: string; username: string; role: string }
export interface TriadaTag { id: string; name: string }
export interface ProxyPool { id: string; name: string; provider?: string | null; country?: string | null; proxy_type?: string | null; status: string; profile_count: number; proxy_count: number }
export interface ProfileOperations { profile_id: string; owner_id?: string | null; assigned_user_id?: string | null; proxy_pool_id?: string | null; proxy_id?: string | null; tag_ids: string[]; tags: TriadaTag[] }
export type OperationAction<T> = { action: 'unchanged' } | { action: 'set'; value: T } | { action: 'clear'; value?: null }
export interface ProfileOperationsPatch { owner?: OperationAction<string>; assigned_user?: OperationAction<string>; proxy_pool?: OperationAction<string>; tags?: OperationAction<string[]> }

export interface TeamSummary {
  members: number
  roles: Record<string, number>
  assigned_profiles: number
  owned_profiles: number
  unassigned_profiles: number
}

export interface TeamDashboard {
  workspace: Workspace
  summary: TeamSummary
  pending_invites: number
  recent_activity: Array<Record<string, unknown>>
}

export const operationsAPI = {
  getWorkspace(): Promise<Workspace> { return request<Workspace>(`${API_PREFIX}/ops/workspace`) },
  teamDashboard(): Promise<TeamDashboard> { return request<TeamDashboard>(`${API_PREFIX}/ops/team/dashboard`) },
  updateWorkspace(data: Partial<Workspace>): Promise<Workspace> { return request<Workspace>(`${API_PREFIX}/ops/workspace`, { method: 'PATCH', body: JSON.stringify(data) }) },
  getMembers(): Promise<WorkspaceMember[]> { return request<WorkspaceMember[]>(`${API_PREFIX}/ops/members`) },
  getTags(): Promise<TriadaTag[]> { return request<TriadaTag[]>(`${API_PREFIX}/ops/tags`) },
  createTag(name: string): Promise<TriadaTag> { return request<TriadaTag>(`${API_PREFIX}/ops/tags`, { method: 'POST', body: JSON.stringify({ name }) }) },
  createInvite(username: string, role: string): Promise<{id:string; invited_username:string; role:string; expires_at:string; token:string}> { return request(`${API_PREFIX}/ops/members/invites`, { method: 'POST', body: JSON.stringify({ username, role }) }) },
  getInvites(): Promise<Array<Record<string, unknown>>> { return request<Array<Record<string, unknown>>>(`${API_PREFIX}/ops/invites`) },
  updateMemberRole(username: string, role: string): Promise<WorkspaceMember> { return request(`${API_PREFIX}/ops/members/${encodeURIComponent(username)}`, { method: 'PATCH', body: JSON.stringify({ role }) }) },
  removeMember(username: string): Promise<{removed:boolean}> { return request(`${API_PREFIX}/ops/members/${encodeURIComponent(username)}`, { method: 'DELETE' }) },
  getProxyPools(): Promise<ProxyPool[]> { return request<ProxyPool[]>(`${API_PREFIX}/ops/proxy-pools`) },
  getAudit(params: { limit?: number; action?: string; actor_user_id?: string } = {}): Promise<Array<Record<string, unknown>>> { return request<Array<Record<string, unknown>>>(`${API_PREFIX}/ops/audit${toQuery(params)}`) },
  getAuditActions(): Promise<string[]> { return request<string[]>(`${API_PREFIX}/ops/audit/actions`) },
  createProxyPool(data: Record<string, unknown>): Promise<ProxyPool> { return request<ProxyPool>(`${API_PREFIX}/ops/proxy-pools`, { method: 'POST', body: JSON.stringify(data) }) },
  assignNext(poolId: string, profileId: string): Promise<ProxyInventory> { return request<ProxyInventory>(`${API_PREFIX}/ops/proxy-pools/${poolId}/assign-next`, { method: 'POST', body: JSON.stringify({ profile_id: profileId }) }) },
  getProfileOperations(id: string): Promise<ProfileOperations> { return request<ProfileOperations>(`${API_PREFIX}/ops/profiles/${id}/operations`) },
  updateProfileOperations(id: string, data: ProfileOperationsPatch): Promise<ProfileOperations> {
    return request<ProfileOperations>(`${API_PREFIX}/ops/profiles/${id}/operations`, { method: 'PUT', body: JSON.stringify(data) })
  },
  bulkUpdate(profile_ids: string[], data: ProfileOperationsPatch): Promise<{ updated: number }> {
    return request<{ updated: number }>(`${API_PREFIX}/ops/profiles/bulk`, { method: 'POST', body: JSON.stringify({ profile_ids, ...data }) })
  },
}

export interface UpdateCheckResult {
  configured: boolean
  update_available: boolean
  channel: 'stable' | 'beta' | string
  version: string
  download_url?: string | null
  sha256?: string | null
  installer_args?: string[]
  staged?: boolean
}

export interface PendingUpdate {
  pending: null | { version: string; channel: string; package: string; sha256: string; staged_at: string; installer_args?: string[] }
}

export const updateAPI = {
  check(payload: { manifest_url?: string; current_version?: string; public_key_b64?: string; channel?: 'stable' | 'beta' }): Promise<UpdateCheckResult> {
    return request<UpdateCheckResult>(`${API_PREFIX}/desktop/updates/check`, { method: 'POST', body: JSON.stringify(payload) })
  },
  stage(payload: { manifest_url?: string; current_version?: string; public_key_b64?: string; channel?: 'stable' | 'beta' }): Promise<UpdateCheckResult> {
    return request<UpdateCheckResult>(`${API_PREFIX}/desktop/updates/stage`, { method: 'POST', body: JSON.stringify(payload) })
  },
  pending(): Promise<PendingUpdate> {
    return request<PendingUpdate>(`${API_PREFIX}/desktop/updates/pending`)
  },
  install(): Promise<{ install_started: boolean; version: string; channel: string }> {
    return request(`${API_PREFIX}/desktop/updates/install`, { method: 'POST' })
  },
}

export interface ProxyInventory {
  id: string
  name: string
  workspace_id: string
  provider: string | null
  country: string | null
  proxy_type: string
  server: string
  username_set: boolean
  pool_id: string | null
  pool_name: string | null
  status: 'active' | 'disabled' | 'retired' | 'unknown' | 'healthy' | 'degraded' | 'unhealthy' | string
  latency_ms: number | null
  last_check_at: string | null
  exit_ip: string | null
  exit_country: string | null
  exit_timezone: string | null
  last_error: string | null
  assigned_profile_id: string | null
  assigned_profile_name: string | null
}

export const proxyAPI = {
  list(params: { pool_id?: string; status?: string } = {}): Promise<{ proxies: ProxyInventory[]; total: number }> {
    return request(`${API_PREFIX}/ops/proxies${toQuery(params)}`)
  },
  create(data: Record<string, unknown>): Promise<ProxyInventory> {
    return request<ProxyInventory>(`${API_PREFIX}/ops/proxies`, { method: 'POST', body: JSON.stringify(data) })
  },
  update(id: string, data: Record<string, unknown>): Promise<ProxyInventory> {
    return request<ProxyInventory>(`${API_PREFIX}/ops/proxies/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return request(`${API_PREFIX}/ops/proxies/${id}`, { method: 'DELETE' })
  },
  check(id: string): Promise<ProxyHealthResponse> {
    return request<ProxyHealthResponse>(`${API_PREFIX}/ops/proxies/${id}/check`, { method: 'POST' })
  },
  assign(id: string, profileId: string): Promise<ProxyInventory> {
    return request<ProxyInventory>(`${API_PREFIX}/ops/proxies/${id}/assign`, { method: 'POST', body: JSON.stringify({ profile_id: profileId }) })
  },
  unassign(id: string): Promise<ProxyInventory> {
    return request<ProxyInventory>(`${API_PREFIX}/ops/proxies/${id}/unassign`, { method: 'POST' })
  },
  bulkImportFile(file: File, params: { pool_id?: string; provider?: string; country?: string; proxy_type?: string } = {}): Promise<{ imported: number; errors: Array<{ line?: number; error: string }> }> {
    const form = new FormData()
    form.append('file', file)
    if (params.pool_id) form.append('pool_id', params.pool_id)
    if (params.provider) form.append('provider', params.provider)
    if (params.country) form.append('country', params.country)
    if (params.proxy_type) form.append('proxy_type', params.proxy_type)
    return fetch(`${API_BASE_URL}${API_PREFIX}/ops/proxies/bulk-import/file`, { method: 'POST', headers: authHeaders(), body: form }).then(async (response) => {
      if (!response.ok) {
        let detail = response.statusText
        try { const body = await response.json(); detail = body.error?.message ?? body.detail ?? detail } catch {}
        throw new Error(detail)
      }
      return response.json()
    })
  },
}

export interface ProxyHealthResponse {
  proxy: ProxyInventory
  reachable: boolean
  latency_ms: number | null
  error: string | null
  exit_ip: string | null
  exit_country: string | null
  exit_timezone: string | null
  findings: { level: 'error' | 'warning' | 'info'; field: string; message: string }[]
}

export const profilesAPI = {
  getProfiles(params: Record<string, unknown> = {}): Promise<ProfilesResponse> {
    return request<ProfilesResponse>(`${API_PREFIX}/profiles${toQuery(params)}`)
  },

  createProfile(data: Record<string, unknown>): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles`, { method: 'POST', body: JSON.stringify(data) })
  },

  updateProfile(id: string, data: Record<string, unknown>): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  },

  deleteProfile(id: string): Promise<void> {
    return request<void>(`${API_PREFIX}/profiles/${id}`, { method: 'DELETE' })
  },

  cloneProfile(id: string, newName: string): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify({ new_name: newName }),
    })
  },

  startProfile(id: string): Promise<unknown> {
    return request<unknown>(`${API_PREFIX}/profiles/${id}/launch`, {
      method: 'POST',
      body: JSON.stringify({ headless: false }),
    })
  },

  closeProfile(id: string): Promise<unknown> {
    return request<unknown>(`${API_PREFIX}/profiles/${id}/close`, { method: 'POST' })
  },

  resetFingerprint(id: string): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles/${id}/reset-fingerprint`, { method: 'POST' })
  },

  refreshBrowserVersion(id: string): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles/${id}/refresh-browser`, { method: 'POST' })
  },

  /** keepMachine: move the OS setting to the pin. Otherwise: pin new hardware for the setting. */
  reconcileOs(id: string, keepMachine: boolean): Promise<Profile> {
    return request<Profile>(`${API_PREFIX}/profiles/${id}/reconcile-os`, {
      method: 'POST',
      body: JSON.stringify({ keep_machine: keepMachine }),
    })
  },

  // Takes a list because the profiles this exists for — created when every one
  // was given a random region — are all of them at once.
  clearGeography(ids: string[]): Promise<ClearGeographyResult> {
    return request<ClearGeographyResult>(`${API_PREFIX}/profiles/clear-geography`, {
      method: 'POST',
      body: JSON.stringify({ profile_ids: ids }),
    })
  },

  checkProxy(id: string): Promise<ProxyCheck> {
    return request<ProxyCheck>(`${API_PREFIX}/profiles/${id}/check-proxy`, { method: 'POST' })
  },

  // The same check for a profile that is still being filled in, so the form can
  // answer before anything is saved.
  checkUnsavedProxy(body: {
    proxy_config: Record<string, unknown> | null
    browser_settings: Record<string, unknown>
  }): Promise<ProxyCheck> {
    return request<ProxyCheck>(`${API_PREFIX}/proxy/check`, { method: 'POST', body: JSON.stringify(body) })
  },

  async exportExcel(): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/export/excel`, {
      headers: authHeaders(),
    })
    if (!response.ok) throw new Error(response.statusText)
    return response.blob()
  },

  async exportArchive(id: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/${id}/export`, {
      headers: authHeaders(),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? response.statusText)
    }
    return response.blob()
  },

  async importArchive(file: File): Promise<Profile> {
    const body = new FormData()
    body.append('file', file)
    // No Content-Type: the browser has to set the multipart boundary itself.
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/import`, {
      method: 'POST',
      headers: authHeaders(),
      body,
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => null)
      throw new Error(detail?.detail ?? response.statusText)
    }
    return response.json() as Promise<Profile>
  },

  async importExcel(file: File): Promise<ImportResult> {
    const body = new FormData()
    body.append('file', file)
    // No Content-Type: the browser has to set the multipart boundary itself.
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/import/excel`, {
      method: 'POST',
      headers: authHeaders(),
      body,
    })
    return response.json() as Promise<ImportResult>
  },
}

export interface ClearGeographyResult {
  cleared: string[]
  unchanged: string[]
  not_found: string[]
}

export interface ImportResult {
  success: boolean
  message: string
  data?: { created_count?: number; errors?: string[] }
}

export interface DesktopDiagnostics {
  platform: string
  python: string
  camoufox_available: boolean
  active_browsers: number
  database_path: string
  disk_free_gb: number
  memory_percent: number
  log_directory: string
}

export const desktopAPI = {
  diagnostics(): Promise<DesktopDiagnostics> {
    return request<DesktopDiagnostics>(`${API_PREFIX}/system/desktop/diagnostics`)
  },
  createBackup(includeBrowserData = false): Promise<{ path: string }> {
    return request<{ path: string }>(`${API_PREFIX}/desktop/backups?include_browser_data=${includeBrowserData ? 'true' : 'false'}`, { method: 'POST' })
  },
  inspectBackup(file: File): Promise<Record<string, unknown>> {
    const form = new FormData(); form.append('file', file)
    return fetch(`${API_BASE_URL}${API_PREFIX}/desktop/backups/inspect`, { method: 'POST', headers: authHeaders(), body: form }).then(async (response) => {
      if (!response.ok) throw new Error(await response.text())
      const body = await response.json(); return body.data ?? body
    })
  },
  restoreBackup(file: File, includeBrowserData = false): Promise<null> {
    const form = new FormData(); form.append('file', file)
    return fetch(`${API_BASE_URL}${API_PREFIX}/desktop/backups/restore?include_browser_data=${includeBrowserData ? 'true' : 'false'}`, { method: 'POST', headers: authHeaders(), body: form }).then(async (response) => {
      if (!response.ok) throw new Error(await response.text())
      return null
    })
  },
}

export interface BrowserSession {
  profile_id: string
  process_id: number | null
  started_at: string
  uptime_seconds: number
  state: 'running' | 'orphaned' | string
  process_alive: boolean
  cpu_percent: number | null
  memory_mb: number | null
  command?: string | null
}

export const browsersAPI = {
  active(): Promise<{ active_browsers: { profile_id: string }[]; count: number }> {
    return request(`${API_PREFIX}/browsers/active`)
  },
  sessions(): Promise<{ sessions: BrowserSession[]; count: number }> {
    return request(`${API_PREFIX}/browsers/sessions`)
  },
  restart(profileId: string): Promise<unknown> {
    return request(`${API_PREFIX}/profiles/${profileId}/restart`, { method: 'POST' })
  },
  forceClose(profileId: string): Promise<unknown> {
    return request(`${API_PREFIX}/profiles/${profileId}/force-close`, { method: 'POST' })
  },
  reconcile(): Promise<{ reconciled: boolean; orphaned_profile_ids: string[]; count: number }> {
    return request(`${API_PREFIX}/browsers/reconcile`, { method: 'POST' })
  },
  closeAll(): Promise<{ closed_count: number; message: string }> {
    return request(`${API_PREFIX}/browsers/close-all`, { method: 'POST' })
  },
}

export const groupsAPI = {
  list(): Promise<{ groups: Group[]; total: number }> {
    return request(`${API_PREFIX}/groups`)
  },

  create(data: { name: string; description?: string }): Promise<Group> {
    return request<Group>(`${API_PREFIX}/groups`, { method: 'POST', body: JSON.stringify(data) })
  },

  update(id: string, data: { name?: string; description?: string }): Promise<Group> {
    return request<Group>(`${API_PREFIX}/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  },

  remove(id: string): Promise<void> {
    return request<void>(`${API_PREFIX}/groups/${id}`, { method: 'DELETE' })
  },
}

// --- Schedules ---------------------------------------------------------------

/** What a schedule does when it fires. Hardware regeneration is deliberately
 * not schedulable: it would hand a warmed-up account new hardware on a timer,
 * which is exactly what the pinned machine exists to prevent. */
export type ScheduleAction = 'launch' | 'refresh_browser'

export type ScheduleKind = 'interval' | 'daily'

export type ScheduleRunOutcome = 'ok' | 'skipped' | 'error' | 'missed'

export interface ScheduleRun {
  id: number | null
  schedule_id: string
  started_at: string
  finished_at: string | null
  outcome: ScheduleRunOutcome
  message: string | null
}

export interface Schedule {
  id: string
  profile_id: string
  profile_name: string | null
  action: ScheduleAction
  kind: ScheduleKind
  interval_minutes: number | null
  /** HH:MM on the server's clock. */
  at_time: string | null
  /** Weekdays a daily schedule fires, 0=Monday … 6=Sunday; null = every day. */
  days: number[] | null
  run_minutes: number | null
  enabled: boolean
  next_run_at: string | null
  last_run: ScheduleRun | null
  created_at: string
  updated_at: string
}

export interface SchedulePayload {
  profile_id?: string
  action?: ScheduleAction
  kind?: ScheduleKind
  interval_minutes?: number | null
  at_time?: string | null
  days?: number[] | null
  run_minutes?: number | null
  enabled?: boolean
}

export const schedulesAPI = {
  list(): Promise<{ schedules: Schedule[]; total: number }> {
    return request(`${API_PREFIX}/schedules`)
  },

  create(data: SchedulePayload): Promise<Schedule> {
    return request<Schedule>(`${API_PREFIX}/schedules`, { method: 'POST', body: JSON.stringify(data) })
  },

  update(id: string, data: SchedulePayload): Promise<Schedule> {
    return request<Schedule>(`${API_PREFIX}/schedules/${id}`, { method: 'PUT', body: JSON.stringify(data) })
  },

  remove(id: string): Promise<void> {
    return request<void>(`${API_PREFIX}/schedules/${id}`, { method: 'DELETE' })
  },

  runNow(id: string): Promise<ScheduleRun> {
    return request<ScheduleRun>(`${API_PREFIX}/schedules/${id}/run`, { method: 'POST' })
  },

  runs(id: string): Promise<{ runs: ScheduleRun[]; total: number }> {
    return request(`${API_PREFIX}/schedules/${id}/runs`)
  },
}

export interface SystemConfig {
  version: string
  host: string
  port: number
  database_path: string
  api_key_set: boolean
  user_auth_enabled: boolean
  encryption_enabled: boolean
  cors_origins: string[]
  camoufox_available: boolean
  uptime_seconds: number
}

/** A fingerprint captured from a real machine, bundled with Camoufox. */
export interface DevicePreset {
  id: string
  os: string
  screen?: string | null
  hardware_concurrency?: number | null
  gpu?: string | null
  vendor?: string | null
  user_agent?: string | null
}

export const presetsAPI = {
  async list(os?: string): Promise<DevicePreset[]> {
    const body = await request<{ data: { presets: DevicePreset[] } }>(
      `${API_PREFIX}/fingerprints/presets${toQuery({ os })}`,
    )
    return body.data.presets
  },
}

/** The caller's authentication state, from GET /auth/session. */
export interface AuthSession {
  user_auth_enabled: boolean
  authenticated: boolean
  username: string | null
}

// The session lives in an HttpOnly cookie the browser sends by itself on this
// same-origin app; nothing here stores or reads a token.
export const authAPI = {
  session(): Promise<AuthSession> {
    return request<AuthSession>(`${API_PREFIX}/auth/session`)
  },

  login(username: string, password: string): Promise<AuthSession> {
    return request<AuthSession>(`${API_PREFIX}/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  },

  logout(): Promise<unknown> {
    return request<unknown>(`${API_PREFIX}/auth/logout`, { method: 'POST' })
  },
}

export const systemAPI = {
  status(): Promise<SystemStatus> {
    return request<SystemStatus>(`${API_PREFIX}/system/status`)
  },

  async config(): Promise<SystemConfig> {
    const body = await request<{ data: SystemConfig }>(`${API_PREFIX}/system/config`)
    return body.data
  },
}

// --- Display helpers ---------------------------------------------------------

/** Whether a profile states where it is instead of letting its proxy say. */
export function hasGeography(profile: Profile): boolean {
  const bs = profile.browser_settings ?? {}
  return Boolean(bs.timezone || bs.geolocation)
}

export function formatProxyString(proxy?: ProxyConfig | null): string {
  if (!proxy || !proxy.server) return ''
  const scheme = proxy.type ? `${proxy.type}://` : ''
  return `${scheme}${proxy.server}`
}

/** How a checked proxy reads: what colour it is, and why.
 *
 * Derived rather than stored, so a row written by an older version cannot
 * disagree with the rules here. An error-level finding is red even when the
 * proxy answered — SOCKS credentials that Camoufox will drop means the launch
 * is wrong, which is not a milder problem than an unreachable proxy.
 */
export function readProxyCheck(check: ProxyCheckRecord): {
  tone: 'ok' | 'warn' | 'danger'
  label: string
  detail: string
} {
  const notes = check.findings.filter((finding) => finding.level !== 'info')
  const worst = notes.find((finding) => finding.level === 'error') ?? notes[0]
  // Repeats what the row shows on purpose: the line truncates, and an IPv6 exit
  // address is long enough to be cut off mid-address, taking the country and the
  // latency with it. The tooltip is the only place left to read them.
  const lines = [
    check.reachable ? 'Proxy answered' : 'Proxy did not answer',
    check.error,
    check.ip,
    [check.country, check.timezone].filter(Boolean).join(' · ') || null,
    check.latency_ms !== null ? `${check.latency_ms} ms` : null,
    ...notes.map((finding) => finding.message),
    `Checked ${formatLastUsed(check.checked_at).toLowerCase()}`,
  ].filter(Boolean)

  const tone = !check.reachable || worst?.level === 'error' ? 'danger' : worst ? 'warn' : 'ok'

  return {
    tone,
    // Green and amber differ only in hue at six pixels, which is exactly the
    // pair a deuteranope cannot separate. The table's other indicator pairs its
    // dot with a word; this one says the word to screen readers.
    label: tone === 'ok' ? 'Healthy' : tone === 'warn' ? 'Needs attention' : 'Failing',
    detail: lines.join('\n'),
  }
}

export function formatLastUsed(value?: string | null): string {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Never'

  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`
  return date.toLocaleDateString()
}

export const OS_LABELS: Record<string, string> = {
  windows: 'Windows',
  macos: 'macOS',
  linux: 'Linux',
}


export interface CloudWorkspace { id: string; name: string; workspace_type: string; role?: string | null; account_id: string }
export interface CloudAccount { id: string; name: string; workspace_count: number; created_at: string; updated_at: string }
export interface CloudApiKey { id: string; workspace_id: string; name: string; prefix: string; scopes: string[]; created_at: string; last_used_at?: string | null; expires_at?: string | null; revoked_at?: string | null; secret?: string | null }
export interface CloudDevice { id: string; account_id: string; user_id: string; name: string; platform?: string | null; app_version?: string | null; created_at: string; last_seen_at: string; revoked_at?: string | null }

export const cloudAPI = {
  me(): Promise<{ user_id: string; username: string | null; accounts: CloudAccount[]; workspaces: CloudWorkspace[] }> { return request(`${API_PREFIX}/cloud/me`) },
  workspaces(): Promise<CloudWorkspace[]> { return request(`${API_PREFIX}/cloud/workspaces`) },
  createWorkspace(name: string, workspace_type: 'personal'|'team' = 'personal'): Promise<CloudWorkspace> { return request(`${API_PREFIX}/cloud/workspaces`, { method:'POST', body: JSON.stringify({ name, workspace_type }) }) },
  selectWorkspace(id: string): Promise<{workspace_id:string}> { return request(`${API_PREFIX}/cloud/workspaces/${encodeURIComponent(id)}/select`, { method:'POST' }) },
  apiKeys(): Promise<CloudApiKey[]> { return request(`${API_PREFIX}/cloud/api-keys`) },
  createApiKey(name: string, scopes: string[], expires_days?: number): Promise<CloudApiKey> { return request(`${API_PREFIX}/cloud/api-keys`, { method:'POST', body:JSON.stringify({name, scopes, expires_days}) }) },
  revokeApiKey(id: string): Promise<{revoked:boolean}> { return request(`${API_PREFIX}/cloud/api-keys/${encodeURIComponent(id)}`, { method:'DELETE' }) },
  devices(): Promise<CloudDevice[]> { return request(`${API_PREFIX}/cloud/devices`) },
  pullSync(after_revision=0): Promise<{workspace_id:string;revision:number;records:Array<Record<string,unknown>>;has_more:boolean}> { return request(`${API_PREFIX}/cloud/sync?after_revision=${after_revision}`) },
  pushSync(entity_type:string, entity_id:string, payload:Record<string,unknown>, expected_revision?:number) { return request(`${API_PREFIX}/cloud/sync`, {method:'POST', body:JSON.stringify({entity_type,entity_id,payload,expected_revision})}) },
  syncProfiles(): Promise<{pushed:number}> { return request(`${API_PREFIX}/cloud/sync/profiles`, {method:'POST'}) },
}

export interface TrashProfile { profile_id: string; name: string; status: string; deleted_at: string; owner_id?: string|null; assigned_user_id?: string|null; tags: Array<{id:string;name:string}> }
export const trashAPI = {
  list(): Promise<TrashProfile[]> { return request(`${API_PREFIX}/profiles/trash`) },
  restore(id: string): Promise<Profile> { return request(`${API_PREFIX}/profiles/trash/${id}/restore`, { method: 'POST' }) },
  purge(id: string): Promise<void> { return request(`${API_PREFIX}/profiles/trash/${id}`, { method: 'DELETE' }) },
}
export async function exportCookies(id: string): Promise<Blob> {
  const r=await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/${id}/cookies/export`, { headers: authHeaders() }); if(!r.ok) throw new Error(await r.text()); return r.blob()
}
export async function importCookies(id: string, file: File): Promise<{profile_id:string; imported:number}> {
  const form=new FormData(); form.append('file',file); const r=await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/${id}/cookies/import`, { method:'POST', headers:authHeaders(), body:form }); if(!r.ok) throw new Error(await r.text()); return r.json()
}


export async function exportCookiesBulk(profileIds: string[]): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/cookies/export-bulk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ profile_ids: profileIds }),
  })
  if (!response.ok) throw new Error(`Cookie export failed (${response.status})`)
  return response.blob()
}

export async function importCookiesBulk(file: File): Promise<{created_count:number; error_count:number; created:Array<{profile_id:string;name:string;cookies:number}>; errors:Array<{file:string;error:string}>}> {
  const form = new FormData(); form.append('file', file)
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/cookies/import-bulk`, { method: 'POST', headers: authHeaders(), body: form })
  if (!response.ok) {
    let detail = response.statusText; try { const body = await response.json(); detail = body.error?.message ?? body.detail ?? detail } catch {}
    throw new Error(detail)
  }
  return response.json()
}


export const api = {
  async get<T>(path: string): Promise<T> {
    return request<T>(path, { credentials: 'include' })
  },
  async post<T = unknown>(path: string, body: unknown): Promise<T> {
    return request<T>(path, { method: 'POST', credentials: 'include', body: JSON.stringify(body) })
  },
};


export type IntegrityReport = {
  ok: boolean
  database: { path: string; exists: boolean; integrity: string | null }
  profiles: { referenced: number; directories: number; missing: string[]; orphaned: string[] }
  warnings: string[]
}

export type DesktopDataStatus = {
  app: string
  version: string
  migration: { current: number; target: number; pending: number[]; up_to_date: boolean }
  recovery: { rollback_available: boolean; quarantine_entries: number }
}

export type QuarantineResult = { count: number; entries?: string[] }
export type SupportBundleResult = { path: string; sha256?: string; size_bytes?: number }
export type MigrationResult = { current: number; target: number; applied?: number[]; pending?: number[] }
export type BackupResult = { path: string; sha256?: string; size_bytes?: number }
export const securityAPI = {
  integrity: (): Promise<IntegrityReport> => api.get<IntegrityReport>('/api/v1/desktop/integrity'),
  status: (): Promise<DesktopDataStatus> => api.get<DesktopDataStatus>('/api/v1/desktop/data/status'),
  migrate: (): Promise<MigrationResult> => api.post<MigrationResult>('/api/v1/desktop/data/migrate', {}),
  recovery: (): Promise<DesktopDataStatus> => api.get<DesktopDataStatus>('/api/v1/desktop/data/status'),
  rollbackLastRestore: (): Promise<{ ok: boolean; path?: string }> => api.post('/api/v1/desktop/recovery/rollback-last-restore', {}),
  quarantineOrphans: (): Promise<QuarantineResult> => api.post('/api/v1/desktop/recovery/quarantine-orphans', {}),
  createSupportBundle: (): Promise<SupportBundleResult> => api.post('/api/v1/desktop/support-bundle', {}),
  createBackup: (includeBrowserData = false): Promise<BackupResult> => api.post(`/api/v1/desktop/backups?include_browser_data=${includeBrowserData ? 'true' : 'false'}`, {}),
  updateCheck: (manifest_url?: string): Promise<UpdateCheckResult> => api.post('/api/v1/desktop/updates/check', { manifest_url }),
  pendingUpdate: (): Promise<PendingUpdate> => api.get<PendingUpdate>('/api/v1/desktop/updates/pending'),
}

export const secureCookieAPI = {
  async export(profileIds: string[], password: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/cookies/export-secure`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ profile_ids: profileIds, password }),
    })
    if (!response.ok) throw new Error(`Secure cookie export failed (${response.status})`)
    return response.blob()
  },
  async import(file: File, password: string): Promise<{created_count:number; error_count:number; created:Array<{profile_id:string;name:string;cookies:number}>; errors:Array<{file:string;error:string}>}> {
    const form = new FormData(); form.append('file', file); form.append('password', password)
    const response = await fetch(`${API_BASE_URL}${API_PREFIX}/profiles/cookies/import-secure`, { method:'POST', headers:authHeaders(), body:form })
    if (!response.ok) { let detail=response.statusText; try { const body=await response.json(); detail=body.error?.message ?? body.detail ?? detail } catch {} ; throw new Error(detail) }
    return response.json()
  },
}
