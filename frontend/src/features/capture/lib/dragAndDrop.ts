"use client";

import { useCallback, useState, type DragEvent } from "react";

/**
 * Bare-bones drag-and-drop handling for a single-file drop zone.
 * Deliberately not a generic multi-file/react-dropzone-style abstraction
 * — this app only ever accepts one audio file at a time (see
 * CaptureChooser), so a small hook covering exactly that case is
 * simpler to read and test than pulling in a drag-and-drop library for
 * three event handlers.
 *
 * `isDraggingOver` exists purely for visual feedback (highlighting the
 * drop zone) — tracked with dragenter/dragleave counting rather than a
 * single boolean toggle, because child elements inside the drop zone
 * fire their own dragenter/dragleave events as the pointer crosses their
 * boundaries, which would otherwise flicker the highlight on and off
 * while still dragging over the outer zone.
 */
export function useFileDropZone(onFile: (file: File) => void) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [, setDragDepth] = useState(0);

  const onDragEnter = useCallback((event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragDepth((depth) => {
      const next = depth + 1;
      setIsDraggingOver(next > 0);
      return next;
    });
  }, []);

  const onDragLeave = useCallback((event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragDepth((depth) => {
      const next = Math.max(depth - 1, 0);
      setIsDraggingOver(next > 0);
      return next;
    });
  }, []);

  const onDragOver = useCallback((event: DragEvent<HTMLElement>) => {
    // Required for onDrop to fire at all — browsers otherwise treat the
    // element as a non-drop target.
    event.preventDefault();
  }, []);

  const onDrop = useCallback(
    (event: DragEvent<HTMLElement>) => {
      event.preventDefault();
      setDragDepth(0);
      setIsDraggingOver(false);

      const file = event.dataTransfer.files?.[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  return { isDraggingOver, onDragEnter, onDragLeave, onDragOver, onDrop };
}
