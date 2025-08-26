# Modern React Dashboard Architecture - Form Bridge Admin

*Version: 1.0 | Date: January 26, 2025*
*Framework: React 18+ with 2025 Best Practices*

## 🏗️ Project Structure

```
frontend/
├── public/
│   ├── index.html
│   ├── manifest.json            # PWA manifest
│   └── sw.js                    # Service worker
├── src/
│   ├── components/              # Reusable UI components
│   │   ├── common/              # Generic components
│   │   │   ├── Button/
│   │   │   ├── Card/
│   │   │   ├── Modal/
│   │   │   ├── Table/
│   │   │   └── Skeleton/
│   │   ├── dashboard/           # Dashboard-specific components
│   │   │   ├── MetricsWidget/
│   │   │   ├── SubmissionsList/
│   │   │   ├── RealtimeUpdates/
│   │   │   └── QuickActions/
│   │   ├── forms/               # Form components
│   │   │   ├── SubmissionForm/
│   │   │   ├── FilterForm/
│   │   │   └── SearchForm/
│   │   └── layout/              # Layout components
│   │       ├── Header/
│   │       ├── Sidebar/
│   │       ├── Footer/
│   │       └── PageContainer/
│   ├── hooks/                   # Custom React hooks
│   │   ├── auth/
│   │   │   ├── useAuth.ts
│   │   │   ├── useSecureAuth.ts
│   │   │   └── useTokenRefresh.ts
│   │   ├── api/
│   │   │   ├── useApiCall.ts
│   │   │   ├── useSubmissions.ts
│   │   │   └── useMetrics.ts
│   │   ├── realtime/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useRealTimeData.ts
│   │   │   └── useSmartPolling.ts
│   │   └── utils/
│   │       ├── useLocalStorage.ts
│   │       ├── useOfflineQueue.ts
│   │       └── usePerformanceMonitoring.ts
│   ├── pages/                   # Route components (lazy loaded)
│   │   ├── Dashboard/
│   │   ├── Submissions/
│   │   ├── Analytics/
│   │   ├── Settings/
│   │   ├── Users/
│   │   └── Login/
│   ├── services/                # API and external services
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── submissions.ts
│   │   │   ├── analytics.ts
│   │   │   └── users.ts
│   │   ├── auth/
│   │   │   ├── cognito.ts
│   │   │   └── tokenManager.ts
│   │   └── realtime/
│   │       ├── websocket.ts
│   │       └── eventHandlers.ts
│   ├── store/                   # State management
│   │   ├── slices/              # Zustand stores
│   │   │   ├── authStore.ts
│   │   │   ├── dashboardStore.ts
│   │   │   ├── submissionsStore.ts
│   │   │   └── uiStore.ts
│   │   └── index.ts
│   ├── types/                   # TypeScript definitions
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   ├── dashboard.ts
│   │   └── common.ts
│   ├── utils/                   # Utility functions
│   │   ├── constants.ts
│   │   ├── formatters.ts
│   │   ├── validators.ts
│   │   └── analytics.ts
│   ├── styles/                  # Styling
│   │   ├── globals.css
│   │   ├── themes/
│   │   │   ├── light.ts
│   │   │   └── dark.ts
│   │   └── components/
│   ├── App.tsx
│   ├── main.tsx
│   └── vite-env.d.ts
├── tests/                       # Test files
│   ├── components/
│   ├── hooks/
│   ├── pages/
│   └── utils/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── README.md
```

## 🧩 Core Component Architecture

### Dashboard Layout Structure
```typescript
// Main dashboard layout with modern patterns
export const DashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isCollapsed, toggleSidebar } = useUIStore();
  const { isOnline } = useOfflineQueue();
  const { connectionStatus } = useWebSocketConnection();
  
  return (
    <div className="min-h-screen bg-gray-50">
      <ErrorBoundary fallback={<ErrorFallback />}>
        <Header 
          onToggleSidebar={toggleSidebar}
          connectionStatus={connectionStatus}
          isOnline={isOnline}
        />
        
        <div className="flex">
          <Sidebar isCollapsed={isCollapsed} />
          
          <main className={cn(
            "flex-1 transition-all duration-300",
            isCollapsed ? "ml-16" : "ml-64"
          )}>
            <PageContainer>
              <Suspense fallback={<PageSkeleton />}>
                {children}
              </Suspense>
            </PageContainer>
          </main>
        </div>
        
        <Toaster position="top-right" />
      </ErrorBoundary>
    </div>
  );
};
```

### Widget-Based Dashboard
```typescript
// Reusable dashboard widget system
interface WidgetProps {
  title: string;
  loading?: boolean;
  error?: string | null;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export const DashboardWidget = memo<WidgetProps>(({ 
  title, 
  loading, 
  error, 
  actions, 
  className, 
  children 
}) => {
  return (
    <Card className={cn("h-full", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {actions && <div className="flex space-x-2">{actions}</div>}
      </CardHeader>
      
      <CardContent>
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {loading ? (
          <WidgetSkeleton />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
});

// Usage in dashboard
const Dashboard = () => {
  const { submissions, metrics, loading, error } = useDashboardData();
  const { realTimeData } = useRealTimeDashboard();
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <DashboardWidget 
        title="Total Submissions" 
        loading={loading}
        error={error}
      >
        <MetricCard 
          value={metrics.totalSubmissions} 
          change={metrics.submissionTrend}
          icon={<FileText />}
        />
      </DashboardWidget>
      
      <DashboardWidget 
        title="Recent Activity" 
        actions={<RefreshButton onClick={refetch} />}
      >
        <RecentSubmissionsList 
          submissions={realTimeData.submissions.slice(0, 5)} 
        />
      </DashboardWidget>
      
      <DashboardWidget 
        title="Processing Status"
        className="md:col-span-2"
      >
        <ProcessingChart data={metrics.processingStats} />
      </DashboardWidget>
      
      <DashboardWidget 
        title="System Health"
        className="lg:col-span-2"
      >
        <HealthIndicators health={metrics.systemHealth} />
      </DashboardWidget>
    </div>
  );
};
```

## 🔐 Authentication Architecture

### Cognito Integration Layer
```typescript
// Modern Cognito authentication service
class CognitoAuthService {
  private amplifyConfig: AmplifyConfig;
  private tokenRefreshTimer?: NodeJS.Timeout;
  
  constructor() {
    this.amplifyConfig = {
      Auth: {
        region: process.env.REACT_APP_AWS_REGION,
        userPoolId: process.env.REACT_APP_USER_POOL_ID,
        userPoolWebClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID,
        oauth: {
          domain: process.env.REACT_APP_COGNITO_DOMAIN,
          scope: ['email', 'openid', 'profile'],
          redirectSignIn: process.env.REACT_APP_REDIRECT_SIGN_IN,
          redirectSignOut: process.env.REACT_APP_REDIRECT_SIGN_OUT,
          responseType: 'code'
        }
      }
    };
    
    Amplify.configure(this.amplifyConfig);
  }
  
  async signIn(email: string, password: string): Promise<CognitoUser> {
    try {
      const user = await Auth.signIn(email, password);
      
      // Handle MFA challenge
      if (user.challengeName === 'SOFTWARE_TOKEN_MFA') {
        throw new MFARequiredError('MFA token required', user);
      }
      
      this.setupTokenRefresh(user);
      return user;
      
    } catch (error) {
      this.handleAuthError(error);
      throw error;
    }
  }
  
  async confirmMFA(user: CognitoUser, code: string): Promise<CognitoUser> {
    try {
      const signedInUser = await Auth.confirmSignIn(user, code, 'SOFTWARE_TOKEN_MFA');
      this.setupTokenRefresh(signedInUser);
      return signedInUser;
    } catch (error) {
      this.handleAuthError(error);
      throw error;
    }
  }
  
  private async setupTokenRefresh(user: CognitoUser): Promise<void> {
    const session = await Auth.currentSession();
    const expirationTime = session.getAccessToken().getExpiration() * 1000;
    const refreshTime = expirationTime - Date.now() - (5 * 60 * 1000); // 5 minutes before expiry
    
    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
    }
    
    this.tokenRefreshTimer = setTimeout(async () => {
      try {
        await Auth.currentSession(); // Triggers refresh
        const newSession = await Auth.currentSession();
        this.setupTokenRefresh(user); // Schedule next refresh
      } catch (error) {
        console.error('Token refresh failed:', error);
        await this.signOut();
      }
    }, Math.max(refreshTime, 60000)); // Minimum 1 minute
  }
  
  async signOut(): Promise<void> {
    if (this.tokenRefreshTimer) {
      clearTimeout(this.tokenRefreshTimer);
      this.tokenRefreshTimer = undefined;
    }
    
    await Auth.signOut();
  }
  
  private handleAuthError(error: any): void {
    // Log to CloudWatch or analytics service
    analytics.track('Auth Error', {
      error: error.message,
      code: error.code,
      timestamp: Date.now()
    });
  }
}

// Authentication hook
export const useAuth = () => {
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    user: null,
    loading: true,
    error: null
  });
  
  const authService = useMemo(() => new CognitoAuthService(), []);
  
  const signIn = useCallback(async (email: string, password: string) => {
    setAuthState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const user = await authService.signIn(email, password);
      setAuthState({
        isAuthenticated: true,
        user,
        loading: false,
        error: null
      });
      
      return user;
    } catch (error) {
      setAuthState(prev => ({
        ...prev,
        loading: false,
        error: error.message
      }));
      throw error;
    }
  }, [authService]);
  
  const signOut = useCallback(async () => {
    await authService.signOut();
    setAuthState({
      isAuthenticated: false,
      user: null,
      loading: false,
      error: null
    });
  }, [authService]);
  
  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const user = await Auth.currentAuthenticatedUser();
        setAuthState({
          isAuthenticated: true,
          user,
          loading: false,
          error: null
        });
      } catch (error) {
        setAuthState({
          isAuthenticated: false,
          user: null,
          loading: false,
          error: null
        });
      }
    };
    
    checkAuth();
  }, []);
  
  return {
    ...authState,
    signIn,
    signOut,
    confirmMFA: authService.confirmMFA.bind(authService)
  };
};
```

## 🚀 Performance Optimization Implementation

### Code Splitting Strategy
```typescript
// Route-based lazy loading
const Dashboard = lazy(() => import('../pages/Dashboard'));
const Submissions = lazy(() => import('../pages/Submissions'));
const Analytics = lazy(() => import('../pages/Analytics').then(module => ({
  default: module.Analytics
})));
const Settings = lazy(() => import('../pages/Settings'));

// Component-level lazy loading for heavy components
const DataVisualization = lazy(() => 
  import('../components/charts/DataVisualization').then(module => ({
    default: module.DataVisualization
  }))
);

const ExportModal = lazy(() => import('../components/modals/ExportModal'));

// App router with Suspense boundaries
export const AppRouter = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute />}>
          <Route path="" element={
            <Suspense fallback={<DashboardSkeleton />}>
              <Dashboard />
            </Suspense>
          } />
          <Route path="submissions" element={
            <Suspense fallback={<PageSkeleton />}>
              <Submissions />
            </Suspense>
          } />
          <Route path="analytics" element={
            <Suspense fallback={<PageSkeleton />}>
              <Analytics />
            </Suspense>
          } />
          <Route path="settings" element={
            <Suspense fallback={<PageSkeleton />}>
              <Settings />
            </Suspense>
          } />
        </Route>
      </Routes>
    </Router>
  );
};
```

### Smart Data Fetching
```typescript
// Optimized data fetching with React 18 concurrent features
export const useOptimizedSubmissions = (filters: FilterState) => {
  const [data, setData] = useState<SubmissionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  
  // Debounced filters to prevent excessive API calls
  const deferredFilters = useDeferredValue(filters);
  
  const fetchData = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/submissions', {
        method: 'POST',
        body: JSON.stringify(deferredFilters),
        headers: { 'Content-Type': 'application/json' },
        signal
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.status}`);
      }
      
      const newData = await response.json();
      
      // Use transition for non-urgent updates
      startTransition(() => {
        setData(newData);
        setLoading(false);
      });
      
    } catch (error) {
      if (error.name !== 'AbortError') {
        setError(error.message);
        setLoading(false);
      }
    }
  }, [deferredFilters]);
  
  // Fetch data when filters change
  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    
    return () => controller.abort();
  }, [fetchData]);
  
  return { 
    data, 
    loading: loading || isPending, 
    error, 
    refetch: () => fetchData() 
  };
};
```

## 🌐 Real-Time Data Architecture

### WebSocket Integration
```typescript
// Centralized WebSocket manager
class WebSocketManager {
  private socket: WebSocket | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  
  constructor(private url: string) {}
  
  connect(token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const wsUrl = `${this.url}?token=${encodeURIComponent(token)}`;
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.notifyListeners(data.type, data.payload);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };
        
        this.socket.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.handleReconnect();
        };
        
        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };
        
      } catch (error) {
        reject(error);
      }
    });
  }
  
  private async handleReconnect(): Promise<void> {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      console.log(`Attempting reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
      
      setTimeout(async () => {
        try {
          // Get fresh token and reconnect
          const session = await Auth.currentSession();
          const token = session.getAccessToken().getJwtToken();
          await this.connect(token);
        } catch (error) {
          console.error('Reconnection failed:', error);
        }
      }, delay);
    }
  }
  
  subscribe(eventType: string, callback: (data: any) => void): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    
    this.listeners.get(eventType)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(eventType);
      if (listeners) {
        listeners.delete(callback);
        if (listeners.size === 0) {
          this.listeners.delete(eventType);
        }
      }
    };
  }
  
  private notifyListeners(eventType: string, data: any): void {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in WebSocket listener:', error);
        }
      });
    }
  }
  
  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.listeners.clear();
  }
}

// React hook for WebSocket integration
export const useRealTimeUpdates = () => {
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const { user } = useAuth();
  const wsManager = useMemo(() => new WebSocketManager(process.env.REACT_APP_WSS_URL!), []);
  
  useEffect(() => {
    if (!user) return;
    
    const connect = async () => {
      setConnectionStatus('connecting');
      try {
        const session = await Auth.currentSession();
        const token = session.getAccessToken().getJwtToken();
        await wsManager.connect(token);
        setConnectionStatus('connected');
      } catch (error) {
        console.error('WebSocket connection failed:', error);
        setConnectionStatus('disconnected');
      }
    };
    
    connect();
    
    return () => {
      wsManager.disconnect();
      setConnectionStatus('disconnected');
    };
  }, [user, wsManager]);
  
  const subscribe = useCallback((eventType: string, callback: (data: any) => void) => {
    return wsManager.subscribe(eventType, callback);
  }, [wsManager]);
  
  return { connectionStatus, subscribe };
};
```

## 🎨 Design System & Components

### Theme Configuration
```typescript
// Comprehensive theme system
export const lightTheme = {
  colors: {
    primary: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
      950: '#172554'
    },
    gray: {
      50: '#f9fafb',
      100: '#f3f4f6',
      200: '#e5e7eb',
      300: '#d1d5db',
      400: '#9ca3af',
      500: '#6b7280',
      600: '#4b5563',
      700: '#374151',
      800: '#1f2937',
      900: '#111827',
      950: '#030712'
    },
    semantic: {
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6'
    }
  },
  spacing: {
    0: '0',
    px: '1px',
    0.5: '0.125rem',
    1: '0.25rem',
    2: '0.5rem',
    3: '0.75rem',
    4: '1rem',
    5: '1.25rem',
    6: '1.5rem',
    8: '2rem',
    10: '2.5rem',
    12: '3rem',
    16: '4rem',
    20: '5rem',
    24: '6rem',
    32: '8rem'
  },
  typography: {
    fontFamily: {
      sans: ['Inter', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'Menlo', 'monospace']
    },
    fontSize: {
      xs: ['0.75rem', { lineHeight: '1rem' }],
      sm: ['0.875rem', { lineHeight: '1.25rem' }],
      base: ['1rem', { lineHeight: '1.5rem' }],
      lg: ['1.125rem', { lineHeight: '1.75rem' }],
      xl: ['1.25rem', { lineHeight: '1.75rem' }],
      '2xl': ['1.5rem', { lineHeight: '2rem' }],
      '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
      '4xl': ['2.25rem', { lineHeight: '2.5rem' }]
    }
  },
  borderRadius: {
    none: '0',
    sm: '0.125rem',
    DEFAULT: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
    xl: '0.75rem',
    '2xl': '1rem',
    '3xl': '1.5rem',
    full: '9999px'
  },
  shadows: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    DEFAULT: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)'
  }
};

export const darkTheme = {
  ...lightTheme,
  colors: {
    ...lightTheme.colors,
    // Dark theme color overrides
    gray: {
      50: '#111827',
      100: '#1f2937',
      200: '#374151',
      300: '#4b5563',
      400: '#6b7280',
      500: '#9ca3af',
      600: '#d1d5db',
      700: '#e5e7eb',
      800: '#f3f4f6',
      900: '#f9fafb',
      950: '#ffffff'
    }
  }
};
```

### Component Library Structure
```typescript
// Reusable button component with variants
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
  variant = 'primary',
  size = 'md',
  loading = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  className,
  ...props
}, ref) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none';
  
  const variantClasses = {
    primary: 'bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500',
    secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
    outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:ring-primary-500',
    ghost: 'text-gray-700 hover:bg-gray-100 focus:ring-primary-500',
    destructive: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
  };
  
  const sizeClasses = {
    sm: 'px-3 py-2 text-sm rounded-md',
    md: 'px-4 py-2 text-base rounded-md',
    lg: 'px-6 py-3 text-lg rounded-lg'
  };
  
  return (
    <button
      ref={ref}
      className={cn(
        baseClasses,
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner className="mr-2 h-4 w-4" />}
      {!loading && leftIcon && <span className="mr-2">{leftIcon}</span>}
      {children}
      {!loading && rightIcon && <span className="ml-2">{rightIcon}</span>}
    </button>
  );
});
```

## 📊 State Management Architecture

### Zustand Store Implementation
```typescript
// Dashboard store with React 18 integration
interface DashboardState {
  // Data
  submissions: Submission[];
  metrics: DashboardMetrics;
  realTimeUpdates: RealTimeUpdate[];
  
  // UI State
  loading: boolean;
  error: string | null;
  filters: FilterState;
  selectedSubmission: Submission | null;
  
  // Actions
  fetchDashboardData: () => Promise<void>;
  updateFilters: (filters: Partial<FilterState>) => void;
  addRealTimeUpdate: (update: RealTimeUpdate) => void;
  selectSubmission: (submission: Submission | null) => void;
  clearError: () => void;
  resetDashboard: () => void;
}

export const useDashboardStore = create<DashboardState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    submissions: [],
    metrics: {
      totalSubmissions: 0,
      todaySubmissions: 0,
      processingRate: 0,
      errorRate: 0
    },
    realTimeUpdates: [],
    loading: false,
    error: null,
    filters: {
      dateRange: 'today',
      status: 'all',
      source: 'all'
    },
    selectedSubmission: null,
    
    // Actions
    fetchDashboardData: async () => {
      const { filters } = get();
      set({ loading: true, error: null });
      
      try {
        const response = await api.getDashboardData(filters);
        set({
          submissions: response.submissions,
          metrics: response.metrics,
          loading: false
        });
      } catch (error) {
        set({
          error: error.message,
          loading: false
        });
      }
    },
    
    updateFilters: (newFilters) => {
      const currentFilters = get().filters;
      const updatedFilters = { ...currentFilters, ...newFilters };
      
      set({ filters: updatedFilters });
      
      // Automatically refetch data when filters change
      get().fetchDashboardData();
    },
    
    addRealTimeUpdate: (update) => {
      set(state => ({
        realTimeUpdates: [update, ...state.realTimeUpdates].slice(0, 50), // Keep last 50
        // Update metrics if needed
        metrics: updateMetricsWithNewData(state.metrics, update)
      }));
    },
    
    selectSubmission: (submission) => {
      set({ selectedSubmission: submission });
    },
    
    clearError: () => set({ error: null }),
    
    resetDashboard: () => {
      set({
        submissions: [],
        metrics: {
          totalSubmissions: 0,
          todaySubmissions: 0,
          processingRate: 0,
          errorRate: 0
        },
        realTimeUpdates: [],
        loading: false,
        error: null,
        selectedSubmission: null
      });
    }
  }))
);

// Hook for dashboard data with React 18 optimizations
export const useDashboardData = () => {
  const {
    submissions,
    metrics,
    loading,
    error,
    fetchDashboardData,
    updateFilters,
    clearError
  } = useDashboardStore();
  
  const [isPending, startTransition] = useTransition();
  
  // Optimized refresh function
  const refreshData = useCallback(() => {
    startTransition(() => {
      fetchDashboardData();
    });
  }, [fetchDashboardData]);
  
  // Optimized filter update
  const updateFiltersOptimized = useCallback((filters: Partial<FilterState>) => {
    startTransition(() => {
      updateFilters(filters);
    });
  }, [updateFilters]);
  
  return {
    submissions,
    metrics,
    loading: loading || isPending,
    error,
    refreshData,
    updateFilters: updateFiltersOptimized,
    clearError
  };
};
```

## 🧪 Testing Architecture

### Component Testing Setup
```typescript
// Test utilities and providers
export const TestProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider theme={lightTheme}>
          <Toaster />
          {children}
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

// Custom render function
export const renderWithProviders = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => {
  return render(ui, { wrapper: TestProviders, ...options });
};

// Dashboard component test
describe('Dashboard Component', () => {
  const mockSubmissions = [
    { id: '1', title: 'Test Submission', status: 'processed', createdAt: new Date() }
  ];
  
  beforeEach(() => {
    server.use(
      rest.get('/api/dashboard', (req, res, ctx) => {
        return res(ctx.json({
          submissions: mockSubmissions,
          metrics: {
            totalSubmissions: 100,
            todaySubmissions: 5,
            processingRate: 0.95,
            errorRate: 0.05
          }
        }));
      })
    );
  });
  
  it('renders dashboard with data', async () => {
    renderWithProviders(<Dashboard />);
    
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Total Submissions')).toBeInTheDocument();
      expect(screen.getByText('100')).toBeInTheDocument();
    });
  });
  
  it('handles real-time updates', async () => {
    const { container } = renderWithProviders(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('Total Submissions')).toBeInTheDocument();
    });
    
    // Simulate WebSocket message
    act(() => {
      const mockUpdate = {
        type: 'NEW_SUBMISSION',
        payload: {
          id: '2',
          title: 'New Submission',
          status: 'pending',
          createdAt: new Date()
        }
      };
      
      // Trigger WebSocket message handler
      window.dispatchEvent(new CustomEvent('websocket-message', { detail: mockUpdate }));
    });
    
    await waitFor(() => {
      expect(screen.getByText('New Submission')).toBeInTheDocument();
    });
  });
  
  it('handles offline mode', async () => {
    // Mock offline state
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false
    });
    
    renderWithProviders(<Dashboard />);
    
    expect(screen.getByText('Offline Mode')).toBeInTheDocument();
    expect(screen.getByText('Limited functionality available')).toBeInTheDocument();
  });
});
```

This comprehensive React dashboard architecture provides:

1. **Modern React 18+ Patterns**: Concurrent features, Suspense, transitions
2. **Security**: Proper Cognito integration with token rotation
3. **Performance**: Code splitting, smart polling, optimistic updates  
4. **Real-time**: WebSocket integration with reconnection logic
5. **Offline**: PWA capabilities with queue management
6. **Testing**: Comprehensive test setup with MSW and RTL
7. **Scalability**: Modular architecture with proper separation of concerns
8. **Accessibility**: WCAG 2.1 compliance throughout
9. **Bundle Optimization**: Route and component-level code splitting
10. **State Management**: Modern Zustand with React 18 integration

The architecture is designed to handle the critical frontend requirements from the todo list while providing a solid foundation for future enhancements.