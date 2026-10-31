import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/** Live JPEG frames of the agent's browser over a websocket, plus a sender for citizen input during human steps. */
export function useLiveFrames(taskId: string, token: string, running: boolean) {
  const [frame, setFrame] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (!running) return;
    let stop = false, timer: number | undefined;
    const connect = () => {
      if (stop) return;
      const sock = new WebSocket(api.liveUrl(taskId, token));
      ws.current = sock;
      sock.onmessage = (m) => { try { setFrame("data:image/jpeg;base64," + JSON.parse(m.data).frame); } catch { /* ignore */ } };
      sock.onclose = () => { ws.current = null; if (!stop) timer = window.setTimeout(connect, 1500); };
    };
    connect();
    return () => { stop = true; clearTimeout(timer); ws.current?.close(); };
  }, [taskId, token, running]);
  const send = (msg: object) => { if (ws.current?.readyState === 1) ws.current.send(JSON.stringify(msg)); };
  return { frame, send };
}
