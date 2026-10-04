# Requirement: Frontend Authentication Screens

**ID:** FEAT-002
**Type:** requirement
**Version:** 1
**Status:** ready
**Owner:** product-manager
**Date:** 2026-10-04
**Priority:** critical

---

## Summary

Implement the three authentication screens for the Spot Rides Expo/React Native app -- Splash, Phone Login, and OTP Verification -- integrating with the already-built backend auth API (FEAT-001). This feature establishes the app's navigation skeleton, secure token storage, and auth state management so that an authenticated user can be handed off to the rest of the app.

## Goal

Enable a Spot Rides mobile user to open the app, enter their phone number, verify via OTP, and arrive at an authenticated state with securely stored JWT tokens, using three screens that match the Stitch design system.

## Problem

The Spot Rides frontend is currently a bare Expo project with no screens, no navigation, no API layer, and no authentication flow. The backend auth API (FEAT-001) is fully built and operational, but there is no mobile client to consume it. Without this layer, no user can authenticate, and no subsequent features (ride booking, profile setup, driver onboarding) can be built on the frontend.

## Users

| Role | Description |
|------|-------------|
| New rider | A person opening the Spot Rides app for the first time who needs to register by verifying their phone number. |
| Returning rider | A person who previously authenticated and expects to either be auto-logged-in (valid refresh token) or re-verify via OTP. |
| Frontend engineer | Developer implementing and maintaining the Expo screens, navigation, and API integration. |

## User Stories

| ID | Statement | Priority |
|----|-----------|---------|
| US-01 | As a new rider, I want to see a splash screen with the Spot Rides branding when I open the app, so that I know the app is loading and I have confidence I am using the correct product. | must |
| US-02 | As a new rider, I want to enter my 10-digit Indian mobile number (with +91 shown automatically) on the login screen and tap "Send OTP", so that I can begin the verification process. | must |
| US-03 | As a rider who requested an OTP, I want to enter the 6-digit code I received via SMS and tap "Verify", so that I can authenticate and start using the app. | must |
| US-04 | As a rider who did not receive the SMS, I want to tap a "Resend" button after a visible countdown expires, so that I can get a new code without guessing when it becomes available. | must |
| US-05 | As a returning rider with a valid session, I want the splash screen to detect my stored tokens and skip the login flow, so that I am not asked to re-verify on every app launch. | must |
| US-06 | As a rider whose access token expired, I want the app to silently refresh it using my stored refresh token, so that I remain logged in without interruption. | must |
| US-07 | As a rider, I want to see clear, user-friendly error messages when something goes wrong (invalid number, wrong code, rate limited, network failure), so that I know what to do next. | must |
| US-08 | As a rider, I want to log out and have my session fully cleared, so that a shared or lost device cannot access my account. | should |
| US-09 | As a rider, I want to see loading indicators while the app communicates with the server, so that I know the app is working and do not tap buttons repeatedly. | must |

## Functional Requirements

| ID | Description | Priority |
|----|-------------|---------|
| FR-01 | **Splash Screen**: Display the Spot Rides logo and app name centered on screen, matching the Stitch design (screen `de7640c5f0dd48d590d66eb06a8261e7`). The splash screen must be shown for a minimum of 2 seconds to ensure branding visibility. | must |
| FR-02 | **Splash Screen -- Auth Check**: On mount, the splash screen must check for an existing refresh token in secure storage. If a valid refresh token exists, attempt a silent token refresh (`POST /api/auth/token/refresh/`). On success, navigate to the authenticated app root (hand-off point). On failure (expired/blacklisted token), clear stored tokens and navigate to the Phone Login screen. If no token exists, navigate to the Phone Login screen. | must |
| FR-03 | **Phone Login Screen**: Display a phone number input field prefixed with a fixed, non-editable "+91" (India) country code label and a "Send OTP" button, matching the Stitch design (screen `c9efcd3463ee446ab00865d79baa0ed4`). There must be no country code picker or selector; the app is India-only. | must |
| FR-04 | **Phone Login -- Fixed India Dial Code**: The dial code is hardcoded to `+91` (India). It must be displayed as a non-interactive prefix next to the phone input (e.g., a label or styled text reading "+91" with the Indian flag). The prefix is automatically prepended when constructing the E.164 number for API submission. No country selection UI is needed. | must |
| FR-05 | **Phone Login -- Input Validation**: The phone input must only accept numeric digits. The "Send OTP" button must be disabled until the phone number field contains exactly 10 digits (standard Indian mobile number length). Client-side validation is a UX convenience; the backend performs canonical E.164 validation. | must |
| FR-06 | **Phone Login -- OTP Request**: When the user taps "Send OTP", the app must call `POST /api/auth/otp/request/` with the full E.164-formatted phone number. While the request is in flight, the button must show a loading state and be disabled to prevent duplicate submissions. | must |
| FR-07 | **Phone Login -- Success Navigation**: On a successful OTP request (200 response), navigate to the OTP Verification screen, passing the phone number and the `resend_available_in` value from the response. | must |
| FR-08 | **Phone Login -- Error Handling**: Handle the following backend error responses with user-visible messages: `400 invalid_phone_number` ("Please enter a valid phone number"), `429 rate_limited` ("Too many attempts. Please try again in {retry_after} seconds."), `502 sms_dispatch_failed` ("Unable to send SMS. Please try again."). Network/timeout errors must show a generic connectivity message. | must |
| FR-09 | **OTP Verification Screen**: Display a 6-digit code input (individual digit boxes or a single field accepting exactly 6 digits), the masked phone number (e.g., "Code sent to +91 *** *** 2671"), a "Verify" button, and a resend countdown timer, matching the Stitch design (screen `92e565d0cbcb40248ba40f48d7be3c15`). | must |
| FR-10 | **OTP Verification -- Auto-Submit**: When the user enters all 6 digits, the app may optionally auto-submit (architect's discretion), but a manual "Verify" button must always be available. The "Verify" button must be disabled until exactly 6 digits are entered. | should |
| FR-11 | **OTP Verification -- Verify Request**: When the user taps "Verify" (or auto-submit triggers), call `POST /api/auth/otp/verify/` with the phone number and code. While the request is in flight, show a loading state and disable the button. | must |
| FR-12 | **OTP Verification -- Success Handling**: On successful verification (200 response), extract `access` and `refresh` JWT tokens and store them in secure storage (see FR-16). Store the `user` object (id, phone_number) and `is_new_user` flag. Navigate to the authenticated app root (hand-off point). | must |
| FR-13 | **OTP Verification -- Error Handling**: Handle: `400 invalid_code` ("Incorrect code. Please try again." -- clear the input), `400 code_expired` ("Code has expired. Please request a new one." -- show resend option prominently), `400 no_active_otp` ("No active code found. Please request a new one." -- navigate back to Phone Login or show resend), `429 too_many_attempts` ("Too many incorrect attempts. Please request a new code." -- reset the input and enable resend). Network errors must show a generic connectivity message. | must |
| FR-14 | **OTP Verification -- Resend Timer**: Display a countdown timer initialized from the `resend_available_in` value (typically 30 seconds). While the timer is active, the resend action must be disabled and the remaining seconds must be visible (e.g., "Resend code in 28s"). When the timer reaches zero, enable a "Resend Code" button. Tapping it calls `POST /api/auth/otp/request/` again with the same phone number and restarts the countdown on success. | must |
| FR-15 | **OTP Verification -- Edit Phone Number**: Provide a way for the user to go back and correct their phone number (back navigation or an "Edit number" link). | must |
| FR-16 | **Secure Token Storage**: JWT access and refresh tokens must be stored using `expo-secure-store` (or an equivalent secure storage mechanism that uses the platform keychain/keystore). Tokens must never be stored in `AsyncStorage`, plain files, or any unencrypted medium. | must |
| FR-17 | **Auth State Management**: The app must maintain a global auth state (e.g., via React Context or a lightweight state manager) that tracks: whether the user is authenticated, the current access token, the current user object (id, phone_number), and the `is_new_user` flag. All downstream screens can consume this context. | must |
| FR-18 | **Token Refresh Interceptor**: API calls to authenticated endpoints must include an `Authorization: Bearer <access_token>` header. If a request returns 401 (token expired), the app must automatically attempt a token refresh using the stored refresh token (`POST /api/auth/token/refresh/`). If the refresh succeeds, retry the original request with the new access token. If the refresh fails, clear all stored tokens and navigate to the Phone Login screen. | must |
| FR-19 | **Logout**: The app must expose a logout action (callable from wherever the authenticated app root provides it). Logout must call `POST /api/auth/logout/` with the stored refresh token, then clear all tokens and user data from secure storage, reset auth state, and navigate to the Phone Login screen. If the logout API call fails (network error, already-expired token), the client must still clear local state and navigate to login. | should |
| FR-20 | **Navigation Structure**: Use React Navigation (or Expo Router -- architect's choice) to manage the navigation stack. The flow must be: Splash Screen (initial route) -> Phone Login Screen -> OTP Verification Screen -> Authenticated App Root (placeholder/hand-off screen). Auth screens and authenticated screens should be in separate navigation groups so that an authenticated user cannot navigate back to the login flow, and an unauthenticated user cannot access authenticated screens. | must |
| FR-21 | **API Base URL Configuration**: The backend API base URL must be configurable via environment variable or Expo config (not hardcoded). It must support different values for development (e.g., `http://localhost:8000`) and production. | must |
| FR-22 | **Envelope Response Handling**: All backend responses are wrapped in an envelope: `{ status, message, data }`. The API layer must unwrap this envelope and expose the inner `data` payload to callers. Error responses must extract the error code from the envelope for display logic. | must |
| FR-23 | **Loading States**: Every API call triggered by user action (Send OTP, Verify, Resend) must show a loading indicator (button spinner or overlay) and disable the triggering control until the response is received or a timeout occurs. | must |
| FR-24 | **Keyboard Handling**: The Phone Login and OTP screens must handle keyboard appearance gracefully. The input fields and action buttons must remain visible and accessible when the on-screen keyboard is open, using `KeyboardAvoidingView` or equivalent. | must |
| FR-25 | **Accessibility**: All interactive elements must have accessibility labels. The minimum touch target for all tappable elements must be 48x48 dp, per the Stitch design system. | should |

## Stitch Design References

| Screen | Stitch Screen ID | Notes |
|--------|-----------------|-------|
| Splash Screen | `de7640c5f0dd48d590d66eb06a8261e7` | App logo, branding, background color |
| Phone Login Screen | `c9efcd3463ee446ab00865d79baa0ed4` | Country picker, phone input, "Send OTP" button |
| OTP Verification Screen | `92e565d0cbcb40248ba40f48d7be3c15` | 6-digit input, verify button, resend timer, masked phone |

### Design System Tokens (from Stitch "SPOT RIDESMARK2")

| Token | Value |
|-------|-------|
| Primary color | `#2563EB` (Electric Royal Blue) |
| Secondary / Success | `#16A34A` (Emerald Green) |
| Font family | Inter |
| Canvas background | `#F8FAFC` |
| Surface (cards, sheets) | `#FFFFFF` |
| Border | `#E2E8F0` |
| Text muted | `#64748B` |
| Text primary (Deep Slate) | `#0F172A` |
| Primary button height | 52px |
| Primary button border radius | 14px |
| Primary button fill | `#2563EB` |
| Input field height | 50px |
| Input field border radius | 12px |
| Card border radius | 16px |
| Full pill badge radius | 9999px |
| Minimum touch target | 48x48 dp |

## Acceptance Criteria

| ID | Description | Verification | Priority |
|----|-------------|-------------|---------|
| AC-01 | Given the app is launched for the first time (no stored tokens), when the splash screen appears, then the Spot Rides logo and app name are displayed centered on screen for at least 2 seconds before navigating to the Phone Login screen. | Manual: launch fresh app, observe splash branding and timing, confirm navigation to login. | must |
| AC-02 | Given the app is launched with a valid refresh token in secure storage, when the splash screen performs the auth check, then the token is refreshed silently and the user is navigated to the authenticated app root without seeing the login screen. | Manual: authenticate, force-close app, relaunch, confirm auto-login. | must |
| AC-03 | Given the app is launched with an expired or blacklisted refresh token in secure storage, when the splash screen attempts a silent refresh, then the stored tokens are cleared and the user is navigated to the Phone Login screen. | Manual: authenticate, wait for token expiry or call logout from backend, relaunch app, confirm redirect to login. | must |
| AC-04 | Given the Phone Login screen is displayed, then a fixed, non-editable "+91" prefix (with Indian flag) is shown next to the phone input field. There is no country code picker or dropdown. | Manual: open Phone Login screen, confirm +91 is displayed and not tappable/editable. | must |
| AC-05 | Given the Phone Login screen, when the phone input contains fewer than 10 digits, then the "Send OTP" button is visually disabled and non-interactive. When exactly 10 digits are entered, the button becomes active. | Manual: type progressively into the field, observe button state; confirm it activates at 10 digits. | must |
| AC-06 | Given a valid phone number is entered, when the user taps "Send OTP", then a loading indicator appears on the button, the button is disabled, and `POST /api/auth/otp/request/` is called with the phone number in E.164 format. | Manual: enter number, tap Send OTP, observe loading state; verify network request in dev tools or proxy. | must |
| AC-07 | Given the OTP request succeeds (200), when the response is received, then the app navigates to the OTP Verification screen showing the masked phone number and a resend countdown timer initialized to the `resend_available_in` value from the response. | Manual: complete OTP request, observe navigation, confirm masked number display and countdown start value. | must |
| AC-08 | Given the OTP request returns `400 invalid_phone_number`, when the response is received, then an inline error message "Please enter a valid phone number" is displayed on the Phone Login screen and the input remains editable. | Manual: enter a clearly invalid number (e.g., "123"), tap Send OTP, observe error message. | must |
| AC-09 | Given the OTP request returns `429 rate_limited` with a `retry_after` value, when the response is received, then the message "Too many attempts. Please try again in {retry_after} seconds." is displayed on the Phone Login screen. | Manual: trigger rate limit by sending rapid requests, observe error with countdown. | must |
| AC-10 | Given the OTP request returns `502 sms_dispatch_failed`, when the response is received, then the message "Unable to send SMS. Please try again." is displayed and the user can retry immediately. | Manual: simulate backend SMS failure, observe error message and retry ability. | must |
| AC-11 | Given the OTP Verification screen is displayed, when the user enters all 6 digits and taps "Verify", then a loading indicator appears, the button is disabled, and `POST /api/auth/otp/verify/` is called with the phone number and code. | Manual: enter 6-digit code, tap Verify, observe loading state and network request. | must |
| AC-12 | Given the OTP verification succeeds (200), when the response is received, then the `access` and `refresh` tokens are stored in secure storage (not AsyncStorage), the user object and `is_new_user` flag are stored in auth state, and the app navigates to the authenticated app root. | Manual: verify OTP, confirm navigation to authenticated screen; inspect secure storage via debug tooling to confirm tokens are present. | must |
| AC-13 | Given the OTP verification returns `400 invalid_code`, when the response is received, then the message "Incorrect code. Please try again." is displayed and the code input is cleared for re-entry. | Manual: enter wrong code, tap Verify, observe error message and input cleared. | must |
| AC-14 | Given the OTP verification returns `400 code_expired`, when the response is received, then the message "Code has expired. Please request a new one." is displayed and the resend option is made prominent. | Manual: wait for code expiry, attempt verification, observe error and resend prompt. | must |
| AC-15 | Given the OTP verification returns `429 too_many_attempts`, when the response is received, then the message "Too many incorrect attempts. Please request a new code." is displayed, the code input is cleared, and the resend option is enabled. | Manual: exhaust verification attempts, observe error message and resend availability. | must |
| AC-16 | Given the OTP Verification screen with an active resend timer, when the countdown is running, then the resend action displays remaining seconds (e.g., "Resend code in 15s") and is not tappable. When the timer reaches zero, a "Resend Code" button becomes active. | Manual: observe countdown decrement each second; confirm button becomes active at zero. | must |
| AC-17 | Given the resend timer has expired, when the user taps "Resend Code", then `POST /api/auth/otp/request/` is called again, and on success the countdown timer restarts from the new `resend_available_in` value. | Manual: wait for timer, tap Resend, observe new API call and timer restart. | must |
| AC-18 | Given an authenticated user whose access token has expired, when any authenticated API call returns 401, then the app automatically calls `POST /api/auth/token/refresh/` with the stored refresh token. If refresh succeeds, the original request is retried with the new access token. If refresh fails, stored tokens are cleared and the user is navigated to the Phone Login screen. | Manual: wait for access token expiry, trigger an authenticated API call, confirm seamless refresh or redirect to login on failure. | must |
| AC-19 | Given an authenticated user, when the logout action is triggered, then `POST /api/auth/logout/` is called with the refresh token, all tokens and user data are cleared from secure storage, auth state is reset, and the user is navigated to the Phone Login screen. If the logout API call fails, local state is still cleared and navigation still occurs. | Manual: log out, confirm navigation to login; log out with airplane mode, confirm same result. | should |
| AC-20 | Given any screen with a network request in flight, when the request is pending, then the triggering button shows a loading indicator and is disabled, preventing duplicate submissions. | Manual: observe all three API interactions (Send OTP, Verify, Resend) for loading states. | must |
| AC-21 | Given no network connectivity, when the user attempts any API action, then a user-friendly error message about connectivity is displayed (not a raw error or stack trace). | Manual: enable airplane mode, attempt Send OTP, observe error message. | must |
| AC-22 | Given the Phone Login or OTP screen with the on-screen keyboard open, when the keyboard appears, then the input fields and action buttons remain visible and are not obscured by the keyboard. | Manual: tap input field on both screens, confirm all interactive elements remain accessible with keyboard open. | must |
| AC-23 | Given all three screens, when rendered, then their visual appearance matches the Stitch designs: primary button is 52px tall with 14px radius and `#2563EB` fill, input fields are 50px tall with 12px radius, the Inter font is used, background is `#F8FAFC`, and text colors match the design tokens. | Manual: compare rendered screens against Stitch designs side-by-side. | must |
| AC-24 | Given the OTP Verification screen, when the user wants to change the phone number, then a back navigation option or "Edit number" link is available that returns to the Phone Login screen with the previously entered number preserved. | Manual: navigate to OTP screen, tap back/edit, confirm return to login with number intact. | must |
| AC-25 | Given a fresh install, when the app is opened, then there is no crash, no unhandled exception, and the splash-to-login flow completes within 5 seconds on a mid-range device over a stable network. | Manual: fresh install test on Android emulator and iOS simulator. | must |

## Non-Goals

- Profile Setup screen (Stitch design exists but implementation deferred)
- Role Selection screen (Stitch design exists but implementation deferred)
- Email Verification screen (Stitch design exists but implementation deferred)
- Driver Verification screen (Stitch design exists but implementation deferred)
- Verification Complete screen (Stitch design exists but implementation deferred)
- Test case creation (explicitly out of scope for this feature)
- Backend changes of any kind (FEAT-001 is complete and deployed)
- Biometric authentication (Face ID, fingerprint) for app unlock
- Social login (Google, Apple, Facebook) integration
- Deep linking into the auth flow
- Push notification permission prompts during auth
- Analytics or event tracking integration
- Localization / internationalization of screen text (English only for v1)
- Offline-first auth flow (network required for OTP request/verify)
- Animated transitions beyond standard React Navigation defaults
- Dark mode support

## Constraints

- Must use Expo SDK 57 with the managed workflow; no bare native modules unless available via Expo
- Must target React Native 0.86 / React 19.2 as present in the current `package.json`
- Must use `expo-secure-store` (or an Expo-compatible secure storage library) for token persistence -- `AsyncStorage` is not acceptable for tokens
- Must follow the Stitch "SPOT RIDESMARK2" design system tokens exactly (colors, radii, heights, font)
- All API calls must target the `/api/auth/` prefix per CLAUDE.md convention
- Screens must reside in `frontend/screens/` per CLAUDE.md convention
- Shared components must reside in `frontend/components/` per CLAUDE.md convention
- The Inter font must be loaded (e.g., via `expo-font` and `@expo-google-fonts/inter` or bundled assets)
- The backend API base URL must be configurable, not hardcoded
- The app must not store any secrets (API keys, tokens) in source code or unencrypted storage

## Dependencies

| Name | Type | Required |
|------|------|----------|
| FEAT-001 (Backend OTP Auth API) | Feature (complete) | true |
| `@react-navigation/native` + `@react-navigation/native-stack` (or `expo-router`) | npm package | true |
| `expo-secure-store` | npm package | true |
| `expo-font` | npm package | true |
| Inter font (`@expo-google-fonts/inter` or bundled) | npm package / asset | true |
| Indian flag icon/emoji for the +91 prefix display | Asset | false |
| HTTP client (`axios` or `fetch` wrapper) | npm package / built-in | true |
| Stitch design exports (screen `de7640c5f0dd48d590d66eb06a8261e7`, `c9efcd3463ee446ab00865d79baa0ed4`, `92e565d0cbcb40248ba40f48d7be3c15`) | Design asset | true |

## Assumptions

- The backend API (FEAT-001) is deployed and accessible at a configurable base URL during development (e.g., `http://localhost:8000` or a shared dev server).
- The backend envelope format `{ status, message, data }` wraps all responses consistently, including error responses.
- The Inter font is available via `@expo-google-fonts/inter` or can be bundled as a static asset.
- The Stitch screen IDs provided correspond to finalized designs that will not change during implementation.
- The "authenticated app root" (the screen users see after successful auth) can be a simple placeholder screen for now; subsequent features will replace it.
- `expo-secure-store` is sufficient for both iOS and Android token storage within the Expo managed workflow. Value size limit (2048 bytes) is sufficient for JWT tokens.
- The app is India-only; the +91 dial code is hardcoded and no country selection is needed.
- `OTP_DEV_MODE=True` with `DEBUG=True` is available on the backend, so frontend developers can test the full flow using a fixed code (`000000`) without real SMS.
- The `resend_available_in` field from the OTP request response is always present on success and is an integer representing seconds.
- A mid-range test device completes the splash-to-login transition within 5 seconds given stable network.

## Open Questions

| ID | Question | Blocking |
|----|----------|---------|
| OQ-01 | Should the architect use React Navigation (`@react-navigation`) or Expo Router (`expo-router`) for navigation? Both are compatible with Expo SDK 57. The requirement is agnostic; the architect decides. | false |
| OQ-02 | Should the 6-digit OTP input use individual digit boxes (one `TextInput` per digit) or a single styled input field? The Stitch design should clarify this, but the architect may adapt for usability. | false |
| OQ-03 | Should the splash screen minimum display time (2 seconds) be configurable or hardcoded? | false |
| OQ-04 | What is the production API base URL? For development, `http://localhost:8000` is assumed. Production URL is needed before release but does not block implementation. | false |
| OQ-05 | Should the app support SMS auto-read / OTP autofill via platform APIs (Android SMS Retriever, iOS auto-fill)? This would improve UX but adds complexity. Currently not in scope; confirm if it should be added. | false |
| OQ-06 | Should the "authenticated app root" placeholder screen include a logout button for testing purposes, or will that be deferred to a subsequent feature? Recommend including it for dev/test usability. | false |

## Success Metrics

| Metric | Target |
|--------|--------|
| Time from app launch to login screen visible (cold start, no stored session) | Under 4 seconds on mid-range device |
| Time from app launch to authenticated root (warm start, valid refresh token) | Under 3 seconds on mid-range device |
| User can complete full OTP flow (enter number, receive code, verify) without confusion | Qualitative: no UX blockers in internal testing |
| Zero crashes or unhandled exceptions during the auth flow | 0 crash reports in auth screens |
| All backend error codes surfaced as user-friendly messages | 100% coverage of documented error codes |
| Visual fidelity to Stitch designs | Approved in design review |
