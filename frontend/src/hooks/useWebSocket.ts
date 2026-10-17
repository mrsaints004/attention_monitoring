"use client";
import { useCallback, useEffect, useRef, useState } from "react";
interface Options { url: string; onMessage?: (data: unknown) => void; onOpen?: () => void; onClose?: () => void; autoConnect?: boolean; }
export function useWebSocket({ url, onMessage, onOpen, onClose, autoConnect = true }: Options) {
  const wsRef = useRef<WebSocket | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enabled = useRef(false);
  const [connected, setConnected] = useState(false);
  const callbacks = useRef({ onMessage, onOpen, onClose });
  useEffect(() => { callbacks.current = { onMessage, onOpen, onClose }; }, [onMessage, onOpen, onClose]);
  const connect = useCallback(function openSocket() {
    enabled.current = true;
    if (wsRef.current && wsRef.current.readyState < WebSocket.CLOSING) return;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => { setConnected(true); callbacks.current.onOpen?.(); };
    ws.onmessage = (event) => {
      let data: unknown = event.data;
      try { data = JSON.parse(event.data); } catch { /* Text message. */ }
      callbacks.current.onMessage?.(data);
    };
    ws.onclose = () => {
      setConnected(false); callbacks.current.onClose?.();
      if (enabled.current) timer.current = setTimeout(openSocket, 2000);
    };
    ws.onerror = () => ws.close();
  }, [url]);
  const disconnect = useCallback(() => {
    enabled.current = false;
    if (timer.current) clearTimeout(timer.current);
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    wsRef.current = null;
    setConnected(false);
  }, []);
  const send = useCallback((data: unknown) => { if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(data)); }, []);
  useEffect(() => { if (autoConnect) connect(); return disconnect; }, [autoConnect, connect, disconnect]);
  return { connected, send, connect, disconnect };
}
