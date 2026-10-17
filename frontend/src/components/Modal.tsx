"use client";
import { useEffect, useId, useRef } from "react";
interface ConfirmModalProps {
  open: boolean; title: string; message: string; onConfirm: () => void; onCancel: () => void;
  variant?: "danger" | "default"; confirmLabel?: string; cancelLabel?: string; confirmDisabled?: boolean;
}
export function ConfirmModal({ open, title, message, onConfirm, onCancel, variant = "default", confirmLabel = "Confirm", cancelLabel = "Cancel", confirmDisabled = false }: ConfirmModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId(); const descriptionId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus(); };
  }, [open]);
  return <dialog ref={ref} aria-labelledby={titleId} aria-describedby={descriptionId} onCancel={event => { event.preventDefault(); if (!confirmDisabled) onCancel(); }} className="m-auto w-full max-w-md rounded-xl bg-white p-6 shadow-xl backdrop:bg-black/50">
    <h2 id={titleId} className="text-lg font-semibold text-gray-900 mb-2">{title}</h2>
    <p id={descriptionId} className="text-sm text-gray-700 mb-6">{message}</p>
    <div className="flex justify-end gap-3">
      <button autoFocus disabled={confirmDisabled} onClick={onCancel} className="rounded-lg bg-gray-100 px-4 py-2 text-sm text-gray-800 disabled:opacity-50">{cancelLabel}</button>
      <button disabled={confirmDisabled} onClick={onConfirm} className={`rounded-lg px-4 py-2 text-sm text-white disabled:opacity-50 ${variant === "danger" ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>{confirmDisabled ? "Working…" : confirmLabel}</button>
    </div>
  </dialog>;
}
