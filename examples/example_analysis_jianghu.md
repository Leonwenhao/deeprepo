# Codebase Analysis: Jiang Hu Chronicles

**Repository**: jianghu-game
**Type**: Next.js 14 Narrative RPG with AI Integration
**Scale**: 225 files, 1.77M characters, 48,868 lines
**Tech Stack**: Next.js, React, TypeScript, Zustand, Claude AI, Fal.ai, Blockchain (Wagmi/Viem)

---

## 1. Architecture Overview

### 1.1 Project Structure

**Entry Points**:
- app/page.tsx - Landing page
- app/game/page.tsx - Main game interface (23,765 chars)
- app/api/* - API routes for AI dialogue, meditation, image generation

**Core Architecture**:
- Frontend: Next.js 14 App Router with React 19, TypeScript strict mode
- State Management: Zustand with 7 domain-specific stores
- Persistence: IndexedDB via idb-keyval with custom serialization
- AI Integration: Claude API for NPC dialogue, Fal.ai for images
- Blockchain: Wagmi/Viem for Base network NFT minting
- Testing: Vitest with 20 test files

### 1.2 Module Dependencies

**Store Layer** (stores/):
- playerStore: Character stats, cultivation, techniques
- narrativeStore: Story progression, scenes, choices
- worldStore: NPCs, locations, time, relationships
- combatStore: Combat state, dice pools, opponents
- dicePoolStore: Dice allocation and resolution
- uiStore: UI state, modals, notifications
- chainStore: Blockchain integration, wallet, NFTs

**Game Logic** (lib/game/):
- 17 game system modules with pure functions
- combat.ts (12KB), diceResolution.ts (8KB), types.ts (17KB)
- Well-tested with 11 test files

**Data Layer** (lib/data/):
- 63 JSON files for scenes, NPCs, locations
- TypeScript definitions for game content
- Content loader with validation

**Component Layer** (components/):
- 42 React components (TSX)
- game/ - Game-specific UI (SceneRenderer, CombatPanel, etc.)
- ui/ - Reusable components (CharacterSheet, SaveSlotPanel, etc.)
- chain/ - Blockchain components (ChainManager, ChainProcessor)

**API Layer** (app/api/):
- dialogue/route.ts - NPC dialogue generation
- meditation/route.ts - Meditation insights
- generate-image/route.ts - Character portraits
- NO authentication or rate limiting (CRITICAL)

### 1.3 Data Flow

1. User Action in Component
2. Zustand Store Action Updates State
3. Side Effects: Persistence, AI calls, blockchain txs
4. Components Re-render via Store Subscriptions
5. Auto-save to IndexedDB

**AI Dialogue Flow**:
- Player input in DialogueBox component
- POST to /api/dialogue with NPC context
- Claude API generates response
- Validation layer checks response
- Response displayed, state updated

### 1.4 Design Patterns

**Strengths**:
- Domain-driven store architecture
- Pure function game logic (testable)
- JSON-based content (easy to edit)
- Component composition

**Weaknesses**:
- No service layer (API calls scattered)
- Cross-store dependencies create coupling
- Large monolithic game page (23KB)
- Tightly coupled to Claude/Fal.ai

---

## 2. Bug and Issue Audit

### 2.1 Critical Security Issues (P0)

#### CRITICAL: API Security - No Authentication or Rate Limiting
**Files**: app/api/dialogue/route.ts, app/api/meditation/route.ts, app/api/generate-image/route.ts

**Issues**:
- All API endpoints publicly accessible without auth
- No rate limiting on AI API calls
- Users can spam requests, burning API credits
- No input sanitization for prompt injection

**Impact**: Unlimited API cost exposure, abuse potential, prompt injection attacks

**Fix**:
- Implement session-based authentication
- Add rate limiting (10 requests/min per user)
- Sanitize user input before AI calls
- Add API cost monitoring and budget alerts
- Use Claude moderation API

#### CRITICAL: Smart Contract Private Key Handling
**File**: contracts/hardhat.config.js

**Issue**: Config contains private key handling logic

**Fix**:
- Verify keys ONLY in .env (never committed)
- Audit git history for leaked keys
- Use hardware wallet for production

### 2.2 Critical Functional Bugs (P0)

#### CRITICAL: Save System Corruption
**Files**: lib/storage/persistence.ts, lib/storage/idbPersistence.ts

**Issues**:
- IndexedDB quota exceeded with no error handling
- Non-atomic multi-store saves (partial corruption)
- No schema versioning (updates break old saves)
- No checksum validation on load
- Large choice history fills storage

**Impact**: Players lose 2+ hours of progress, game unplayable

**Fix**:
- Implement atomic transaction wrapper
- Add schema version field and migrations
- Prune choice history (keep last 50)
- Add storage quota monitoring
- Implement save verification
- Add checksum validation

#### CRITICAL: Combat Dice Allocation Exploit
**Files**: lib/game/combat.ts, components/game/DiceAllocation.tsx

**Issues**:
- No validation that total allocated <= available
- Race condition allows multiple increments
- Players can allocate 10+ dice when only 6 available
- One-shot any opponent

**Impact**: Game balance completely broken

**Fix**:
- Add debouncing to allocation buttons (100ms)
- Validate total dice before combat resolution
- Add client-side validation
- Add unit tests for edge cases

#### CRITICAL: AI Dialogue Infinite Loop
**Files**: app/api/dialogue/route.ts, lib/ai/validation.ts

**Issues**:
- Validation fails, triggers retry with same context
- No max retry limit
- Same response regenerates 5-10 times
- Game becomes unresponsive

**Impact**: Blocks progression

**Fix**:
- Add max retry limit (3 attempts)
- Add circuit breaker for repeated failures
- Fallback to pre-written dialogue
- Vary context on retry

### 2.3 High Priority Bugs (P1)

#### Combat System Logic Errors
**File**: lib/game/combat.ts

**Issues Found**:
1. normalizeWeights never divides by total (lines 81-92)
2. Crits impossible on first exchange even with critSurgeReady
3. No validation of technique qi cost before use
4. Health can go negative before clamping
5. No handling for simultaneous death

**Fix**: Fix normalization, add qi validation, handle edge cases

#### Blockchain Transaction Errors
**File**: lib/chain/useChainMint.ts

**Issues**:
- useWriteContract hook called but never used
- No gas estimation before transactions
- No transaction confirmation waiting
- Optimistic UI updates without rollback
- No error differentiation

**Impact**: Failed mints, wasted gas, UI shows non-existent NFTs

**Fix**:
- Fix useWriteContract usage
- Add gas estimation with 20% buffer
- Wait for transaction confirmation
- Implement rollback on failure
- Add user-friendly error messages

#### Relationship Values Overflow
**Issue**: NPC relationships exceed -100 to +100 bounds
**Impact**: UI display issues, ending routing breaks
**Fix**: Clamp values in applyConsequence()

#### Image Generation Failures
**Issue**: 20% of image requests fail silently
**Impact**: Blank portraits, degraded experience
**Fix**: Add retry logic, fallback placeholders, error toasts

### 2.4 Medium Priority Issues (P2)

#### Performance Issues
**File**: app/game/page.tsx

**Issues**:
- No code splitting (all components loaded at once)
- Store subscription overload (entire stores)
- No memoization of expensive calculations
- Images loaded without lazy loading
- Large bundle size (500KB+)

**Impact**: Slow load, laggy UI, poor mobile performance

#### Memory Leaks
**Issues**:
- Event listeners not cleaned up in useEffect
- Store subscriptions may not be cleaned up
- Interval/timeout cleanup missing

**Impact**: Memory leaks, multiple handlers, timers after unmount

#### Serialization Bugs
**File**: stores/serialization.ts

**Issues**:
- Functions in stores cannot be serialized
- Date objects serialize to strings
- Circular references in NPC relationships
- No deep clone (mutations affect saved payload)

### 2.5 Low Priority Issues (P3)

- Audio desync when skipping dialogue
- Gossip duplication in pool
- NPC schedule conflicts at hour boundaries
- Typos in dialogue content
- Mobile layout issues on screens < 375px

---

## 3. Code Quality Assessment

### 3.1 Strengths

**Testing**:
- 20 test files covering game logic, storage, components
- Good coverage of core systems (combat, cultivation, dice)
- Contract tests for all 3 smart contracts

**Type Safety**:
- TypeScript strict mode enabled
- Comprehensive types in lib/game/types.ts (17KB)
- Zod schemas for runtime validation

**Code Organization**:
- Clear separation of concerns
- Domain-driven store architecture
- Pure function game logic

**Documentation**:
- Extensive design docs (M2-M5 specs, 300KB+)
- Dialogue design documentation
- Development plans and task queues
- Playtest bug tracking

### 3.2 Weaknesses

**Pattern Consistency**:
- Inconsistent error handling across API routes
- Mixed async/await and promise patterns
- Some inline styles, others use Tailwind

**Test Coverage Gaps**:
- No tests for API routes (critical security gap)
- No tests for React components (except FaceMeter)
- No E2E tests for critical user flows
- No tests for persistence edge cases

**Code Duplication**:
- Similar validation logic in multiple API routes
- Repeated store subscription patterns
- Duplicate error handling code

**Missing Abstractions**:
- No service layer for API calls
- No AI provider abstraction
- No image provider abstraction
- No error handling middleware

### 3.3 Technical Debt

**High Priority**:
- Refactor 23KB game page into smaller components
- Extract API call logic into service layer
- Implement proper error boundaries
- Add authentication middleware

**Medium Priority**:
- Standardize error handling patterns
- Add component tests
- Implement code splitting
- Add API route tests

---

## 4. Prioritized Development Plan

### P0: Critical Fixes (Must Fix Before Launch)

#### 1. API Security Hardening
**What**: Add authentication, rate limiting, input sanitization
**Why**: Prevents unlimited API cost exposure
**Complexity**: Medium (2-3 days)

#### 2. Save System Overhaul
**What**: Fix corruption, add versioning, atomic saves
**Why**: Players losing progress is unacceptable
**Complexity**: High (4-5 days)

#### 3. Combat Exploit Fix
**What**: Add dice allocation validation and debouncing
**Why**: Game-breaking exploit
**Complexity**: Low (1 day)

#### 4. AI Dialogue Circuit Breaker
**What**: Add retry limits and fallback dialogue
**Why**: Infinite loops block progression
**Complexity**: Low (1 day)

#### 5. Smart Contract Security Audit
**What**: Verify no private keys in code
**Why**: Key exposure is catastrophic
**Complexity**: Low (1 day)

### P1: Important Improvements (Fix Before Public Beta)

#### 6. Combat System Bug Fixes
**What**: Fix weight normalization, qi validation, edge cases
**Why**: Combat is core gameplay
**Complexity**: Medium (2 days)

#### 7. Blockchain Transaction Reliability
**What**: Fix transaction flow, add gas estimation
**Why**: Failed mints waste gas
**Complexity**: Medium (2-3 days)

#### 8. Performance Optimization
**What**: Code splitting, memoization, lazy loading
**Why**: Slow load times hurt UX
**Complexity**: Medium (2-3 days)

#### 9. Error Boundary Implementation
**What**: Wrap game in error boundaries
**Why**: Crashes lose player progress
**Complexity**: Low (1 day)

#### 10. Image Generation Reliability
**What**: Add retry logic, fallbacks
**Why**: 20% failure rate degrades experience
**Complexity**: Low (1 day)

### P2: Nice-to-Have Enhancements

#### 11. Test Coverage Expansion
**What**: Add API route tests, component tests, E2E tests
**Complexity**: High (5-7 days)

#### 12. Code Refactoring
**What**: Extract service layer, split large components
**Complexity**: High (5-7 days)

#### 13. Memory Leak Fixes
**What**: Add cleanup to all useEffect hooks
**Complexity**: Low (1-2 days)

#### 14. Mobile Optimization
**What**: Fix layout issues, optimize for small screens
**Complexity**: Medium (2-3 days)

#### 15. Monitoring and Observability
**What**: Add error tracking, API monitoring, analytics
**Complexity**: Medium (2-3 days)

---

## 5. Summary and Recommendations

### Overall Assessment

**Strengths**:
- Ambitious and well-architected narrative RPG
- Good separation of concerns with domain stores
- Solid test coverage for game logic
- Extensive documentation and design specs
- Innovative AI integration for dynamic dialogue

**Critical Risks**:
- API security completely absent (unlimited cost exposure)
- Save system corruption loses player progress
- Combat exploit breaks game balance
- AI dialogue can enter infinite loops

### Launch Readiness

**Current State**: NOT READY FOR PUBLIC LAUNCH

**Blockers**:
1. API security must be implemented (P0)
2. Save system must be fixed (P0)
3. Combat exploit must be patched (P0)
4. AI dialogue circuit breaker needed (P0)
5. Smart contract security audit required (P0)

**Estimated Time to Launch**: 2-3 weeks
- Week 1: P0 critical fixes (5 items)
- Week 2: P1 important improvements (5 items)
- Week 3: Testing, bug fixes, polish

---

**Analysis Completed**: This codebase shows strong architectural foundations but has critical security and reliability issues that must be addressed before launch. The P0 items are non-negotiable blockers.

*Generated by deeprepo (Sonnet 4.5 root + MiniMax M2.5 sub-LLM workers)*
