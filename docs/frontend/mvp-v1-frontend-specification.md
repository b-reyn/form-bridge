# Form-Bridge MVPv1 Frontend Specification

*Version: 1.0*  
*Date: January 26, 2025*  
*Status: Ready for Implementation*

## Executive Summary

This document defines the MVPv1 frontend implementation for Form-Bridge, a multi-tenant serverless form ingestion and fan-out platform. The frontend provides a React-based admin dashboard for managing WordPress site connections, configuring destinations, and monitoring form submissions. This specification synthesizes requirements from product, UX research, WordPress integration patterns, and the EventBridge-centric backend architecture.

**Key MVPv1 Goals:**
- 5-minute WordPress plugin setup
- Support for 1-50 sites per client
- Real-time submission monitoring
- Simple destination configuration
- $50/month operational cost target

---

## 1. Architecture Overview

### 1.1 System Integration

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Dashboard │  │  Sites   │  │  Routes  │  │ Settings │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│       │             │             │             │            │
│  ┌───────────────────────────────────────────────────┐      │
│  │              Zustand State Management             │      │
│  └───────────────────────────────────────────────────┘      │
│       │                                                      │
│  ┌───────────────────────────────────────────────────┐      │
│  │          TanStack Query (API Layer)               │      │
│  └───────────────────────────────────────────────────┘      │
└────────────────────────│─────────────────────────────────────┘
                         │
                    HTTPS + JWT
                         │
         ┌───────────────▼────────────────┐
         │   API Gateway + Cognito Auth   │
         └───────────────┬────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                     │
    ▼                    ▼                     ▼
EventBridge          DynamoDB            Lambda Functions
(Events)          (Persistence)         (Processing)
```

### 1.2 Authentication Flow

```typescript
// Authentication sequence
1. User registers via Cognito hosted UI
2. Receives JWT tokens (access + refresh)
3. Frontend stores tokens securely (httpOnly cookies preferred)
4. All API calls include Authorization: Bearer {token}
5. Token refresh handled automatically by TanStack Query
```

### 1.3 Multi-Tenant Data Isolation

```typescript
// Every API request includes tenant context
interface TenantContext {
  tenant_id: string;        // e.g., "t_abc123"
  organization_name: string; // e.g., "Acme Agency"
  subscription_tier: 'free' | 'starter' | 'pro';
  site_limit: number;       // Based on tier
}

// Frontend enforces tenant isolation
const useTenantData = () => {
  const { tenant_id } = useAuthContext();
  return useQuery({
    queryKey: ['tenant', tenant_id],
    queryFn: () => api.getTenantData(tenant_id),
    // Data is automatically scoped to authenticated tenant
  });
};
```

### 1.4 Real-time Updates Strategy

**MVP Approach: Polling with smart intervals**
```typescript
// Progressive polling based on activity
const POLL_INTERVALS = {
  active: 5000,    // 5s when viewing dashboard
  idle: 30000,     // 30s when tab is backgrounded
  inactive: 60000  // 1min after 5min of no activity
};

// Future V2: WebSocket via AWS IoT Core for true real-time
```

---

## 2. Core Features (MVP)

### 2.1 User Registration/Login

**Implementation:**
```typescript
// Cognito Hosted UI integration
const AuthConfig = {
  domain: 'formbridge.auth.us-east-1.amazoncognito.com',
  clientId: process.env.VITE_COGNITO_CLIENT_ID,
  redirectUri: window.location.origin + '/auth/callback',
  scopes: ['openid', 'profile', 'email'],
  responseType: 'code',
  
  // MVP: Email/password only
  // V2: Social login (Google, Microsoft)
};

// Component structure
<AuthProvider>
  <Routes>
    <Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="/login" element={<LoginPage />} />
    <Route path="/*" element={
      <RequireAuth>
        <Dashboard />
      </RequireAuth>
    } />
  </Routes>
</AuthProvider>
```

### 2.2 Dashboard Overview

**Component Structure:**
```typescript
interface DashboardMetrics {
  totalSubmissions24h: number;
  activesSites: number;
  failedDeliveries: number;
  successRate: number;
  topForms: Array<{
    form_id: string;
    site_name: string;
    count: number;
  }>;
}

const Dashboard: React.FC = () => {
  const { data: metrics } = useMetrics();
  const { data: recentActivity } = useRecentActivity();
  
  return (
    <DashboardLayout>
      {/* Key Metrics Cards */}
      <MetricGrid>
        <MetricCard 
          title="24h Submissions" 
          value={metrics.totalSubmissions24h}
          trend={metrics.submissionsTrend}
        />
        <MetricCard 
          title="Active Sites" 
          value={metrics.activeSites}
          status="healthy"
        />
        <MetricCard 
          title="Success Rate" 
          value={`${metrics.successRate}%`}
          threshold={99}
        />
      </MetricGrid>
      
      {/* Activity Feed */}
      <ActivityFeed 
        items={recentActivity}
        onItemClick={navigateToSubmission}
      />
      
      {/* Quick Actions */}
      <QuickActions>
        <Button onClick={openAddSite}>Connect New Site</Button>
        <Button onClick={openDestinations}>Configure Routes</Button>
      </QuickActions>
    </DashboardLayout>
  );
};
```

### 2.3 WordPress Plugin Management

**Self-Registration Flow:**
```typescript
interface SiteRegistration {
  // Step 1: Generate credentials
  generateCredentials(): {
    site_id: string;
    api_key: string;
    shared_secret: string;
  };
  
  // Step 2: Provide plugin download
  getPluginDownload(): {
    download_url: string;
    install_instructions: string;
  };
  
  // Step 3: Verify connection
  verifyConnection(site_id: string): Promise<{
    status: 'pending' | 'connected' | 'error';
    last_ping?: string;
  }>;
}

// UI Implementation
const AddWordPressSite: React.FC = () => {
  const [step, setStep] = useState<'generate' | 'install' | 'verify'>('generate');
  const [credentials, setCredentials] = useState<Credentials>();
  
  return (
    <WizardLayout currentStep={step}>
      {step === 'generate' && (
        <GenerateCredentialsStep
          onGenerate={(creds) => {
            setCredentials(creds);
            setStep('install');
          }}
        />
      )}
      
      {step === 'install' && (
        <InstallPluginStep
          credentials={credentials}
          downloadUrl="/api/plugin/download"
          onContinue={() => setStep('verify')}
        />
      )}
      
      {step === 'verify' && (
        <VerifyConnectionStep
          siteId={credentials.site_id}
          onSuccess={() => navigate('/sites')}
        />
      )}
    </WizardLayout>
  );
};
```

### 2.4 Destination Configuration

**Route Builder Interface:**
```typescript
interface DestinationConfig {
  id: string;
  name: string;
  type: 'webhook' | 'database' | 'email' | 'crm';
  config: {
    endpoint?: string;
    method?: 'POST' | 'PUT';
    headers?: Record<string, string>;
    auth?: {
      type: 'none' | 'bearer' | 'basic' | 'api_key';
      credentials_ref?: string; // Secrets Manager reference
    };
    field_mapping?: Array<{
      source: string;
      target: string;
      transform?: 'lowercase' | 'uppercase' | 'trim';
    }>;
  };
  filters?: Array<{
    field: string;
    operator: 'equals' | 'contains' | 'regex';
    value: string;
  }>;
  enabled: boolean;
}

// Visual Route Builder
const RouteBuilder: React.FC = () => {
  const { control, handleSubmit } = useForm<DestinationConfig>();
  
  return (
    <Form onSubmit={handleSubmit(saveDestination)}>
      {/* Destination Type Selection */}
      <DestinationTypeSelector control={control} />
      
      {/* Dynamic Configuration Based on Type */}
      <DynamicConfigFields control={control} />
      
      {/* Visual Field Mapper */}
      <FieldMapper
        sourceFields={getAvailableFields()}
        control={control}
      />
      
      {/* Test Connection */}
      <TestConnection
        config={watch()}
        onTest={testDestination}
      />
    </Form>
  );
};
```

### 2.5 Form Submission Monitoring

**Real-time Activity View:**
```typescript
interface SubmissionView {
  id: string;
  tenant_id: string;
  site_name: string;
  form_id: string;
  submitted_at: string;
  status: 'received' | 'processing' | 'delivered' | 'failed';
  delivery_attempts: Array<{
    destination_id: string;
    destination_name: string;
    status: 'success' | 'failed' | 'pending';
    response_code?: number;
    error_message?: string;
    duration_ms: number;
  }>;
  payload: Record<string, any>;
}

const SubmissionMonitor: React.FC = () => {
  const { data, isLoading } = useSubmissions({
    polling: true,
    interval: 5000
  });
  
  return (
    <MonitorLayout>
      {/* Status filters */}
      <StatusFilter />
      
      {/* Submission table with TanStack Table */}
      <SubmissionsTable
        data={data}
        columns={[
          { header: 'Time', accessor: 'submitted_at' },
          { header: 'Site', accessor: 'site_name' },
          { header: 'Form', accessor: 'form_id' },
          { header: 'Status', accessor: 'status', cell: StatusBadge },
          { header: 'Deliveries', accessor: 'delivery_attempts', cell: DeliveryStatus }
        ]}
        onRowClick={openSubmissionDetails}
      />
      
      {/* Real-time status indicator */}
      <ConnectionStatus polling={true} lastUpdate={data?.timestamp} />
    </MonitorLayout>
  );
};
```

---

## 3. WordPress Plugin Strategy

### 3.1 Self-Registration Mechanism

**HMAC Authentication Implementation:**
```php
// WordPress plugin side
class FormBridge_Connection {
    private $api_endpoint = 'https://api.form-bridge.com/ingest';
    
    public function register_site() {
        // Generate unique site identifier
        $site_id = wp_generate_uuid4();
        
        // Request credentials from Form-Bridge API
        $response = wp_remote_post($this->api_endpoint . '/register', [
            'body' => json_encode([
                'site_url' => get_site_url(),
                'site_name' => get_bloginfo('name'),
                'admin_email' => get_option('admin_email')
            ])
        ]);
        
        $credentials = json_decode(wp_remote_retrieve_body($response), true);
        
        // Store securely in WordPress
        update_option('formbridge_site_id', $credentials['site_id']);
        update_option('formbridge_api_key', $credentials['api_key']);
        update_option('formbridge_shared_secret', $credentials['shared_secret']);
        
        return $credentials;
    }
    
    public function send_submission($form_data) {
        $timestamp = gmdate('c');
        $body = json_encode($form_data);
        
        // Generate HMAC signature
        $signature = hash_hmac(
            'sha256',
            $timestamp . "\n" . $body,
            get_option('formbridge_shared_secret')
        );
        
        // Send to Form-Bridge
        return wp_remote_post($this->api_endpoint, [
            'headers' => [
                'X-Tenant-Id' => get_option('formbridge_site_id'),
                'X-Timestamp' => $timestamp,
                'X-Signature' => $signature,
                'Content-Type' => 'application/json'
            ],
            'body' => $body
        ]);
    }
}
```

### 3.2 Bulk Site Management

**Frontend Bulk Operations:**
```typescript
interface BulkSiteManager {
  sites: Array<{
    id: string;
    name: string;
    url: string;
    status: 'active' | 'inactive' | 'error';
    last_submission?: string;
    plugin_version?: string;
  }>;
  
  operations: {
    selectAll(): void;
    selectGroup(tag: string): void;
    updatePlugins(site_ids: string[]): Promise<void>;
    regenerateCredentials(site_ids: string[]): Promise<void>;
    exportConfiguration(site_ids: string[]): void;
  };
}

const BulkSiteManagement: React.FC = () => {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  
  return (
    <div>
      {/* Bulk action bar */}
      <BulkActionBar
        selectedCount={selected.size}
        actions={[
          { label: 'Update Plugin', onClick: updateSelected },
          { label: 'Regenerate Keys', onClick: regenerateKeys },
          { label: 'Export Config', onClick: exportConfig },
          { label: 'Add to Group', onClick: showGroupDialog }
        ]}
      />
      
      {/* Site grid with selection */}
      <SiteGrid
        sites={sites}
        selected={selected}
        onToggle={toggleSelection}
        renderSite={(site) => (
          <SiteCard
            {...site}
            actions={
              <SiteActions
                onUpdate={() => updateSite(site.id)}
                onViewDetails={() => navigate(`/sites/${site.id}`)}
              />
            }
          />
        )}
      />
    </div>
  );
};
```

### 3.3 Plugin Distribution

**Download & Update System:**
```typescript
// Frontend plugin distribution
interface PluginDistribution {
  getLatestVersion(): string;
  generateDownloadUrl(site_id: string): string;
  trackDownload(site_id: string): void;
  checkUpdates(current_version: string): boolean;
}

// API endpoint implementation
app.get('/api/plugin/download', authenticate, async (req, res) => {
  const { tenant_id } = req.user;
  
  // Generate personalized plugin with embedded credentials
  const plugin = await generatePlugin({
    tenant_id,
    site_id: req.query.site_id,
    api_endpoint: process.env.API_GATEWAY_URL
  });
  
  // Track download
  await trackDownload(tenant_id, req.query.site_id);
  
  // Return zip file
  res.setHeader('Content-Type', 'application/zip');
  res.setHeader('Content-Disposition', 'attachment; filename="form-bridge.zip"');
  res.send(plugin);
});
```

---

## 4. Multi-Site Management Solution

### 4.1 Site Grouping Architecture

```typescript
interface SiteGroup {
  id: string;
  name: string;
  tenant_id: string;
  site_ids: string[];
  settings: {
    inherit_destinations: boolean;
    inherit_credentials: boolean;
    custom_config?: Record<string, any>;
  };
  tags: string[];
}

// State management with Zustand
interface SiteStore {
  sites: Map<string, Site>;
  groups: Map<string, SiteGroup>;
  
  // Actions
  addSite: (site: Site) => void;
  createGroup: (name: string, site_ids: string[]) => void;
  applyGroupSettings: (group_id: string, settings: any) => void;
  
  // Computed
  getSitesByGroup: (group_id: string) => Site[];
  getSitesByTag: (tag: string) => Site[];
}

const useSiteStore = create<SiteStore>((set, get) => ({
  sites: new Map(),
  groups: new Map(),
  
  addSite: (site) => set((state) => {
    state.sites.set(site.id, site);
    return { sites: new Map(state.sites) };
  }),
  
  createGroup: (name, site_ids) => set((state) => {
    const group: SiteGroup = {
      id: generateId(),
      name,
      tenant_id: getCurrentTenant(),
      site_ids,
      settings: { inherit_destinations: true, inherit_credentials: false },
      tags: []
    };
    state.groups.set(group.id, group);
    return { groups: new Map(state.groups) };
  }),
  
  getSitesByGroup: (group_id) => {
    const group = get().groups.get(group_id);
    if (!group) return [];
    return group.site_ids.map(id => get().sites.get(id)).filter(Boolean);
  }
}));
```

### 4.2 Credential Inheritance Model

```typescript
interface CredentialInheritance {
  // Group-level credentials
  group_credentials: {
    api_key: string;
    shared_secret: string;
    destinations: DestinationConfig[];
  };
  
  // Site can override or inherit
  site_overrides?: {
    use_group_credentials: boolean;
    custom_destinations?: DestinationConfig[];
    custom_api_key?: string;
  };
}

// Implementation
const getEffectiveCredentials = (site_id: string): Credentials => {
  const site = siteStore.sites.get(site_id);
  const group = site.group_id ? siteStore.groups.get(site.group_id) : null;
  
  if (site.overrides?.use_group_credentials && group) {
    return {
      ...group.credentials,
      ...site.overrides.custom_credentials
    };
  }
  
  return site.credentials;
};
```

### 4.3 Status Monitoring at Scale

```typescript
// Efficient bulk status checking
interface BulkStatusMonitor {
  checkHealth(site_ids: string[]): Promise<Map<string, HealthStatus>>;
  aggregateMetrics(site_ids: string[]): Promise<AggregatedMetrics>;
  detectAnomalies(site_ids: string[]): Promise<Anomaly[]>;
}

const StatusDashboard: React.FC = () => {
  const [groupView, setGroupView] = useState(true);
  const { data: health } = useBulkHealth({ refresh: 30000 });
  
  return (
    <Grid>
      {groupView ? (
        // Group-level view
        groups.map(group => (
          <GroupHealthCard
            key={group.id}
            group={group}
            health={getGroupHealth(group.id, health)}
            expandable
            onExpand={() => showGroupDetails(group.id)}
          />
        ))
      ) : (
        // Individual site view
        <SiteHealthGrid
          sites={sites}
          health={health}
          columns={4}
          showFilters
        />
      )}
      
      {/* Alert banner for critical issues */}
      <AlertBanner
        alerts={health.criticalAlerts}
        onDismiss={dismissAlert}
      />
    </Grid>
  );
};
```

---

## 5. Technical Implementation

### 5.1 Component Structure

```
src/
├── components/
│   ├── common/
│   │   ├── Layout/
│   │   ├── LoadingStates/
│   │   ├── ErrorBoundary/
│   │   └── DataTable/
│   ├── auth/
│   │   ├── LoginForm/
│   │   ├── AuthProvider/
│   │   └── ProtectedRoute/
│   ├── dashboard/
│   │   ├── MetricCards/
│   │   ├── ActivityFeed/
│   │   └── QuickActions/
│   ├── sites/
│   │   ├── SiteList/
│   │   ├── SiteCard/
│   │   ├── AddSiteWizard/
│   │   └── BulkActions/
│   ├── destinations/
│   │   ├── DestinationList/
│   │   ├── RouteBuilder/
│   │   └── FieldMapper/
│   └── monitoring/
│       ├── SubmissionsTable/
│       ├── StatusIndicator/
│       └── DetailView/
├── hooks/
│   ├── useAuth.ts
│   ├── useTenant.ts
│   ├── usePolling.ts
│   └── useApi.ts
├── stores/
│   ├── authStore.ts
│   ├── siteStore.ts
│   └── monitoringStore.ts
├── services/
│   ├── api.ts
│   ├── auth.service.ts
│   └── websocket.service.ts
├── utils/
│   ├── validators.ts
│   ├── formatters.ts
│   └── constants.ts
└── types/
    └── index.ts
```

### 5.2 State Management Patterns

```typescript
// Zustand store with persistence
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface AppStore {
  // Auth state
  user: User | null;
  tenant: TenantContext | null;
  
  // UI state
  sidebarCollapsed: boolean;
  activeFilters: FilterState;
  
  // Data state
  sites: Map<string, Site>;
  submissions: Submission[];
  destinations: Destination[];
  
  // Actions
  login: (credentials: Credentials) => Promise<void>;
  logout: () => void;
  toggleSidebar: () => void;
  
  // Async actions
  fetchSites: () => Promise<void>;
  createDestination: (config: DestinationConfig) => Promise<void>;
}

const useAppStore = create<AppStore>()(
  persist(
    immer((set, get) => ({
      // Initial state
      user: null,
      tenant: null,
      sidebarCollapsed: false,
      activeFilters: {},
      sites: new Map(),
      submissions: [],
      destinations: [],
      
      // Sync actions
      toggleSidebar: () => set((state) => {
        state.sidebarCollapsed = !state.sidebarCollapsed;
      }),
      
      // Async actions
      login: async (credentials) => {
        const { user, tenant } = await authService.login(credentials);
        set((state) => {
          state.user = user;
          state.tenant = tenant;
        });
      },
      
      fetchSites: async () => {
        const sites = await api.getSites(get().tenant?.tenant_id);
        set((state) => {
          sites.forEach(site => state.sites.set(site.id, site));
        });
      }
    })),
    {
      name: 'form-bridge-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        activeFilters: state.activeFilters
      })
    }
  )
);
```

### 5.3 API Integration

```typescript
// API client with TanStack Query
import { QueryClient } from '@tanstack/react-query';
import axios from 'axios';

// Configure axios
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000
});

// Auth interceptor
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const newToken = await refreshToken();
      if (newToken) {
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return apiClient.request(error.config);
      }
    }
    return Promise.reject(error);
  }
);

// Query client configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
    }
  }
});

// API hooks
export const useSubmissions = (filters?: SubmissionFilters) => {
  return useQuery({
    queryKey: ['submissions', filters],
    queryFn: () => api.getSubmissions(filters),
    refetchInterval: 5000, // Poll every 5 seconds
    refetchIntervalInBackground: false
  });
};

export const useCreateSite = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateSiteData) => api.createSite(data),
    onSuccess: () => {
      queryClient.invalidateQueries(['sites']);
      toast.success('Site connected successfully');
    },
    onError: (error) => {
      toast.error(`Failed to connect site: ${error.message}`);
    }
  });
};
```

### 5.4 Error Handling Strategy

```typescript
// Global error boundary
class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log to monitoring service
    logger.error('React Error Boundary', { error, errorInfo });
    
    // Send to error tracking
    if (import.meta.env.PROD) {
      Sentry.captureException(error, { contexts: { react: errorInfo } });
    }
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          onReset={() => this.setState({ hasError: false, error: null })}
        />
      );
    }
    
    return this.props.children;
  }
}

// API error handling
const handleApiError = (error: AxiosError): AppError => {
  if (error.response) {
    // Server responded with error
    const status = error.response.status;
    const data = error.response.data;
    
    switch (status) {
      case 400:
        return new ValidationError(data.message, data.errors);
      case 401:
        return new AuthenticationError('Session expired');
      case 403:
        return new AuthorizationError('Insufficient permissions');
      case 429:
        return new RateLimitError(data.retryAfter);
      case 500:
        return new ServerError('Internal server error');
      default:
        return new AppError(data.message || 'Unknown error');
    }
  } else if (error.request) {
    // Request made but no response
    return new NetworkError('Network error - check your connection');
  } else {
    // Request setup error
    return new AppError(error.message);
  }
};

// User-friendly error messages
const getErrorMessage = (error: AppError): string => {
  const messages: Record<string, string> = {
    'SITE_LIMIT_EXCEEDED': 'You have reached your site limit. Please upgrade your plan.',
    'INVALID_CREDENTIALS': 'The provided credentials are invalid.',
    'PLUGIN_VERSION_MISMATCH': 'Please update your WordPress plugin to the latest version.',
    'DESTINATION_UNREACHABLE': 'Cannot connect to the destination. Please check the configuration.'
  };
  
  return messages[error.code] || error.message;
};
```

### 5.5 Performance Optimization

```typescript
// Code splitting by route
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Sites = lazy(() => import('./pages/Sites'));
const Destinations = lazy(() => import('./pages/Destinations'));
const Monitoring = lazy(() => import('./pages/Monitoring'));

// Virtual scrolling for large lists
import { VariableSizeList } from 'react-window';

const SubmissionsList: React.FC<Props> = ({ submissions }) => {
  const getItemSize = useCallback((index: number) => {
    // Variable height based on content
    return submissions[index].expanded ? 200 : 80;
  }, [submissions]);
  
  return (
    <VariableSizeList
      height={600}
      itemCount={submissions.length}
      itemSize={getItemSize}
      width="100%"
    >
      {({ index, style }) => (
        <SubmissionRow
          key={submissions[index].id}
          submission={submissions[index]}
          style={style}
        />
      )}
    </VariableSizeList>
  );
};

// Memoization for expensive computations
const useAggregatedMetrics = (submissions: Submission[]) => {
  return useMemo(() => {
    return submissions.reduce((acc, submission) => {
      acc.total++;
      acc.byStatus[submission.status] = (acc.byStatus[submission.status] || 0) + 1;
      acc.bySite[submission.site_id] = (acc.bySite[submission.site_id] || 0) + 1;
      return acc;
    }, {
      total: 0,
      byStatus: {} as Record<string, number>,
      bySite: {} as Record<string, number>
    });
  }, [submissions]);
};

// Debounced search
const useSearch = () => {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 300);
  
  const { data, isLoading } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => api.search(debouncedQuery),
    enabled: debouncedQuery.length > 2
  });
  
  return { query, setQuery, results: data, isSearching: isLoading };
};
```

---

## 6. Security Model

### 6.1 HMAC Implementation

```typescript
// Frontend HMAC signature generation (for testing)
class HMACAuth {
  private secret: string;
  
  constructor(secret: string) {
    this.secret = secret;
  }
  
  async generateSignature(
    method: string,
    path: string,
    body: any,
    timestamp: string
  ): Promise<string> {
    const payload = `${method}\n${path}\n${timestamp}\n${JSON.stringify(body)}`;
    
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      'raw',
      encoder.encode(this.secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    
    const signature = await crypto.subtle.sign(
      'HMAC',
      key,
      encoder.encode(payload)
    );
    
    return Array.from(new Uint8Array(signature))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
  
  validateTimestamp(timestamp: string): boolean {
    const now = Date.now();
    const requestTime = new Date(timestamp).getTime();
    const difference = Math.abs(now - requestTime);
    
    return difference < 5 * 60 * 1000; // 5 minute window
  }
}
```

### 6.2 Credential Storage

```typescript
// Secure credential management
interface CredentialStore {
  // Never store sensitive data in localStorage
  // Use httpOnly cookies or session storage for tokens
  
  storeTokens(tokens: TokenPair): void {
    // Store in httpOnly cookie via backend
    api.post('/auth/store-tokens', tokens, {
      withCredentials: true
    });
  };
  
  getAccessToken(): string | null {
    // Retrieved from httpOnly cookie via API
    return sessionStorage.getItem('access_token_hint');
  };
  
  clearTokens(): void {
    api.post('/auth/logout', {}, { withCredentials: true });
    sessionStorage.clear();
  };
}

// Environment-specific secrets
const getApiKey = (): string => {
  if (import.meta.env.DEV) {
    return import.meta.env.VITE_DEV_API_KEY;
  }
  
  // Production keys fetched from backend
  return window.__RUNTIME_CONFIG__.apiKey;
};
```

### 6.3 Rate Limiting

```typescript
// Frontend rate limit handling
class RateLimiter {
  private requests: Map<string, number[]> = new Map();
  
  canMakeRequest(endpoint: string, limit: number = 10, window: number = 60000): boolean {
    const now = Date.now();
    const requests = this.requests.get(endpoint) || [];
    
    // Remove old requests outside window
    const validRequests = requests.filter(time => now - time < window);
    
    if (validRequests.length >= limit) {
      return false;
    }
    
    validRequests.push(now);
    this.requests.set(endpoint, validRequests);
    return true;
  }
  
  getRemainingTime(endpoint: string, window: number = 60000): number {
    const requests = this.requests.get(endpoint) || [];
    if (requests.length === 0) return 0;
    
    const oldestRequest = Math.min(...requests);
    return Math.max(0, window - (Date.now() - oldestRequest));
  }
}

// Hook for rate-limited requests
const useRateLimitedRequest = (endpoint: string) => {
  const rateLimiter = useRef(new RateLimiter());
  const [canRequest, setCanRequest] = useState(true);
  const [retryAfter, setRetryAfter] = useState(0);
  
  const makeRequest = useCallback(async (data: any) => {
    if (!rateLimiter.current.canMakeRequest(endpoint)) {
      const remaining = rateLimiter.current.getRemainingTime(endpoint);
      setCanRequest(false);
      setRetryAfter(remaining);
      
      setTimeout(() => {
        setCanRequest(true);
        setRetryAfter(0);
      }, remaining);
      
      throw new RateLimitError(`Rate limit exceeded. Retry after ${remaining}ms`);
    }
    
    return api.post(endpoint, data);
  }, [endpoint]);
  
  return { makeRequest, canRequest, retryAfter };
};
```

### 6.4 Content Security Policy

```typescript
// CSP headers configuration
const cspConfig = {
  'default-src': ["'self'"],
  'script-src': [
    "'self'",
    "'unsafe-inline'", // Required for React DevTools in dev
    'https://cdn.jsdelivr.net' // For external libraries
  ],
  'style-src': [
    "'self'",
    "'unsafe-inline'", // Required for inline styles
    'https://fonts.googleapis.com'
  ],
  'font-src': [
    "'self'",
    'https://fonts.gstatic.com'
  ],
  'img-src': [
    "'self'",
    'data:',
    'https://*.amazonaws.com' // For S3 assets
  ],
  'connect-src': [
    "'self'",
    process.env.VITE_API_BASE_URL,
    'wss://*.amazonaws.com' // For WebSocket connections
  ]
};

// Meta tag for CSP (development)
const cspString = Object.entries(cspConfig)
  .map(([key, values]) => `${key} ${values.join(' ')}`)
  .join('; ');

// Production: Set via CloudFront headers
```

---

## 7. MVP Limitations & Future Roadmap

### 7.1 MVP Scope (Q1 2025)

**Included:**
- Basic authentication (Cognito email/password)
- Single tenant management
- Up to 50 WordPress sites
- 3 destination types (webhook, email, database)
- Manual field mapping
- 5-second polling for updates
- English language only
- Desktop-first design (mobile-responsive but not optimized)

**Explicitly Excluded:**
- Social login (Google, Microsoft)
- Multi-tenant switching
- Advanced routing rules (conditional logic)
- Custom transformations
- Real-time WebSocket updates
- Internationalization
- Native mobile apps
- White-labeling
- Advanced analytics/reporting

### 7.2 V2 Features (Q2 2025)

```typescript
interface V2Features {
  // Enhanced Authentication
  socialLogin: ['google', 'microsoft', 'github'];
  mfa: boolean;
  sso: 'saml' | 'oauth2';
  
  // Advanced Routing
  conditionalRouting: {
    if: 'field_condition',
    then: 'destination_a',
    else: 'destination_b'
  };
  
  // Transformations
  dataTransformations: [
    'custom_javascript',
    'regex_replace',
    'date_formatting',
    'field_concatenation'
  ];
  
  // Real-time
  websockets: true;
  serverSentEvents: true;
  
  // Analytics
  customDashboards: true;
  exportReports: ['pdf', 'csv', 'excel'];
  alerting: {
    email: true,
    sms: true,
    slack: true
  };
}
```

### 7.3 V3 Enterprise Features (Q3-Q4 2025)

```typescript
interface EnterpriseFeatures {
  // Compliance
  compliance: ['GDPR', 'HIPAA', 'SOC2'];
  dataResidency: ['us', 'eu', 'asia'];
  auditLogs: 'comprehensive';
  
  // Scale
  unlimitedSites: true;
  dedicatedInfrastructure: true;
  sla: '99.99%';
  
  // Customization
  whiteLabeling: true;
  customDomain: true;
  apiAccess: 'full';
  
  // Support
  support: {
    level: 'priority',
    response: '1 hour',
    dedicated: true
  };
}
```

### 7.4 Migration Path

```typescript
// Versioned API contracts
const API_VERSIONS = {
  v1: {
    endpoints: ['/ingest', '/sites', '/submissions'],
    deprecation: null
  },
  v2: {
    endpoints: [...v1.endpoints, '/analytics', '/transformations'],
    deprecation: '2026-01-01'
  }
};

// Database migrations
interface Migration {
  version: string;
  up: () => Promise<void>;
  down: () => Promise<void>;
}

const migrations: Migration[] = [
  {
    version: '1.0.0',
    up: async () => {
      // Initial schema
    },
    down: async () => {
      // Rollback
    }
  },
  {
    version: '2.0.0',
    up: async () => {
      // Add analytics tables
      // Add transformation configs
      // Migrate destination format
    },
    down: async () => {
      // Rollback v2 changes
    }
  }
];

// Feature flags for gradual rollout
const featureFlags = {
  'v2_routing': {
    enabled: false,
    rollout: 0.1, // 10% of users
    override: ['beta_users']
  },
  'websocket_updates': {
    enabled: false,
    rollout: 0.0,
    override: ['internal_testing']
  }
};
```

---

## 8. Implementation Checklist

### 8.1 Week 1-2: Foundation
- [ ] Initialize Vite + React + TypeScript project
- [ ] Setup Tailwind + shadcn/ui
- [ ] Configure Zustand stores
- [ ] Implement Cognito authentication
- [ ] Create base layouts and routing
- [ ] Setup TanStack Query
- [ ] Configure error boundaries
- [ ] Implement theme system

### 8.2 Week 3-4: Core Features
- [ ] Build dashboard with metrics
- [ ] Implement site management CRUD
- [ ] Create WordPress plugin wizard
- [ ] Build destination configuration UI
- [ ] Implement submission monitoring
- [ ] Add bulk operations
- [ ] Create activity feed
- [ ] Setup polling mechanism

### 8.3 Week 5: Integration
- [ ] Connect to API Gateway endpoints
- [ ] Implement HMAC testing tools
- [ ] Add real data flows
- [ ] Test WordPress plugin integration
- [ ] Verify multi-site scenarios
- [ ] Load test with 50 sites
- [ ] Security audit
- [ ] Performance optimization

### 8.4 Week 6: Polish & Deploy
- [ ] Responsive design fixes
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Error message improvements
- [ ] Loading states refinement
- [ ] Documentation completion
- [ ] CloudFront deployment
- [ ] Monitoring setup
- [ ] Launch readiness review

---

## 9. Code Examples

### 9.1 Complete Dashboard Component

```typescript
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Activity, CheckCircle, AlertTriangle, TrendingUp } from 'lucide-react';
import { useMetrics, useRecentActivity, useSites } from '@/hooks';
import { formatRelativeTime, formatNumber } from '@/utils';

const Dashboard: React.FC = () => {
  const { data: metrics, isLoading: metricsLoading } = useMetrics();
  const { data: activity } = useRecentActivity({ limit: 10 });
  const { data: sites } = useSites();
  const [selectedTimeRange, setSelectedTimeRange] = useState('24h');
  
  if (metricsLoading) {
    return <DashboardSkeleton />;
  }
  
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-500">
            Welcome back! Here's what's happening with your forms.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/sites/add')}>
            Connect Site
          </Button>
          <Button onClick={() => navigate('/destinations/new')}>
            Add Destination
          </Button>
        </div>
      </div>
      
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Total Submissions"
          value={formatNumber(metrics?.totalSubmissions || 0)}
          change={metrics?.submissionChange}
          icon={<Activity className="h-4 w-4" />}
        />
        <MetricCard
          title="Active Sites"
          value={sites?.filter(s => s.status === 'active').length || 0}
          subtitle={`of ${sites?.length || 0} total`}
          icon={<CheckCircle className="h-4 w-4" />}
        />
        <MetricCard
          title="Success Rate"
          value={`${metrics?.successRate || 0}%`}
          status={metrics?.successRate > 95 ? 'good' : 'warning'}
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <MetricCard
          title="Failed Deliveries"
          value={metrics?.failedDeliveries || 0}
          status={metrics?.failedDeliveries > 0 ? 'error' : 'good'}
          icon={<AlertTriangle className="h-4 w-4" />}
        />
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity Feed */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {activity?.map((item) => (
                  <ActivityItem
                    key={item.id}
                    type={item.type}
                    message={item.message}
                    timestamp={item.timestamp}
                    status={item.status}
                  />
                ))}
                {!activity?.length && (
                  <p className="text-center text-gray-500 py-8">
                    No recent activity
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
        
        {/* Quick Stats */}
        <div className="space-y-4">
          <TopFormsList forms={metrics?.topForms} />
          <SiteHealthSummary sites={sites} />
          <QuickActions />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
```

### 9.2 Site Connection Wizard

```typescript
import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Stepper } from '@/components/ui/stepper';
import { CopyButton } from '@/components/ui/copy-button';
import { useCreateSite } from '@/hooks';

const siteSchema = z.object({
  name: z.string().min(1, 'Site name is required'),
  url: z.string().url('Must be a valid URL'),
  type: z.enum(['wordpress', 'custom']),
});

const SiteConnectionWizard: React.FC = () => {
  const [step, setStep] = useState(0);
  const [siteData, setSiteData] = useState<SiteData>();
  const [credentials, setCredentials] = useState<Credentials>();
  const { mutate: createSite, isLoading } = useCreateSite();
  
  const form = useForm({
    resolver: zodResolver(siteSchema),
    defaultValues: {
      type: 'wordpress'
    }
  });
  
  const steps = [
    {
      title: 'Site Details',
      description: 'Enter your site information',
      content: (
        <form onSubmit={form.handleSubmit(onSiteSubmit)}>
          <div className="space-y-4">
            <div>
              <Label>Site Name</Label>
              <Input {...form.register('name')} placeholder="My WordPress Site" />
              {form.formState.errors.name && (
                <ErrorMessage>{form.formState.errors.name.message}</ErrorMessage>
              )}
            </div>
            
            <div>
              <Label>Site URL</Label>
              <Input {...form.register('url')} placeholder="https://example.com" />
              {form.formState.errors.url && (
                <ErrorMessage>{form.formState.errors.url.message}</ErrorMessage>
              )}
            </div>
            
            <RadioGroup {...form.register('type')}>
              <RadioItem value="wordpress">WordPress</RadioItem>
              <RadioItem value="custom">Custom Integration</RadioItem>
            </RadioGroup>
          </div>
          
          <div className="mt-6 flex justify-end">
            <Button type="submit" loading={isLoading}>
              Generate Credentials
            </Button>
          </div>
        </form>
      )
    },
    {
      title: 'Install Plugin',
      description: 'Download and install the Form-Bridge plugin',
      content: (
        <div className="space-y-6">
          <Alert>
            <AlertTitle>Your Credentials</AlertTitle>
            <AlertDescription>
              Save these credentials securely. You'll need them to configure the plugin.
            </AlertDescription>
          </Alert>
          
          <div className="space-y-4">
            <CredentialField
              label="Site ID"
              value={credentials?.site_id}
              copyable
            />
            <CredentialField
              label="API Key"
              value={credentials?.api_key}
              copyable
              masked
            />
            <CredentialField
              label="Secret"
              value={credentials?.secret}
              copyable
              masked
            />
          </div>
          
          <div className="border rounded-lg p-4">
            <h4 className="font-medium mb-2">Installation Steps:</h4>
            <ol className="list-decimal list-inside space-y-2 text-sm">
              <li>Download the Form-Bridge plugin</li>
              <li>Upload to WordPress via Plugins → Add New → Upload</li>
              <li>Activate the plugin</li>
              <li>Go to Settings → Form-Bridge</li>
              <li>Enter the credentials shown above</li>
              <li>Click "Connect"</li>
            </ol>
          </div>
          
          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => window.open('/api/plugin/download')}
            >
              Download Plugin
            </Button>
            <Button onClick={() => setStep(2)}>
              I've Installed the Plugin
            </Button>
          </div>
        </div>
      )
    },
    {
      title: 'Verify Connection',
      description: 'Confirming your site is connected',
      content: (
        <ConnectionVerification
          siteId={credentials?.site_id}
          onSuccess={() => navigate('/sites')}
        />
      )
    }
  ];
  
  return (
    <div className="max-w-3xl mx-auto p-6">
      <Stepper
        steps={steps}
        currentStep={step}
        onStepClick={setStep}
      />
      
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>{steps[step].title}</CardTitle>
          <CardDescription>{steps[step].description}</CardDescription>
        </CardHeader>
        <CardContent>
          {steps[step].content}
        </CardContent>
      </Card>
    </div>
  );
};
```

---

## Conclusion

This MVPv1 specification provides a complete blueprint for building the Form-Bridge frontend. The implementation focuses on:

1. **Speed to Market**: 6-week development timeline
2. **User Experience**: 5-minute setup, intuitive UI
3. **Scalability**: Architecture supports 50 sites initially, thousands later
4. **Security**: HMAC authentication, secure credential storage
5. **Cost Efficiency**: < $50/month operational costs

The specification is ready for immediate implementation by the engineering team, with clear technical requirements, code examples, and a phased approach to feature delivery.