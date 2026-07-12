/**
 * UI-facing recording states for the Practice screen.
 *
 * This is intentionally a subset of the full state machine described in
 * docs/decisions/001-audio-recording-module-architecture.md. That design
 * also defines `requesting_permission` and `error` states, which only
 * make sense once real microphone capture exists. Sprint 2.1 builds the
 * UI shell only (no MediaRecorder, no getUserMedia), so those two states
 * are deferred until the real `useAudioRecorder` hook replaces
 * `useRecordingUIState` in a later sprint.
 */
export type RecordingStatus = "idle" | "recording" | "paused" | "stopped";
