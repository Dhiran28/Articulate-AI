import { getApiBaseUrl } from "@/lib/apiConfig";
import type { CommunicationReport } from "@/features/results/types";

interface BackendErrorDetail {
  error: string;
  message: string;
}

/**
 * Thrown by analyzeAudio with the backend's own classified reason (see
 * docs/api.md's error table — unsupported_format, transcript_empty,
 * no_provider_configured, llm_timeout, etc.) and friendly message, or a
 * client-side reason ("network_error" / "timeout") if the request never
 * completed. Mirrors AudioUploadError (features/audio-upload/lib/uploadClient.ts)
 * — same shape, same reasoning, applied to the one-call analysis
 * endpoint instead of the plain upload endpoint.
 */
export class AnalyzeError extends Error {
  readonly reason: string;

  constructor(reason: string, message: string) {
    super(message);
    this.name = "AnalyzeError";
    this.reason = reason;
  }
}

interface AnalyzeAudioOptions {
  /** Called with 0-100 as the upload progresses. Never reaches 100 from the server's processing time — see the comment at the call site below. */
  onUploadProgress?: (percent: number) => void;
  /** Aborts the in-flight request when this signal fires. */
  signal?: AbortSignal;
}

/**
 * POSTs one audio file to POST /api/analyze and returns the parsed
 * CommunicationReport (see backend/app/reporting/models.py, ADR 004).
 *
 * Built on XMLHttpRequest rather than `fetch`, specifically so real
 * upload progress can be reported: the Fetch API has no supported way
 * to observe request-body upload progress in a browser (only response
 * download progress, via a ReadableStream reader) — XHR's
 * `upload.onprogress` is the only standard mechanism for this. Given
 * this app's Analysis feature explicitly requires an upload-progress
 * indicator, XHR is the deliberate choice here, isolated to this one
 * file — every other API call in this codebase (uploadClient.ts) still
 * uses plain `fetch`, since none of the others need upload progress.
 *
 * Progress only covers the upload itself, not the backend's subsequent
 * work (transcription, then up to two LLM calls — ADR 004 §2). There is
 * no server-sent progress for that part of the pipeline; the caller
 * (useAnalyzeMutation) is expected to show an indeterminate "processing"
 * state once the upload reaches 100%, not imply that the number
 * reflects total request completion.
 */
export function analyzeAudio(file: File, options: AnalyzeAudioOptions = {}): Promise<CommunicationReport> {
  const { onUploadProgress, signal } = options;

  return new Promise<CommunicationReport>((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${getApiBaseUrl()}/api/analyze`);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onUploadProgress) return;
      onUploadProgress(Math.round((event.loaded / event.total) * 100));
    };

    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as CommunicationReport);
        return;
      }

      const detail = (body as { detail?: BackendErrorDetail } | null)?.detail;
      reject(
        new AnalyzeError(
          detail?.error ?? "unknown_error",
          detail?.message ?? "Something went wrong analyzing this recording. Please try again."
        )
      );
    };

    xhr.onerror = () => {
      reject(new AnalyzeError("network_error", "Couldn't reach the server. Check your connection and try again."));
    };

    xhr.ontimeout = () => {
      reject(new AnalyzeError("timeout", "The request took too long and timed out. Please try again."));
    };

    xhr.onabort = () => {
      reject(new AnalyzeError("aborted", "The request was cancelled."));
    };

    // Generous: transcription plus up to two LLM calls can legitimately
    // take a while (ADR 004 §2, docs/deployment.md's latency guidance).
    // A hung request still needs *some* ceiling so a user is never
    // stuck on an infinite spinner.
    xhr.timeout = 120_000;

    if (signal) {
      if (signal.aborted) {
        xhr.abort();
      } else {
        signal.addEventListener("abort", () => xhr.abort());
      }
    }

    xhr.send(formData);
  });
}
