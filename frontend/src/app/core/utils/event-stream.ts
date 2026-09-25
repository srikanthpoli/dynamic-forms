import { Observable } from 'rxjs';

export interface StreamEvent<T> {
  type: 'status' | 'complete' | 'error';
  data: T | { message: string };
}

export function postEventStream<T>(url: string, body: unknown): Observable<StreamEvent<T>> {
  return new Observable<StreamEvent<T>>(subscriber => {
    const controller = new AbortController();

    void (async () => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          const detail = await response.text();
          throw new Error(detail || `Streaming request failed (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
          const events = buffer.split('\n\n');
          buffer = events.pop() ?? '';
          for (const block of events) {
            const event = parseEvent<T>(block);
            if (event) subscriber.next(event);
          }
          if (done) break;
        }
        const finalEvent = parseEvent<T>(buffer);
        if (finalEvent) subscriber.next(finalEvent);
        subscriber.complete();
      } catch (error) {
        if (!controller.signal.aborted) subscriber.error(error);
      }
    })();

    return () => controller.abort();
  });
}

function parseEvent<T>(block: string): StreamEvent<T> | null {
  const eventType = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
  const data = block.match(/^data:\s*(.+)$/m)?.[1];
  if (!eventType || !data) return null;
  return { type: eventType as StreamEvent<T>['type'], data: JSON.parse(data) };
}
