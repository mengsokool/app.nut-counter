export type PowerCommandResult =
  | { success: true }
  | { success: false; needsAuth: true }
  | { success: false; error: string };

export type Detection = {
  label: string;
  confidence: number;
  // All values normalized [0, 1] in the AI input frame coordinate space.
  x: number;
  y: number;
  w: number;
  h: number;
};

export type DetectionFrame = {
  seq: number;
  ts: number;
  count: number;
  processingMs: number;
  partType: string;
  detections: Detection[];
};

export type SystemStatus = {
  safeMode: boolean;
  trayPresent: boolean;
  lightOn: boolean;
  selectedPartType: string;
  count: number;
  processingMs: number;
  camera: "mock" | "ready" | "missing" | "error";
  model: "mock" | "ready" | "missing" | "error";
  gpio: "mock" | "ready" | "missing" | "error";
};

export type AppConfig = {
  gpio: {
    tray_sensor_pin: number;
    relay_pin: number;
    active_low: boolean;
    debounce_ms: number;
  };
  camera: {
    source: "auto" | "mock" | "picamera2" | "v4l2" | "avfoundation";
    device: string;
    width: number;
    height: number;
    warmup_frames: number;
    exposure_mode: string;
    flip_horizontal: boolean;
    flip_vertical: boolean;
  };
  model: {
    engine: string;
    model_path: string;
    hef_path: string;
    labels_path: string;
    inference_command: string[];
    confidence_threshold: number;
    nms_threshold: number;
  };
  counting: {
    stable_frames: number;
    timeout_ms: number;
    selected_part_type: string;
  };
  kiosk: {
    browser: string;
    url: string;
    profile_path: string;
  };
  safe_mode: boolean;
};

export type CameraSource = {
  id: string;
  source: AppConfig["camera"]["source"];
  label: string;
  detail: string;
  available: boolean;
  device: string;
};

export type DepStatus = {
  key: string;
  label: string;
  description: string;
  installed: boolean;
  apt_packages: string[];
};

export type DoctorReport = {
  ok: boolean;
  safeMode: boolean;
  platform: {
    system: string;
    machine: string;
    model: string;
  };
  aptAvailable: boolean;
  sudoNeedsPassword: boolean;
  deps: DepStatus[];
  checks: Array<{
    name: string;
    ok: boolean;
    status?: string;
    detail: string;
  }>;
};

export type FileBrowserEntry = {
  name: string;
  path: string;
  type: "directory" | "file";
  selectable: boolean;
  size: number | null;
};

export type FileBrowserResult = {
  path: string;
  parent: string;
  roots: Array<{ label: string; path: string }>;
  entries: FileBrowserEntry[];
  error: string;
};

export type ModelValidationCheck = {
  key: string;
  label: string;
  status: "ok" | "warn" | "error";
  detail: string;
};

export type ModelValidationResult = {
  ok: boolean;
  checks: ModelValidationCheck[];
};

export async function fetchStatus(): Promise<SystemStatus> {
  const response = await fetch("/api/status");
  if (!response.ok) {
    throw new Error("Failed to read system status");
  }
  return response.json();
}

export async function fetchConfig(): Promise<AppConfig> {
  const response = await fetch("/api/config");
  if (!response.ok) {
    throw new Error("Failed to read config");
  }
  return response.json();
}

export async function fetchCameraSources(): Promise<CameraSource[]> {
  const response = await fetch("/api/camera/sources");
  if (!response.ok) {
    throw new Error("Failed to scan camera sources");
  }
  const payload = (await response.json()) as { sources: CameraSource[] };
  return payload.sources;
}

export async function browseFiles(
  path: string,
  kind: "model" | "labels",
): Promise<FileBrowserResult> {
  const params = new URLSearchParams({ kind });
  if (path) params.set("path", path);
  const response = await fetch(`/api/files?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to browse files");
  }
  return response.json();
}

export async function validateModel(
  model: AppConfig["model"],
): Promise<ModelValidationResult> {
  const response = await fetch("/api/model/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error ?? "Failed to validate model");
  }
  return payload as ModelValidationResult;
}

export async function saveConfig(config: AppConfig): Promise<AppConfig> {
  const response = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error ?? "Failed to save config");
  }
  return response.json();
}

export async function fetchDoctor(): Promise<DoctorReport> {
  const response = await fetch("/api/doctor");
  if (!response.ok) {
    throw new Error("Failed to read doctor report");
  }
  return response.json();
}

export async function testLight(lightOn: boolean) {
  const response = await fetch("/api/hardware/light", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lightOn }),
  });
  if (!response.ok) {
    throw new Error("Failed to test relay");
  }
  return response.json() as Promise<{ success: boolean; lightOn: boolean }>;
}

export async function testTray(present: boolean) {
  const response = await fetch("/api/hardware/tray", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ present }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error ?? "Failed to test tray sensor");
  }
  return payload as { success: boolean } & SystemStatus;
}

export async function startCount() {
  const response = await fetch("/api/count/start", {
    method: "POST",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error ?? "Failed to start count");
  }
  return payload as Promise<{ success: true } & SystemStatus>;
}

export async function selectPartType(partType: string): Promise<SystemStatus> {
  const response = await fetch("/api/counting/part-type", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ partType }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error ?? "Failed to select part type");
  }
  return payload as SystemStatus;
}

export async function powerOff(password?: string): Promise<PowerCommandResult> {
  return postPowerCommand("/api/system/shutdown", password);
}

export async function reboot(password?: string): Promise<PowerCommandResult> {
  return postPowerCommand("/api/system/reboot", password);
}

export async function streamInstall(
  keys: string[],
  sudoPassword: string | null,
  onLine: (line: string) => void,
  onDone: () => void,
  onError: (message: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/doctor/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keys, sudoPassword }),
      signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") return;
    onError("ไม่สามารถเชื่อมต่อ backend ได้");
    return;
  }

  if (!res.ok || !res.body) {
    onError("เริ่มการติดตั้งไม่สำเร็จ");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // Parse SSE chunks separated by blank lines
      const events = buf.split("\n\n");
      buf = events.pop() ?? "";

      for (const event of events) {
        for (const raw of event.split("\n")) {
          if (!raw.startsWith("data: ")) continue;
          let content: string;
          try {
            content = JSON.parse(raw.slice(6)) as string;
          } catch {
            continue;
          }
          if (content === "__done__") {
            onDone();
            return;
          } else if (content.startsWith("__error__ ")) {
            onError(content.slice("__error__ ".length));
            return;
          } else {
            onLine(content);
          }
        }
      }
    }
  } catch (err) {
    if (err instanceof Error && err.name !== "AbortError") {
      onError("การติดตั้งถูกขัดจังหวะ");
    }
  }
}

async function postPowerCommand(
  path: string,
  password?: string,
): Promise<PowerCommandResult> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!response.ok) {
    return { success: false, error: "ไม่สามารถเชื่อมต่อ backend ได้" };
  }

  return response.json();
}
