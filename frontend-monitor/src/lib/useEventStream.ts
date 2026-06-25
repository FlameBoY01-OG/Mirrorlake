import { useEffect, useState } from "react";
import useWebSocket, { ReadyState } from "react-use-websocket";
import { WS_URL, type CdcEvent } from "./api";

export function useEventStream(max = 150) {
  const [events, setEvents] = useState<CdcEvent[]>([]);
  const { lastJsonMessage, readyState } = useWebSocket(WS_URL, {
    shouldReconnect: () => true,
    reconnectAttempts: 1000,
    reconnectInterval: 2000,
  });

  useEffect(() => {
    if (lastJsonMessage) {
      setEvents((prev) => [lastJsonMessage as CdcEvent, ...prev].slice(0, max));
    }
  }, [lastJsonMessage, max]);

  return { events, connected: readyState === ReadyState.OPEN };
}
