export type SsePayload = Record<string, any>;

const extractErrorMessage = async (response: Response) => {
  const fallbackMessage = `请求失败 (${response.status})`;
  const contentType = response.headers.get('content-type') || '';

  try {
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return data?.detail || data?.message || data?.error || fallbackMessage;
    }

    const text = await response.text();
    if (!text) {
      return fallbackMessage;
    }

    try {
      const data = JSON.parse(text);
      return data?.detail || data?.message || data?.error || fallbackMessage;
    } catch {
      return text;
    }
  } catch {
    return fallbackMessage;
  }
};

const processSseLine = (
  rawLine: string,
  onPayload: (payload: SsePayload) => void,
) => {
  const line = rawLine.trim();
  if (!line.startsWith('data:')) {
    return false;
  }

  const data = line.slice(5).trim();
  if (!data) {
    return false;
  }
  if (data === '[DONE]') {
    return true;
  }

  try {
    onPayload(JSON.parse(data));
  } catch {
    // 忽略不完整的行，等待后续 buffer 拼接
  }
  return false;
};

export const consumeSseStream = async (
  response: Response,
  onPayload: (payload: SsePayload) => void,
  options?: {
    shouldPause?: () => boolean;
    isStopped?: () => boolean;
  },
) => {
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('无法读取响应流');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let sawDone = false;
  const waitIfPaused = async () => {
    while (options?.shouldPause?.()) {
      if (options?.isStopped?.()) {
        throw new DOMException('请求已停止', 'AbortError');
      }
      await new Promise(resolve => window.setTimeout(resolve, 160));
    }
  };

  while (true) {
    if (options?.isStopped?.()) {
      throw new DOMException('请求已停止', 'AbortError');
    }
    await waitIfPaused();
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      await waitIfPaused();
      if (options?.isStopped?.()) {
        throw new DOMException('请求已停止', 'AbortError');
      }
      sawDone = processSseLine(line, onPayload) || sawDone;
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    sawDone = processSseLine(buffer, onPayload) || sawDone;
  }

  if (!sawDone) {
    throw new Error('标准解析连接在后端发送完成标记前中断，可能是模型网关关闭连接、后端 worker 被终止，或浏览器网络提前结束。');
  }
};
