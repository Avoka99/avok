# AVOK ARCHITECTURE - UPDATED DOCUMENTATION

**Updated**: March 29, 2025  
**Status**: Production-Ready ✅  
**Changes**: Profile picture feature removed, token system updated

---

## SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AVOK PLATFORM                                │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐      ┌──────────────────┐
│   Web Frontend   │         │   Mobile Web     │      │   Admin Panel    │
│  (Next.js 15)    │         │  (Responsive)    │      │  (Dashboard)     │
│                  │         │                  │      │                  │
│  - Auth (login)  │         │  - Order Status  │      │  - Dispute Mgmt  │
│  - Wallet        │         │  - Payment Init  │      │  - User Flag     │
│  - Orders        │         │  - Delivery OTP  │      │  - KYC Review    │
│  - Disputes      │         │  - Notifications │      │  - Admin Tools   │
└────────┬─────────┘         └────────┬─────────┘      └────────┬─────────┘
         │                           │                          │
         │    HTTPS (TLS 1.3)        │                          │
         └──────────────────┬────────┴──────────────────────────┘
                            │
                ┌───────────▼───────────┐
                │   API GATEWAY / LB    │
                │  (nginx / HAProxy)    │
                │  Rate Limit: 100/min  │
                └───────────┬───────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐        ┌─────────┐
   │ API-1   │         │ API-2   │        │ API-3   │
   │(uvicorn)│         │(uvicorn)│        │(uvicorn)│
   │ FastAPI │         │ FastAPI │        │ FastAPI │
   └────┬────┘         └────┬────┘        └────┬────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   ┌─────────────────┬──────────────┬─────────────────┐
   │                 │              │                 │
   │           CORE SERVICES        │                 │
   │          (in FastAPI)          │                 │
   │                 │              │                 │
   ├─────────────────┼──────────────┤                 │
   │ Auth Service    │ Order Service│ Payment Service │
   │ - Register      │ - Create     │ - MoMo Init     │
   │ - Login         │ - List       │ - Bank Transfer │
   │ - 2FA (SMS)     │ - Get Detail │ - Avok Balance  │
   │ - Refresh token │ - Update     │ - Callback      │
   │ - Logout        │ - Delete     │ - Fee Calc      │
   │ - KYC Submit    │              │                 │
   │ - KYC Approve   │              │                 │
   │                 │              │                 │
   ├─────────────────┼──────────────┤                 │
   │ Wallet Service  │ Escrow Srv   │ Fraud Detection │
   │ - Balance       │ - Hold Funds │ - Score User    │
   │ - Deposit       │ - Release    │ - Score Dispute │
   │ - Withdraw      │ - Refund     │ - Auto Flag     │
   │ - Transactions  │ - OTP Verify │ - Risk Analysis │
   │                 │ - Auto-Release                 │
   ├─────────────────┴──────────────┼─────────────────┤
   │ Dispute Service │ Notification │ Guest Checkout  │
   │ - Create        │ - Send SMS   │ - Create Session│
   │ - Add Evidence  │ - Send Email │ - Temp Token    │
   │ - Analyze       │ - Webhook    │ - Convert to    │
   │ - Resolve       │ - Delivery   │   User Account  │
   │                 │              │                 │
   └─────────────────┴──────────────┴─────────────────┘
        │                │                │
        │ SQLAlchemy     │ SQLAlchemy     │ Redis
        │ ORM (async)    │ ORM (async)    │ (Cache)
        │                │                │
        ▼                ▼                ▼
    ┌──────────────────────────┐    ┌─────────────┐
    │    PostgreSQL 15         │    │ Redis 7     │
    │  (Main Database)         │    │ (In-Memory) │
    │                          │    │             │
    │ Tables:                  │    │ Data:       │
    │ - users                  │    │ - Sessions  │
    │ - wallets                │    │ - OTP       │
    │ - orders                 │    │ - Cache     │
    │ - transactions           │    │ - Blacklist │
    │ - disputes               │    │ - Queues    │
    │ - admin_actions          │    │             │
    │ - guest_checkout_sessions│    │ (Broker)    │
    │ - notifications          │    │             │
    │ - audit_logs             │    │ (Backend)   │
    │                          │    │             │
    └──────────┬───────────────┘    └──────┬──────┘
               │                           │
               │ Async Replication         │
               │                    Pub/Sub│
               │                           │
               └───────────┬───────────────┘
                           │
                    ┌──────▼────────┐
                    │ Celery Beat   │
                    │ (Scheduler)   │
                    │               │
                    │ Scheduled Jobs:
                    │ - Auto-release│
                    │ - Reminders   │
                    │ - KYC timeout │
                    │ - Cleanup     │
                    └──────┬────────┘
                           │
                    Task Queue (Redis)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    ┌────────────┐  ┌────────────┐  ┌──────────────┐
    │  Worker 1  │  │  Worker 2  │  │  Worker N    │
    │ (Celery)   │  │ (Celery)   │  │  (Celery)    │
    │            │  │            │  │              │
    │ Tasks:     │  │ - SMS Send  │  │ - Email      │
    │ - Payment  │  │ - OTP Gen   │  │ - Webhooks   │
    │ - Fraud    │  │ - Cleanup   │  │ - Reports    │
    └────┬───────┘  └────────────┘  └──────┬───────┘
         │                                   │
         └──────────────┬────────────────────┘
                        │
            ┌───────────┼───────────┐
            │           │           │
            ▼           ▼           ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │ SMS API  │ │Email API │ │ MoMo API │
      │(Africa's │ │(SendGrid)│ │(Provider)│
      │ Talking) │ │          │ │          │
      └──────────┘ └──────────┘ └──────────┘
```

---

## DATA FLOW: ORDER LIFECYCLE (WITH TOKENS)

```
1. USER AUTHENTICATION
   ┌─────────────┐
   │ POST /login │
   └──────┬──────┘
          ▼
   ┌─────────────────────────────────────┐
   │ Backend validates phone + password  │
   │ Hashes password with bcrypt         │
   │ Checks account lockout              │
   └──────┬──────────────────────────────┘
          ▼
   ┌──────────────────────────────────────────┐
   │ Creates tokens:                          │
   │ - access_token (30 min, unique jti)     │
   │ - refresh_token (7 days, unique jti)    │
   └──────┬───────────────────────────────────┘
          ▼
   Frontend stores in:
   - localStorage (Zustand persistence)
   - Memory (useAuthStore)
   - Cookie (HttpOnly, SameSite=Lax)
   
   Auto-refresh scheduled:
   - 1 min before access_token expiry
   - Call POST /auth/refresh
   - Get new token pair
   - Old refresh_token revoked

2. CREATE ORDER
   User → API (Authorization: Bearer {accessToken})
      ↓
   API validates token (not revoked, not expired)
      ↓
   OrderService → PostgreSQL
      ↓
   Order(PENDING_PAYMENT)

3. INITIATE PAYMENT
   User → API → PaymentService
         ├─→ FraudDetectionService (analyzes risk)
         ├─→ Fee Calculation
         └─→ Route to Payment Channel:
             ├─→ Avok Balance (direct → escrow)
             ├─→ MoMo (Celery task → SMS → webhook)
             ├─→ Bank (virtual account setup)
             └─→ Transaction(PENDING)

4. PAYMENT CONFIRMATION
   Provider → Webhook → API → PaymentService
                        ├─→ Checks transaction status (idempotent)
                        ├─→ Transaction(COMPLETED)
                        └─→ EscrowService.hold_funds_in_escrow()
                            └─→ Order(PAYMENT_CONFIRMED)
                                └─→ Wallet.escrow_balance += amount

5. DELIVERY CONFIRMATION
   Seller → API (Authorization: Bearer {accessToken}) → OTPDelivery.verify()
            ├─→ Order(SHIPPED → DELIVERED)
            └─→ EscrowService.release_funds_to_seller()
                ├─→ Calculate release_fee
                ├─→ Transaction(ESCROW_RELEASE)
                ├─→ Wallet.escrow_balance -= amount
                ├─→ Wallet.available_balance += (amount - fee)
                └─→ Order(COMPLETED)

6. LOGOUT
   User → POST /auth/logout (sends access_token or refresh_token)
      ↓
   Backend revokes both tokens:
   - access_token added to Redis blacklist
   - refresh_token added to Redis blacklist
   - TTL = time until token natural expiry
      ↓
   Frontend clears:
   - localStorage (Zustand)
   - Memory state
   - Auth cookie
      ↓
   Token can't be reused (blacklist checked on each API call)

7. DISPUTE SCENARIO
   User → API → DisputeService.create_dispute()
         ├─→ Dispute(PENDING)
         ├─→ FraudDetectionService.analyze_dispute()
         └─→ Notify admins (SMS)
         
   Admin 1 → API → DisputeService.resolve_dispute()
            ├─→ Dispute(UNDER_REVIEW)
            └─→ Request evidence (buyer/seller)
   
   Admin 2 → API → DisputeService.approve()
            ├─→ admin_approvals_received = 2
            ├─→ Execute resolution
            └─→ Dispute(RESOLVED_*)
                ├─→ EscrowService.refund_buyer() OR
                └─→ EscrowService.release_funds_to_seller()
```

---

## TOKEN MANAGEMENT

### Token Lifecycle

```
CREATION
   ↓
┌─────────────────────────────────────┐
│ create_access_token(user_id, role)  │
│ {                                   │
│   "sub": "user_id",                │
│   "role": "user",                  │
│   "exp": datetime(now + 30min),    │
│   "type": "access",                │
│   "jti": "unique_id"               │ ← Unique per token
│ }                                   │
│ Sign with: HS256(JWT_SECRET_KEY)   │
└────────┬────────────────────────────┘
         │
STORAGE
   ↓
┌─────────────────────────────────────┐
│ Frontend:                           │
│ - localStorage (persisted)         │
│ - Memory (useAuthStore)            │
│ - Cookie (HttpOnly)                │
│                                     │
│ Backend:                            │
│ - Redis blacklist (when revoked)   │
│ - Database audit log               │
└────────┬────────────────────────────┘
         │
USAGE
   ↓
┌─────────────────────────────────────┐
│ Every API call:                     │
│ Authorization: Bearer {access_token}│
│                                     │
│ Backend validates:                  │
│ 1. Verify signature (HS256)         │
│ 2. Check expiry (exp claim)         │
│ 3. Check revocation (Redis lookup)  │
│ 4. Extract user info (sub, role)    │
└────────┬────────────────────────────┘
         │
REFRESH
   ↓
┌─────────────────────────────────────┐
│ Frontend scheduled (1 min before exp)│
│ POST /auth/refresh                  │
│ { refresh_token: "..." }            │
│                                     │
│ Backend:                            │
│ 1. Validate refresh_token signature │
│ 2. Check type == "refresh"          │
│ 3. Check NOT revoked                │
│ 4. Issue new access_token           │
│ 5. Issue new refresh_token          │
│ 6. Revoke old refresh_token         │
└────────┬────────────────────────────┘
         │
LOGOUT
   ↓
┌─────────────────────────────────────┐
│ POST /auth/logout                   │
│ { refresh_token: "..." }            │
│                                     │
│ Backend:                            │
│ 1. Extract both tokens (if present) │
│ 2. Add to Redis blacklist           │
│ 3. Set TTL = token expiry time      │
│ 4. Return success                   │
│                                     │
│ Frontend:                           │
│ 1. Clear localStorage               │
│ 2. Clear memory (Zustand)           │
│ 3. Clear cookie                     │
│ 4. Redirect to login                │
└────────┬────────────────────────────┘
         │
EXPIRY/CLEANUP
   ↓
   After token natural expiry:
   - Token unusable (exp check fails)
   - Redis blacklist TTL expires
   - Entry auto-deleted
```

### Token Revocation (Redis Blacklist)

```
On LOGOUT or REFRESH:
   
   1. Extract token jti claim
   2. Hash token with SHA256
   3. Store in Redis:
      Key:   revoked_token:{hash}
      Value: {"revoked": true}
      TTL:   seconds_until_token_expires
   
   On API call:
   
   1. Validate JWT signature
   2. Check if token in blacklist
      await is_token_revoked(token)
      ↓
      hash_token = SHA256(token)
      record = await redis.get(f"revoked_token:{hash}")
      return bool(record)
   
   3. If revoked → raise UnauthorizedError
   4. If valid → process request
   
   Automatic cleanup:
   
   - Redis TTL expires = key deleted
   - No manual cleanup needed
   - Efficient memory usage
```

---

## AUTHENTICATION FLOW

```
┌──────────────┐
│  Frontend    │
└────────┬─────┘
         │
         │ POST /auth/login
         │ { phone_number, password }
         ▼
┌─────────────────────────────────────┐
│ Backend Auth Service                │
│ 1. Validate Ghana phone format      │
│ 2. Find user by phone               │
│ 3. Check account not locked         │
│ 4. Verify bcrypt password           │
│ 5. Reset login_attempts to 0        │
│ 6. Update last_login_at             │
└────────┬────────────────────────────┘
         │
         │ On wrong password:
         │ - Increment login_attempts
         │ - After 5 fails: lock 30 min
         │
         │ Success:
         │ - Generate access_token (30min)
         │ - Generate refresh_token (7day)
         │ - Return both
         ▼
┌──────────────────────────────────┐
│ Frontend Zustand Auth Store      │
│                                  │
│ setSession({                     │
│   accessToken,    // 30min       │
│   refreshToken,   // 7days       │
│   user: {...}                    │
│ })                               │
│                                  │
│ → Persist to localStorage        │
│ → Schedule auto-refresh          │
└───────────┬──────────────────────┘
            │
            │ On subsequent API calls:
            │
            ▼
┌────────────────────────────────────┐
│ Attach Authorization Header        │
│                                    │
│ Authorization: Bearer {accessToken}│
└────────┬───────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Backend API Middleware               │
│ 1. Extract token from header         │
│ 2. Decode JWT (verify signature)     │
│ 3. Check token expiry                │
│ 4. Check token revocation (Redis)    │
│ 5. Check account status              │
│ 6. Fetch user from database          │
│ 7. Inject into request context       │
└──────────┬───────────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│ Endpoint Handler               │
│ @router.get("/orders")         │
│ async def list_orders(         │
│   current_user: User = ...     │ ◄── Dependency injection
│ ):                             │
│   # current_user is authenticated
│   # and not revoked
└────────────────────────────────┘

Auto-refresh (every 1 min before expiry):
   
   frontend scheduled_refresh():
       1. Check accessToken expiry (1 min before)
       2. Call POST /auth/refresh
       3. Send { refresh_token }
       4. Backend validates & returns new pair
       5. Frontend updates both tokens
       6. Reschedule next refresh
```

---

## RATE LIMITING

```
Request arrives
    ↓
┌────────────────────────────────────────┐
│ RateLimitMiddleware                    │
│ Identify client:                       │
│ 1. User ID (if authenticated)          │
│ 2. X-Forwarded-For (if from proxy)     │
│ 3. Direct IP (fallback)                │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ RateLimiter.is_allowed(client_id)      │
│                                        │
│ Try Redis:                             │
│   - Get sorted set (sliding window)    │
│   - Remove old entries (> 60 sec old)  │
│   - Count remaining entries            │
│   - Add current timestamp              │
│   - If count >= 100: REJECT            │
│                                        │
│ If Redis fails:                        │
│   - Fall back to in-memory             │
│   - Same logic with defaultdict        │
│   - Cleanup if > 10,000 keys           │
└────────┬───────────────────────────────┘
         │
         ├─→ Allowed → Continue
         │
         └─→ Exceeded → Return 429
             "Rate limit exceeded. Maximum 100 requests
              per 60 seconds."
```

---

## DATABASE RELATIONSHIPS

```
┌──────────────┐
│    users     │
├──────────────┤
│ id (PK)      │
│ phone_number │◄───────┐
│ email        │        │
│ password     │        │ 1:1
│ role         │        │
│ kyc_status   │        │
│ fraud_score  │        │
│ is_flagged   │        │
└──────────────┘        │
      │1                │
      │                 │
      ├─ N ─────────────┘
      │  wallet (1:1 user → wallet)
      │        
      ├─ N ─────────────────┐
      │  orders             │
      │  (buyer_id)         │
      │                     │
      └─ N ───────────┐     │
         orders       │     │
        (seller_id)   │     │
                      │     │
                  ┌───▼─────▼────┐
                  │    orders    │
                  ├──────────────┤
                  │ id (PK)      │
                  │ buyer_id (FK)│───┐
                  │ seller_id(FK)│   │
                  │ order_ref    │   │
                  │ escrow_stat  │   │
                  │ product_name │   │
                  │ total_amount │   │
                  │ delivery_otp │   │
                  └──────┬───────┘   │
                         │           │
              ┌──────────┼───────┬───┘
              │          │       │
              │1      N  │       │
              │          ▼       │
          ┌───▼────────────────┐ │
          │   transactions     │ │
          ├────────────────────┤ │
          │ id                 │ │
          │ order_id (FK)  ────┘ │
          │ wallet_id (FK) ──┐   │
          │ type             │   │
          │ amount           │   │
          │ status           │   │
          └────────────────────┘  │
                                  │
          ┌───────────────────┐   │
          │   wallets         │◄──┘
          ├───────────────────┤
          │ id (PK)           │
          │ user_id (FK/uniq) │
          │ available_balance │
          │ escrow_balance    │
          │ pending_balance   │
          └───────────────────┘

          ┌────────────────────┐
          │    disputes        │
          ├────────────────────┤
          │ id (PK)            │
          │ order_id (FK)  ───┐│
          │ buyer_id (FK)     ││
          │ seller_id (FK)    ││
          │ status             ││
          │ evidence_urls      ││
          │ admin_approvals    ││
          └────────────────────┘│
                                │
                        (1:1 with order)
```

---

## SECURITY ARCHITECTURE

```
┌────────────────────────────────────────────────┐
│            SECURITY LAYERS                     │
└────────────────────────────────────────────────┘

Layer 1: HTTPS/TLS
   - All traffic encrypted (TLS 1.3)
   - Certificate validation
   - HSTS headers

Layer 2: AUTHENTICATION
   - JWT with signature verification
   - Unique jti per token
   - Token expiry enforcement
   - Password bcrypt hashing

Layer 3: AUTHORIZATION
   - Role-based access control (USER, ADMIN, SUPER_ADMIN)
   - Endpoint guards via Depends()
   - Row-level security checks

Layer 4: DATA PROTECTION
   - Row-level database locks
   - Foreign key constraints
   - Check constraints (positive balances)
   - Timestamp timezone safety

Layer 5: TOKEN MANAGEMENT
   - Token revocation (Redis blacklist)
   - Automatic TTL cleanup
   - Refresh token rotation
   - Logout revocation

Layer 6: RATE LIMITING
   - 100 requests/min per IP/user
   - Graceful fallback to in-memory
   - IP-based and user-based tracking

Layer 7: FRAUD DETECTION
   - Risk scoring (0-100)
   - Auto-flagging users
   - Context-aware analysis
   - Manual review for flagged payments

Layer 8: AUDIT LOGGING
   - Admin action tracking
   - Transaction immutability
   - User activity logging
```

---

**Status**: Production-ready ✅

All critical fixes applied. Token system working properly.
Token refresh and logout endpoints operational.

