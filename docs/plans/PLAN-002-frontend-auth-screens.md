# Plan: Frontend Authentication Screens

**ID:** PLAN-002
**Type:** plan
**Feature:** FEAT-002
**Architecture:** ARCH-002
**Version:** 1
**Status:** ready
**Date:** 2026-10-04

---

## Context

The Spot Rides Expo frontend is a bare SDK 57 project with only `App.js` (default template), `package.json` (4 deps), and `app.json`. No screens, navigation, services, config, or components exist. This plan breaks the ARCH-002 architecture (15 components across 3 auth screens, a placeholder home screen, navigation, services, and state management) into 10 dependency-ordered tasks that a `frontend-engineer` agent can execute sequentially or in parallel where noted.

The backend auth API (FEAT-001) is fully operational. Test code `000000` is available in dev mode.

---

## Task Table

| ID | Title | Owner | Depends On | Phase | Risk | Status |
|----|-------|-------|-----------|-------|------|--------|
| TASK-001 | Install dependencies and scaffold project structure | frontend-engineer | -- | Foundation | low | pending |
| TASK-002 | Create configuration modules (theme + constants) | frontend-engineer | TASK-001 | Foundation | low | pending |
| TASK-003 | Create secure store service | frontend-engineer | TASK-002 | Services | low | pending |
| TASK-004 | Create API client with interceptors | frontend-engineer | TASK-002, TASK-003 | Services | medium | pending |
| TASK-005 | Create auth service functions | frontend-engineer | TASK-004 | Services | low | pending |
| TASK-006 | Create auth context provider | frontend-engineer | TASK-003, TASK-005 | State | medium | pending |
| TASK-007 | Create reusable UI components | frontend-engineer | TASK-002 | Components | low | pending |
| TASK-008 | Create SplashScreen and HomeScreen | frontend-engineer | TASK-006, TASK-007 | Screens | low | pending |
| TASK-009 | Create PhoneLoginScreen and OtpVerificationScreen | frontend-engineer | TASK-006, TASK-007 | Screens | medium | pending |
| TASK-010 | Create RootNavigator, update App.js, and verify end-to-end | frontend-engineer | TASK-008, TASK-009 | Integration | medium | pending |

---

## Task Details

### TASK-001 -- Install dependencies and scaffold project structure

- **Owner:** frontend-engineer
- **Goal:** Install all npm packages required by ARCH-002 and create the directory structure and environment files so that all subsequent tasks have their prerequisites in place.
- **Rationale:** Every other task depends on having the packages installed and directories available. This is the single prerequisite for all downstream work.
- **Dependencies:** none
- **Component Refs:** none (infrastructure only)
- **Affected Files:**
  - `frontend/package.json` (modified by expo install)
  - `frontend/.env` (new)
  - `frontend/.env.example` (new)
  - `frontend/config/` (new directory)
  - `frontend/services/` (new directory)
  - `frontend/context/` (new directory)
  - `frontend/navigation/` (new directory)
  - `frontend/screens/` (new directory)
  - `frontend/components/` (new directory)
- **Implementation Notes:**
  - Run: `npx expo install @react-navigation/native @react-navigation/native-stack react-native-screens react-native-safe-area-context expo-secure-store expo-font @expo-google-fonts/inter expo-splash-screen axios`
  - Create all directories listed in ARCH-002 directory structure.
  - Create `frontend/.env.example` with `EXPO_PUBLIC_API_BASE_URL=http://localhost:8000`.
  - Create `frontend/.env` with the same content (gitignored).
  - Verify `.env` is in `.gitignore`; add it if not.
- **Acceptance Criteria:**
  - [ ] All 9 packages appear in `package.json` dependencies
  - [ ] `npx expo start` launches without errors (no runtime test, just Metro bundler starts)
  - [ ] Directories `config/`, `services/`, `context/`, `navigation/`, `screens/`, `components/` exist under `frontend/`
  - [ ] `.env.example` contains `EXPO_PUBLIC_API_BASE_URL=http://localhost:8000`
  - [ ] `.env` is gitignored
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-002 -- Create configuration modules (theme + constants)

- **Owner:** frontend-engineer
- **Goal:** Create `config/theme.js` and `config/constants.js` that centralize all Stitch design tokens and app constants, providing a single source of truth consumed by every downstream component and screen.
- **Rationale:** ARCH-002 mandates that design tokens and app constants are centralized, not scattered. Every UI component, screen, and service module imports from these files.
- **Dependencies:** TASK-001
- **Component Refs:** COMP-002, COMP-003
- **Affected Files:**
  - `frontend/config/theme.js` (new)
  - `frontend/config/constants.js` (new)
- **Implementation Notes:**
  - **theme.js** exports a flat object with all Stitch tokens:
    - Colors: primary `#2563EB`, secondary `#16A34A`, canvas `#F8FAFC`, surface `#FFFFFF`, border `#E2E8F0`, textPrimary `#0F172A`, textMuted `#64748B`, error (red for inline errors), white `#FFFFFF`
    - Typography: fontFamily (`Inter_400Regular`, `Inter_500Medium`, `Inter_600SemiBold`, `Inter_700Bold`), font sizes for heading, subheading, body, caption
    - Dimensions: buttonHeight `52`, buttonRadius `14`, inputHeight `50`, inputRadius `12`, cardRadius `16`, pillRadius `9999`, minTouchTarget `48`
    - Spacing scale (e.g., 4, 8, 12, 16, 20, 24, 32)
  - **constants.js** exports:
    - `API_BASE_URL`: `process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000'`
    - `SPLASH_MIN_DISPLAY_MS`: `2000`
    - `DIAL_CODE`: `'+91'`
    - `OTP_LENGTH`: `6`
    - `PHONE_LENGTH`: `10`
    - Secure store key names: `STORAGE_KEYS.ACCESS_TOKEN`, `STORAGE_KEYS.REFRESH_TOKEN`, `STORAGE_KEYS.USER`, `STORAGE_KEYS.IS_NEW_USER` (all prefixed `spot_rides_`)
- **Acceptance Criteria:**
  - [ ] `import theme from '../config/theme'` resolves and `theme.colors.primary === '#2563EB'`
  - [ ] `import { API_BASE_URL, SPLASH_MIN_DISPLAY_MS, DIAL_CODE, STORAGE_KEYS } from '../config/constants'` resolves
  - [ ] `API_BASE_URL` defaults to `http://localhost:8000` when env var is unset
  - [ ] All four `STORAGE_KEYS` entries use the `spot_rides_` prefix
  - [ ] All Stitch design tokens from the requirements are present in theme.js
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-003 -- Create secure store service

- **Owner:** frontend-engineer
- **Goal:** Create `services/secureStore.js` that wraps `expo-secure-store` with typed helper functions for reading, writing, and clearing auth tokens and user data.
- **Rationale:** COMP-006 in ARCH-002. FR-16 mandates tokens are stored in secure storage (keychain/keystore), never AsyncStorage. A wrapper centralizes key management and JSON serialization, preventing key typos and inconsistent access patterns across screens and the API interceptor.
- **Dependencies:** TASK-002 (imports `STORAGE_KEYS` from constants)
- **Component Refs:** COMP-006
- **Affected Files:**
  - `frontend/services/secureStore.js` (new)
- **Implementation Notes:**
  - Import `* as SecureStore` from `expo-secure-store` and `STORAGE_KEYS` from constants.
  - Export async functions:
    - `getTokens()` -- returns `{ accessToken, refreshToken }` or `{ accessToken: null, refreshToken: null }`
    - `setTokens(accessToken, refreshToken)` -- writes both keys
    - `getRefreshToken()` -- reads refresh token only (for interceptor)
    - `clearTokens()` -- deletes access and refresh token keys
    - `getUser()` -- reads and JSON-parses user object + isNewUser flag; returns `{ user, isNewUser }` or null
    - `setUser(user, isNewUser)` -- JSON-stringifies and writes
    - `clearAll()` -- deletes all four keys (best-effort, swallow individual errors)
  - Wrap all SecureStore calls in try/catch; return null/undefined on read failure, swallow on delete.
- **Acceptance Criteria:**
  - [ ] `setTokens('abc', 'def')` followed by `getTokens()` returns `{ accessToken: 'abc', refreshToken: 'def' }`
  - [ ] `clearAll()` removes all four keys; subsequent `getTokens()` returns nulls
  - [ ] `setUser({ id: 1, phone_number: '+919812345678' }, true)` followed by `getUser()` returns the correct object
  - [ ] All functions handle SecureStore errors gracefully (no unhandled promise rejections)
  - [ ] No use of AsyncStorage anywhere in the file
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-004 -- Create API client with interceptors

- **Owner:** frontend-engineer
- **Goal:** Create `services/api.js` with a configured axios instance that handles Bearer token injection, backend envelope unwrapping, and automatic 401 token refresh with request queuing.
- **Rationale:** COMP-004 in ARCH-002. FR-18 (token refresh interceptor), FR-22 (envelope unwrapping), and FR-21 (configurable base URL) are all satisfied by this single module. It is the HTTP foundation for every API call in the app.
- **Dependencies:** TASK-002 (imports `API_BASE_URL`), TASK-003 (imports secureStore for token read/write in interceptor)
- **Component Refs:** COMP-004
- **Affected Files:**
  - `frontend/services/api.js` (new)
- **Implementation Notes:**
  - Create axios instance with `baseURL` from `API_BASE_URL`, `timeout: 15000`, `Content-Type: application/json`.
  - **Request interceptor:** Read access token from a module-level variable (set by AuthContext on sign-in/restore); attach `Authorization: Bearer <token>` if present.
  - **Response interceptor (success):** Unwrap envelope per ARCH-002: if `response.data.success === true`, return `response.data.data`. Handle 204/205 (no body) by returning null.
  - **Response interceptor (error):** Extract structured error from envelope `response.data.error` and throw an `ApiError` object with `{ code, detail, message, fields, retryAfter, httpStatus }`.
  - **401 interceptor:** Per ARCH-002 Token Refresh Interceptor Design:
    - Skip retry for refresh/logout endpoints (prevent infinite loop).
    - Use module-level `isRefreshing` flag and `failedRequestQueue` array.
    - If not already refreshing: read refresh token from secureStore, call `/api/auth/token/refresh/`, on success store new tokens and retry original + queued requests, on failure call the registered sign-out callback and reject all.
    - If already refreshing: queue the request's retry promise.
  - Export `setAccessToken(token)` for AuthContext to update the in-memory token.
  - Export `setSignOutCallback(fn)` for AuthContext to register the logout dispatcher.
  - Network errors (no response) throw with `code: 'network_error'` and message "Connection failed. Please check your internet and try again."
- **Acceptance Criteria:**
  - [ ] Axios instance uses `API_BASE_URL` as baseURL
  - [ ] Successful responses are unwrapped: callers receive `response.data.data`, not the full envelope
  - [ ] Error responses throw an object with `code`, `detail`, `message`, `retryAfter`, `httpStatus` fields
  - [ ] 401 responses trigger automatic token refresh (single refresh for concurrent 401s)
  - [ ] Refresh/logout endpoint 401s are NOT retried (no infinite loop)
  - [ ] Network errors produce a user-friendly error object with `code: 'network_error'`
  - [ ] `setAccessToken` and `setSignOutCallback` are exported and functional
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** medium (interceptor race conditions, circular dependency prevention)
- **Status:** pending

---

### TASK-005 -- Create auth service functions

- **Owner:** frontend-engineer
- **Goal:** Create `services/auth.js` that exports async functions for each auth API endpoint, providing a clean interface between screens and the API client.
- **Rationale:** COMP-005 in ARCH-002. Isolates API endpoint details (paths, request body shapes) from screen components. Screens call `requestOtp(phone)` instead of constructing axios requests directly.
- **Dependencies:** TASK-004 (imports the axios instance from api.js)
- **Component Refs:** COMP-005
- **Affected Files:**
  - `frontend/services/auth.js` (new)
- **Implementation Notes:**
  - Import `api` from `./api.js`.
  - Export functions:
    - `requestOtp(phoneE164)` -- POST `/api/auth/otp/request/` with `{ phone_number: phoneE164 }`. Returns `{ detail, expires_in, resend_available_in }`.
    - `verifyOtp(phoneE164, code)` -- POST `/api/auth/otp/verify/` with `{ phone_number: phoneE164, code }`. Returns `{ access, refresh, is_new_user, user }`.
    - `refreshToken(refreshJwt)` -- POST `/api/auth/token/refresh/` with `{ refresh: refreshJwt }`. Returns `{ access, refresh }`.
    - `logout(refreshJwt)` -- POST `/api/auth/logout/` with `{ refresh: refreshJwt }`. Returns null (205 no body).
  - All functions simply call `api.post(path, body)` and return the result. The envelope is already unwrapped by api.js interceptors. Errors propagate naturally.
- **Acceptance Criteria:**
  - [ ] `requestOtp('+919812345678')` sends POST to `/api/auth/otp/request/` with correct body shape
  - [ ] `verifyOtp('+919812345678', '000000')` sends POST to `/api/auth/otp/verify/` with correct body shape
  - [ ] `refreshToken('jwt_string')` sends POST to `/api/auth/token/refresh/`
  - [ ] `logout('jwt_string')` sends POST to `/api/auth/logout/`
  - [ ] All functions return the unwrapped data payload (not the raw axios response)
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-006 -- Create auth context provider

- **Owner:** frontend-engineer
- **Goal:** Create `context/AuthContext.js` with a React Context + useReducer that manages global auth state and exposes `signIn`, `signOut`, and `restoreSession` actions.
- **Rationale:** COMP-007 in ARCH-002. FR-17 requires global auth state. The navigator, screens, and API interceptor all depend on this shared state to determine authentication status and trigger navigation changes.
- **Dependencies:** TASK-003 (imports secureStore for token persistence in signIn/signOut), TASK-005 (imports auth service for logout API call)
- **Component Refs:** COMP-007
- **Affected Files:**
  - `frontend/context/AuthContext.js` (new)
- **Implementation Notes:**
  - State shape: `{ isAuthenticated: bool, isLoading: bool, user: object|null, isNewUser: bool, accessToken: string|null }`
  - Reducer actions: `SIGN_IN`, `SIGN_OUT`, `SET_ACCESS_TOKEN`, `RESTORE_SESSION`, `LOADING_COMPLETE`
  - Provider component `AuthProvider`:
    - On mount, register the sign-out callback with `api.js` via `setSignOutCallback` (for the 401 interceptor to force logout).
    - `signIn({ user, isNewUser, accessToken })` -- dispatches `SIGN_IN`, calls `setAccessToken` on api.js.
    - `signOut()` -- reads refresh token from secureStore, calls `logout()` from auth service (fire-and-forget, catch errors), calls `secureStore.clearAll()`, dispatches `SIGN_OUT`, calls `setAccessToken(null)` on api.js.
    - `restoreSession({ user, isNewUser, accessToken })` -- dispatches `RESTORE_SESSION`, calls `setAccessToken` on api.js. Used by SplashScreen after successful silent refresh.
  - Export `AuthProvider` component and `useAuth()` custom hook.
  - The refresh token is NOT stored in React state (ARCH-002 DEC-008). It is read from secureStore on demand.
- **Acceptance Criteria:**
  - [ ] `useAuth()` returns `{ isAuthenticated, isLoading, user, isNewUser, signIn, signOut, restoreSession }`
  - [ ] After `signIn({ user: { id: 1, phone_number: '+91...' }, isNewUser: true, accessToken: 'abc' })`, `isAuthenticated` is `true` and `user` is populated
  - [ ] After `signOut()`, `isAuthenticated` is `false`, `user` is `null`, `accessToken` is `null`
  - [ ] `signOut()` clears secureStore even if the logout API call fails
  - [ ] The sign-out callback is registered with api.js on provider mount
  - [ ] `restoreSession` sets authenticated state without calling the login API
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** medium (must correctly wire the signOut callback to the API interceptor to prevent circular dependencies)
- **Status:** pending

---

### TASK-007 -- Create reusable UI components

- **Owner:** frontend-engineer
- **Goal:** Create `components/PrimaryButton.js`, `components/PhoneInput.js`, and `components/OtpInput.js` -- three reusable components that encapsulate design system compliance and shared input behavior.
- **Rationale:** COMP-013, COMP-014, COMP-015 in ARCH-002. These components are consumed by multiple screens and must match Stitch design tokens exactly. Building them before screens ensures consistent styling and avoids duplication.
- **Dependencies:** TASK-002 (imports theme for colors, dimensions, typography)
- **Component Refs:** COMP-013, COMP-014, COMP-015
- **Affected Files:**
  - `frontend/components/PrimaryButton.js` (new)
  - `frontend/components/PhoneInput.js` (new)
  - `frontend/components/OtpInput.js` (new)
- **Implementation Notes:**
  - **PrimaryButton (COMP-013):**
    - Pressable wrapper, 52px height, 14px border radius, `#2563EB` fill, white text (Inter SemiBold).
    - Props: `title` (string), `onPress` (function), `loading` (bool -- shows ActivityIndicator instead of text), `disabled` (bool -- reduces opacity).
    - Minimum touch target 48x48 dp.
    - `accessibilityLabel` defaults to `title`.
    - Disabled state: opacity 0.5, non-interactive.
  - **PhoneInput (COMP-014):**
    - Horizontal row: non-editable "+91" label (with Indian flag emoji) + bordered TextInput.
    - Props: `value` (string), `onChangeText` (function), `error` (string|null -- shown as red text below).
    - TextInput: `keyboardType="number-pad"`, `maxLength={10}`, strips non-digits in onChangeText.
    - 50px height, 12px border radius per Stitch.
    - Error border color on error state.
  - **OtpInput (COMP-015):**
    - Hidden TextInput (`opacity: 0`, `position: absolute`) with `keyboardType="number-pad"`, `maxLength={6}`.
    - 6 visual digit boxes rendered as Views. Each box shows one character from the value. Active box (current input position) has primary-color border.
    - Props: `value` (string), `onChangeText` (function), `error` (string|null).
    - Handles paste (full 6 digits land in value via onChangeText).
    - Tapping any box focuses the hidden TextInput.
    - No `onComplete` auto-submit (ARCH-002 DEC-004).
- **Acceptance Criteria:**
  - [ ] PrimaryButton renders at 52px height, 14px radius, `#2563EB` background
  - [ ] PrimaryButton shows ActivityIndicator when `loading={true}` and is non-interactive
  - [ ] PrimaryButton is visually disabled (reduced opacity) when `disabled={true}`
  - [ ] PhoneInput displays "+91" as a non-editable prefix
  - [ ] PhoneInput only accepts numeric digits and enforces maxLength 10
  - [ ] PhoneInput shows error text below the input when `error` prop is set
  - [ ] OtpInput renders 6 visual boxes that reflect the current value
  - [ ] OtpInput active box has primary-color border
  - [ ] OtpInput handles full 6-digit paste
  - [ ] All components use Inter font and Stitch design tokens from theme.js
  - [ ] All interactive elements have accessibility labels
  - [ ] All touch targets meet 48x48 dp minimum
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-008 -- Create SplashScreen and HomeScreen

- **Owner:** frontend-engineer
- **Goal:** Create `screens/SplashScreen.js` (branding + silent auth check) and `screens/HomeScreen.js` (authenticated placeholder with logout), the two simpler screens in the auth flow.
- **Rationale:** COMP-009 and COMP-012 in ARCH-002. SplashScreen is the app entry point that handles the auth check decision (FR-01, FR-02). HomeScreen is the authenticated hand-off placeholder with logout (FR-19, ARCH-002 DEC-006).
- **Dependencies:** TASK-006 (AuthContext for `restoreSession` and `signOut`), TASK-007 (PrimaryButton for HomeScreen logout button)
- **Component Refs:** COMP-009, COMP-012
- **Affected Files:**
  - `frontend/screens/SplashScreen.js` (new)
  - `frontend/screens/HomeScreen.js` (new)
- **Implementation Notes:**
  - **SplashScreen (COMP-009):**
    - Full screen, canvas background `#F8FAFC`. Spot Rides logo (from `assets/icon.png` or text placeholder) and "Spot Rides" text centered vertically.
    - On mount, simultaneously:
      1. Start a `SPLASH_MIN_DISPLAY_MS` (2000ms) timer.
      2. Read refresh token from secureStore. If found, call `refreshToken()` from auth service.
    - After BOTH timer and auth check complete:
      - If refresh succeeded: store new tokens via secureStore, load user from secureStore, call `restoreSession()` on AuthContext (triggers automatic navigation to AppStack).
      - If no token or refresh failed: call `secureStore.clearAll()`, then `navigation.replace('PhoneLogin')`.
    - Edge cases: network timeout during refresh treated as failure. SecureStore read failure treated as no token.
  - **HomeScreen (COMP-012):**
    - Canvas background. Centered content: "Welcome to Spot Rides" heading, user phone number from `useAuth()`, PrimaryButton ("Log Out").
    - On logout press: call `signOut()` from AuthContext. Navigation happens automatically (conditional stack rendering).
- **Acceptance Criteria:**
  - [ ] SplashScreen displays branding centered on `#F8FAFC` background
  - [ ] SplashScreen stays visible for at least 2 seconds
  - [ ] SplashScreen with no stored tokens navigates to PhoneLogin after the timer
  - [ ] SplashScreen with a valid refresh token navigates to authenticated state (via `restoreSession`)
  - [ ] SplashScreen with an expired refresh token clears storage and navigates to PhoneLogin
  - [ ] HomeScreen displays the authenticated user's phone number from AuthContext
  - [ ] HomeScreen logout button calls `signOut()` and the user is navigated to the auth flow
  - [ ] HomeScreen logout works even when the network is unavailable (local state still cleared)
  - [ ] Both screens use Inter font and Stitch design tokens
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** low
- **Status:** pending

---

### TASK-009 -- Create PhoneLoginScreen and OtpVerificationScreen

- **Owner:** frontend-engineer
- **Goal:** Create `screens/PhoneLoginScreen.js` (phone input + Send OTP) and `screens/OtpVerificationScreen.js` (6-digit verification + resend timer), the two interactive auth screens.
- **Rationale:** COMP-010 and COMP-011 in ARCH-002. These screens handle the core user-facing authentication flow: collecting the phone number (FR-03 through FR-08) and verifying the OTP (FR-09 through FR-15). They are the most complex screens with input validation, API integration, error handling, and countdown timer logic.
- **Dependencies:** TASK-006 (AuthContext for `signIn`), TASK-007 (PrimaryButton, PhoneInput, OtpInput components)
- **Component Refs:** COMP-010, COMP-011
- **Affected Files:**
  - `frontend/screens/PhoneLoginScreen.js` (new)
  - `frontend/screens/OtpVerificationScreen.js` (new)
- **Implementation Notes:**
  - **PhoneLoginScreen (COMP-010):**
    - Layout: Canvas background, "Welcome" heading, "Enter your mobile number to get started" subtext, PhoneInput component, error area, PrimaryButton ("Send OTP"). Wrapped in KeyboardAvoidingView.
    - Local state: `phone` (string, max 10), `error` (string|null), `isLoading` (bool).
    - PrimaryButton disabled when `phone.length !== 10` or `isLoading`.
    - On Send OTP:
      1. Set loading, clear error.
      2. Call `requestOtp(DIAL_CODE + phone)`.
      3. Success: `navigation.navigate('OtpVerification', { phone, resendAvailableIn: response.resend_available_in })`.
      4. Error: map error codes to user messages per ARCH-002 error mapping table (FR-08).
      5. Clear loading.
    - Error messages: `invalid_phone_number` -> "Please enter a valid phone number", `rate_limited` -> "Too many attempts. Please try again in {retry_after} seconds.", `sms_dispatch_failed` -> "Unable to send SMS. Please try again.", `network_error` -> "Connection failed. Please check your internet and try again."
  - **OtpVerificationScreen (COMP-011):**
    - Route params: `{ phone: string, resendAvailableIn: number }`.
    - Layout: Canvas background, back arrow (goBack to PhoneLogin), "Verify your number" heading, masked phone "Code sent to +91 *** *** {last4}", OtpInput, error area, PrimaryButton ("Verify"), resend timer/button. Wrapped in KeyboardAvoidingView.
    - Local state: `code` (string, max 6), `error` (string|null), `isLoading` (bool), `resendTimer` (number), `isResending` (bool).
    - Phone masking: For phone "9812345678", display "Code sent to +91 *** *** 5678".
    - Countdown timer: initialized from `resendAvailableIn`, decrements every second. While > 0: "Resend code in {N}s" (disabled). At 0: "Resend Code" button (enabled).
    - PrimaryButton ("Verify") disabled when `code.length !== 6` or `isLoading`.
    - NO auto-submit (ARCH-002 DEC-004).
    - On Verify:
      1. Set loading, clear error.
      2. Call `verifyOtp(DIAL_CODE + phone, code)`.
      3. Success: call `secureStore.setTokens(access, refresh)`, `secureStore.setUser(user, is_new_user)`, `authContext.signIn({ user, isNewUser: is_new_user, accessToken: access })`. Navigation happens automatically.
      4. Error: map codes per ARCH-002 table. Clear code on `invalid_code` or `too_many_attempts`. On `code_expired` or `no_active_otp`: highlight resend.
      5. Clear loading.
    - On Resend: set isResending, call `requestOtp(DIAL_CODE + phone)`, restart timer on success, show error on failure, clear isResending.
    - Back/Edit number: `navigation.goBack()` (phone preserved in PhoneLoginScreen local state via React Navigation stack).
- **Acceptance Criteria:**
  - [ ] PhoneLoginScreen displays +91 prefix via PhoneInput component (non-editable)
  - [ ] Send OTP button is disabled until exactly 10 digits entered
  - [ ] Send OTP button shows loading state during API call
  - [ ] Successful OTP request navigates to OtpVerificationScreen with phone and resendAvailableIn params
  - [ ] PhoneLoginScreen displays correct error messages for `invalid_phone_number`, `rate_limited`, `sms_dispatch_failed`, and network errors
  - [ ] OtpVerificationScreen shows masked phone number (first 6 digits masked, last 4 visible)
  - [ ] OtpVerificationScreen countdown timer decrements each second and enables resend at zero
  - [ ] Verify button is disabled until exactly 6 digits entered
  - [ ] Verify button shows loading state during API call
  - [ ] Successful verification stores tokens and user, signs in via AuthContext, navigates to authenticated state
  - [ ] OTP error codes display correct user messages and clear input where specified
  - [ ] Resend calls requestOtp and restarts timer on success
  - [ ] Back navigation returns to PhoneLoginScreen with phone number preserved
  - [ ] Both screens use KeyboardAvoidingView for keyboard handling (FR-24)
  - [ ] Both screens use Inter font and Stitch design tokens
  - [ ] All interactive elements have accessibility labels (FR-25)
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** medium (complex state management with timer, error handling, and navigation; most likely screen for UX bugs)
- **Status:** pending

---

### TASK-010 -- Create RootNavigator, update App.js, and verify end-to-end

- **Owner:** frontend-engineer
- **Goal:** Create `navigation/RootNavigator.js` (conditional auth/app stack switching), rewrite `App.js` (font loading, providers, NavigationContainer), and verify the complete auth flow works end-to-end.
- **Rationale:** COMP-001 and COMP-008 in ARCH-002. This is the integration task that wires all previously-built pieces together. FR-20 (navigation structure), font loading (ARCH-002 Font Loading section), and the complete splash-to-login-to-otp-to-home flow must work as a cohesive whole.
- **Dependencies:** TASK-008, TASK-009 (all screens must exist)
- **Component Refs:** COMP-001, COMP-008
- **Affected Files:**
  - `frontend/navigation/RootNavigator.js` (new)
  - `frontend/App.js` (modified -- full rewrite)
- **Implementation Notes:**
  - **RootNavigator (COMP-008):**
    - Import `useAuth()` from AuthContext.
    - Import all 4 screens.
    - Create `AuthStack` (native-stack): SplashScreen (initial route), PhoneLoginScreen, OtpVerificationScreen. All with `headerShown: false` except OtpVerification which has back enabled via header or in-screen back button.
    - Create `AppStack` (native-stack): HomeScreen. `headerShown: false`.
    - Conditional render: if `isAuthenticated` render AppStack, else render AuthStack.
    - While `isLoading` is true from AuthContext, render nothing (SplashScreen handles its own display).
  - **App.js (COMP-001):**
    - Load Inter fonts via `useFonts` from `@expo-google-fonts/inter` (`Inter_400Regular`, `Inter_500Medium`, `Inter_600SemiBold`, `Inter_700Bold`).
    - Call `SplashScreen.preventAutoHideAsync()` before component mounts to keep native splash visible during font loading.
    - Once fonts loaded, hide native splash via `SplashScreen.hideAsync()`.
    - Render: `<AuthProvider><NavigationContainer><RootNavigator /></NavigationContainer></AuthProvider>`.
    - Include `<StatusBar style="auto" />`.
  - **End-to-end verification:**
    - Fresh launch (no tokens): Splash -> PhoneLogin -> enter 10 digits -> Send OTP -> OtpVerification -> enter 000000 -> Verify -> HomeScreen.
    - Logout from HomeScreen -> returns to PhoneLogin.
    - Re-launch with stored tokens: Splash -> silent refresh -> HomeScreen (if backend running) or Splash -> PhoneLogin (if refresh fails).
    - Keyboard does not obscure inputs on either auth screen.
    - All screens match Stitch design tokens visually.
- **Acceptance Criteria:**
  - [ ] App loads Inter fonts and shows native splash screen until fonts are ready
  - [ ] NavigationContainer wraps RootNavigator, which is wrapped by AuthProvider
  - [ ] Unauthenticated users see AuthStack (Splash -> PhoneLogin -> OtpVerification); cannot access HomeScreen
  - [ ] Authenticated users see AppStack (HomeScreen); cannot swipe back to login screens
  - [ ] Auth state change (signIn) automatically transitions from AuthStack to AppStack
  - [ ] Auth state change (signOut) automatically transitions from AppStack to AuthStack
  - [ ] Complete flow works: launch -> splash -> phone login -> send OTP -> verify (000000 with dev backend) -> home -> logout -> phone login
  - [ ] No crashes or unhandled exceptions during the flow
  - [ ] Splash-to-login transition completes within 5 seconds (AC-25)
  - [ ] All screens use `#F8FAFC` canvas background, `#2563EB` primary buttons, Inter font
- **Tests Required:** none (out of scope per FEAT-002)
- **Risk:** medium (integration of all pieces; font loading timing; navigation state edge cases)
- **Status:** pending

---

## Critical Path

TASK-001 -> TASK-002 -> TASK-003 -> TASK-004 -> TASK-005 -> TASK-006 -> TASK-009 -> TASK-010

8 hops. The longest sequential chain runs through the services layer (secureStore -> api -> auth -> context) before reaching the most complex screen task (PhoneLogin + OtpVerification) and final integration.

## Parallel Groups

| Group | Tasks | Notes |
|-------|-------|-------|
| P-A | TASK-003, TASK-007 | Both depend only on TASK-002. SecureStore and UI components are independent of each other. |
| P-B | TASK-008, TASK-009 | Both depend on TASK-006 + TASK-007. SplashScreen/HomeScreen and PhoneLogin/OtpVerification are independent of each other. |

## Rollout

- **Feature flag:** false
- **Migration:** false (frontend-only; no database changes)
- **Order:** install deps -> config -> services -> context -> components -> screens -> navigator + App.js
- **Rollback:** Revert the commit. App returns to default Expo template. No server-side state affected.

## Blockers

None. The backend API (FEAT-001) is complete and operational. All ARCH-002 decisions are resolved. The dev backend with `OTP_DEV_MODE=True` and fixed code `000000` is available for testing.
