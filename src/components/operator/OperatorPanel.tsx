import {
  Activity,
  Box,
  Camera,
  CheckCircle2,
  File,
  FlaskConical,
  FolderOpen,
  LoaderCircle,
  RefreshCw,
  Save,
  Settings,
  TriangleAlert,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  type AppConfig,
  type CameraSource,
  type DepStatus,
  type DoctorReport,
  type FileBrowserResult,
  type ModelValidationResult,
  type SystemStatus,
  browseFiles,
  fetchCameraSources,
  fetchConfig,
  fetchDoctor,
  fetchStatus,
  saveConfig,
  startCount,
  streamInstall,
  testLight,
  testTray,
  validateModel,
} from "../../api/client";

type OperatorPanelProps = {
  onClose: () => void;
};

type TabId = "status" | "config" | "test";

const OPERATOR_TABS: Array<{
  id: TabId;
  label: string;
  detail: string;
  icon: React.ReactNode;
}> = [
  {
    id: "status",
    label: "สถานะระบบ",
    detail: "ตรวจความพร้อม",
    icon: <Activity className="h-5 w-5" />,
  },
  {
    id: "config",
    label: "ตั้งค่าเครื่อง",
    detail: "กล้อง GPIO โมเดล",
    icon: <Settings className="h-5 w-5" />,
  },
  {
    id: "test",
    label: "ทดสอบอุปกรณ์",
    detail: "ไฟ ถาด การนับ",
    icon: <FlaskConical className="h-5 w-5" />,
  },
];

export default function OperatorPanel({ onClose }: OperatorPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>("status");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [doctor, setDoctor] = useState<DoctorReport | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedConfig, setSavedConfig] = useState<AppConfig | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  const isDirty =
    config !== null &&
    savedConfig !== null &&
    JSON.stringify(config) !== JSON.stringify(savedConfig);

  async function refresh() {
    setError("");
    const [nextStatus, nextDoctor, nextConfig] = await Promise.all([
      fetchStatus(),
      fetchDoctor(),
      fetchConfig(),
    ]);
    setStatus(nextStatus);
    setDoctor(nextDoctor);
    setConfig(nextConfig);
  }

  useEffect(() => {
    let isMounted = true;

    async function loadInitialState() {
      try {
        const [nextStatus, nextDoctor, nextConfig] = await Promise.all([
          fetchStatus(),
          fetchDoctor(),
          fetchConfig(),
        ]);
        if (!isMounted) return;
        setStatus(nextStatus);
        setDoctor(nextDoctor);
        setConfig(nextConfig);
        setSavedConfig(nextConfig);
      } catch (caught) {
        if (!isMounted) return;
        setError(
          caught instanceof Error ? caught.message : "โหลดข้อมูลไม่สำเร็จ",
        );
      }
    }

    void loadInitialState();

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSave() {
    if (!config || !isDirty) return;
    const cameraChanged =
      savedConfig !== null &&
      JSON.stringify(config.camera) !== JSON.stringify(savedConfig.camera);
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      const saved = await saveConfig(config);
      setConfig(saved);
      setSavedConfig(saved);
      setJustSaved(true);
      if (cameraChanged) {
        window.dispatchEvent(new Event("nut-counter-camera-refresh"));
      }
      setTimeout(() => setJustSaved(false), 1000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "บันทึกไม่สำเร็จ");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLightTest(lightOn: boolean) {
    setIsBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await testLight(lightOn);
      setMessage(result.lightOn ? "เปิด relay แล้ว" : "ปิด relay แล้ว");
      await refresh();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "ทดสอบ relay ไม่สำเร็จ",
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCountTest() {
    setIsBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await startCount();
      setStatus(result);
      setMessage(`นับทดสอบสำเร็จ: ${result.count} ชิ้น`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "ทดสอบนับไม่สำเร็จ");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleTrayTest(present: boolean) {
    setIsBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await testTray(present);
      setStatus(result);
      setMessage(present ? "จำลองวางถาดแล้ว" : "จำลองถอดถาดแล้ว");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "ทดสอบถาดไม่สำเร็จ");
    } finally {
      setIsBusy(false);
    }
  }

  const activeTabMeta =
    OPERATOR_TABS.find((tab) => tab.id === activeTab) ?? OPERATOR_TABS[0];

  return (
    <div className="animate-fade-in fixed inset-0 z-[60] bg-[color:oklch(0.14_0.006_95_/_0.76)] p-3">
      <div className="animate-panel-lift mx-auto grid h-full min-h-0 max-w-6xl grid-cols-[15rem_minmax(0,1fr)] overflow-hidden rounded-[0.25rem] border-2 border-[var(--machine-line)] bg-[var(--machine-panel)] text-[var(--machine-ink)] shadow-2xl">
        <aside className="flex min-h-0 min-w-0 flex-col border-r border-[var(--machine-line)] bg-[var(--machine-panel-strong)]">
          <header className="flex min-h-20 shrink-0 flex-col justify-center border-b border-[var(--machine-line)] px-5">
            <div className="text-[11px] font-black uppercase tracking-[0.28em] text-[var(--machine-muted)]">
              operator
            </div>
            <h2 className="mt-1 text-xl font-black leading-tight">
              ตั้งค่าเครื่อง
            </h2>
          </header>

          <nav className="grid gap-2 p-3">
            {OPERATOR_TABS.map((tab) => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                icon={tab.icon}
                label={tab.label}
                detail={tab.detail}
                onClick={() => setActiveTab(tab.id)}
              />
            ))}
          </nav>

          <div className="mt-auto border-t border-[var(--machine-line)] p-3">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isBusy || isSaving || !isDirty || justSaved}
              className={`flex min-h-12 w-full items-center justify-center gap-2 rounded-[0.2rem] px-4 text-sm font-black transition-colors duration-150 ${
                justSaved
                  ? "bg-[oklch(0.47_0.13_127)] text-[oklch(0.96_0.009_85)]"
                  : isDirty
                    ? "bg-[var(--machine-ink)] text-[var(--machine-light)]"
                    : "border border-[var(--machine-line)] bg-[var(--machine-panel)] text-[var(--machine-muted)]"
              } ${isBusy || isSaving ? "opacity-50" : ""}`}
            >
              {isSaving ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {isSaving ? "กำลังบันทึก" : justSaved ? "บันทึกสำเร็จ" : "บันทึก"}
            </button>
            <div className="mt-2 min-h-5 text-center text-xs font-bold text-[var(--machine-muted)]">
              {isDirty ? "มีการเปลี่ยนแปลงที่ยังไม่บันทึก" : "ค่าปัจจุบันถูกบันทึกแล้ว"}
            </div>
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col bg-[var(--machine-panel)]">
          <header className="flex min-h-20 shrink-0 items-center justify-between border-b border-[var(--machine-line)] px-6">
            <div className="min-w-0">
              <div className="text-[11px] font-black uppercase tracking-[0.28em] text-[var(--machine-muted)]">
                {activeTabMeta.detail}
              </div>
              <h3 className="mt-1 text-xl font-black leading-tight">
                {activeTabMeta.label}
              </h3>
            </div>
            <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void refresh()}
              className="flex h-11 w-11 items-center justify-center rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-panel-strong)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-pressed)]"
              aria-label="รีเฟรช"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex h-11 w-11 items-center justify-center rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-panel-strong)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-pressed)]"
              aria-label="ปิด"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main
          key={activeTab}
          className="animate-fade-in min-h-0 min-w-0 flex-1 overflow-y-auto px-6 py-5"
        >
          {(message || error) && (
            <div
              className={`mb-5 rounded-[0.2rem] border px-4 py-3 text-sm font-semibold ${
                error
                  ? "border-[#dfc0b6] bg-[var(--machine-danger-soft)] text-[var(--machine-danger)]"
                  : "border-[#bfd49b] bg-[#edf7df] text-[#476119]"
              }`}
            >
              {error || message}
            </div>
          )}

          {activeTab === "status" && (
            <StatusTab status={status} doctor={doctor} onRefresh={refresh} />
          )}
          {activeTab === "config" && config && (
            <ConfigTab config={config} onChange={setConfig} />
          )}
          {activeTab === "test" && (
            <TestTab
              isBusy={isBusy}
              onLightTest={handleLightTest}
              onCountTest={handleCountTest}
              onTrayTest={handleTrayTest}
            />
          )}
        </main>
        </section>
      </div>
    </div>
  );
}

function StatusTab({
  status,
  doctor,
  onRefresh,
}: {
  status: SystemStatus | null;
  doctor: DoctorReport | null;
  onRefresh: () => Promise<void>;
}) {
  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-4 overflow-hidden rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)]">
        <MetricCell
          label="ถาด"
          value={status?.trayPresent ? "มีถาด" : "ไม่มีถาด"}
        />
        <MetricCell label="ไฟ" value={status?.lightOn ? "เปิด" : "ปิด"} />
        <MetricCell label="นับได้" value={status ? `${status.count}` : "-"} />
        <MetricCell
          label="เวลา"
          value={status ? `${status.processingMs} ms` : "-"}
          last
        />
      </div>

      <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)]">
        <header className="flex min-h-12 items-center gap-2 border-b border-[var(--machine-line)] px-4 font-black">
          <Activity className="h-5 w-5" />
          Doctor
        </header>
        <div className="px-4">
          {doctor?.checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center justify-between gap-4 border-b border-[var(--machine-line)] py-3 last:border-b-0"
            >
              <div>
                <div className="font-bold">{check.name}</div>
                <div className="text-sm text-[var(--machine-muted)]">
                  {check.detail}
                </div>
              </div>
              {check.ok ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 text-[#58751c]" />
              ) : (
                <XCircle className="h-5 w-5 shrink-0 text-[var(--machine-danger)]" />
              )}
            </div>
          ))}
        </div>
      </section>

      {doctor && (
        <DepsSection
          deps={doctor.deps}
          sudoNeedsPassword={doctor.sudoNeedsPassword}
          aptAvailable={doctor.aptAvailable}
          onRefresh={onRefresh}
        />
      )}
    </div>
  );
}

type InstallPhase = "idle" | "password" | "running" | "done" | "error";

function DepsSection({
  deps,
  sudoNeedsPassword,
  aptAvailable,
  onRefresh,
}: {
  deps: DepStatus[];
  sudoNeedsPassword: boolean;
  aptAvailable: boolean;
  onRefresh: () => Promise<void>;
}) {
  const missing = deps.filter((d) => !d.installed);
  const [phase, setPhase] = useState<InstallPhase>("idle");
  const [targetKeys, setTargetKeys] = useState<string[]>([]);
  const [sudoPassword, setSudoPassword] = useState("");
  const [lines, setLines] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [lines]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  if (missing.length === 0) return null;

  function beginInstall(keys: string[], password: string | null) {
    setPhase("running");
    setLines([]);
    setErrorMsg("");
    const ac = new AbortController();
    abortRef.current = ac;
    void streamInstall(
      keys,
      password,
      (line) => setLines((prev) => [...prev, line]),
      () => {
        setPhase("done");
        void onRefresh();
      },
      (msg) => {
        setPhase("error");
        setErrorMsg(msg);
      },
      ac.signal,
    );
  }

  function handleInstallClick(keys: string[]) {
    setTargetKeys(keys);
    setSudoPassword("");
    if (sudoNeedsPassword) {
      setPhase("password");
    } else {
      beginInstall(keys, null);
    }
  }

  function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    beginInstall(targetKeys, sudoPassword);
  }

  function handleReset() {
    abortRef.current?.abort();
    setPhase("idle");
    setLines([]);
    setSudoPassword("");
  }

  return (
    <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)]">
      <header className="flex min-h-12 items-center gap-2 border-b border-[var(--machine-line)] px-4 font-black">
        <Zap className="h-5 w-5" />
        Dependencies
      </header>

      {phase === "idle" && (
        <div className="px-4">
          {!aptAvailable && (
            <p className="py-3 text-sm text-[var(--machine-muted)]">
              apt-get ไม่พบในระบบนี้ กรุณาติดตั้ง package เหล่านี้ด้วยตนเอง
            </p>
          )}
          {missing.map((dep) => (
            <div
              key={dep.key}
              className="flex items-center justify-between gap-4 border-b border-[var(--machine-line)] py-3 last:border-b-0"
            >
              <div>
                <div className="font-bold">{dep.label}</div>
                <div className="text-sm text-[var(--machine-muted)]">
                  {dep.description}
                </div>
                {!aptAvailable && (
                  <div className="mt-0.5 font-mono text-xs text-[var(--machine-muted)]">
                    apt install {dep.apt_packages.join(" ")}
                  </div>
                )}
              </div>
              {aptAvailable ? (
                <button
                  type="button"
                  onClick={() => handleInstallClick([dep.key])}
                  className="shrink-0 rounded-[0.2rem] bg-[var(--machine-ink)] px-3 py-1.5 text-xs font-bold text-[var(--machine-light)] transition-opacity hover:opacity-80"
                >
                  ติดตั้ง
                </button>
              ) : (
                <XCircle className="h-5 w-5 shrink-0 text-[var(--machine-danger)]" />
              )}
            </div>
          ))}
        </div>
      )}

      {phase === "password" && (
        <form onSubmit={handlePasswordSubmit} className="p-4">
          <p className="mb-3 text-sm text-[var(--machine-muted)]">
            ระบบต้องการรหัส sudo เพื่อติดตั้ง{" "}
            <span className="font-bold text-[var(--machine-ink)]">
              {targetKeys.join(", ")}
            </span>
          </p>
          <input
            type="password"
            placeholder="รหัสผ่าน sudo"
            autoComplete="off"
            autoFocus
            value={sudoPassword}
            onChange={(e) => setSudoPassword(e.target.value)}
            className="mb-3 w-full rounded-[0.2rem] border border-[var(--machine-line)] bg-white px-3 py-2 text-sm text-[var(--machine-ink)] outline-none focus:border-[var(--machine-ink)]"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!sudoPassword}
              className="rounded-[0.2rem] bg-[var(--machine-ink)] px-4 py-2 text-sm font-bold text-[var(--machine-light)] disabled:opacity-40"
            >
              ติดตั้ง
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="rounded-[0.2rem] px-4 py-2 text-sm font-bold text-[var(--machine-muted)] hover:bg-[var(--machine-panel-strong)]"
            >
              ยกเลิก
            </button>
          </div>
        </form>
      )}

      {(phase === "running" || phase === "done" || phase === "error") && (
        <div className="p-4">
          <div
            ref={logRef}
            className="mb-3 max-h-52 overflow-y-auto rounded-[0.2rem] bg-[var(--machine-display)] p-3"
            style={{ fontFamily: "var(--font-machine-mono)" }}
          >
            {lines.length === 0 && phase === "running" && (
              <span className="text-xs text-[var(--machine-display-label)]">
                กำลังติดตั้ง...
              </span>
            )}
            {lines.map((line, i) => (
              <div
                key={i}
                className="text-xs leading-relaxed text-[var(--machine-light)]"
              >
                {line}
              </div>
            ))}
          </div>

          {phase === "done" && (
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-[#476119]">
              <CheckCircle2 className="h-4 w-4" />
              ติดตั้งสำเร็จ
            </div>
          )}
          {phase === "error" && (
            <div className="mb-3 rounded-[0.2rem] border border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-3 py-2 text-sm font-semibold text-[var(--machine-danger)]">
              {errorMsg}
            </div>
          )}

          {phase !== "running" && (
            <button
              type="button"
              onClick={handleReset}
              className="rounded-[0.2rem] px-4 py-2 text-sm font-bold text-[var(--machine-muted)] hover:bg-[var(--machine-panel-strong)]"
            >
              {phase === "done" ? "ปิด" : "ลองใหม่"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function ConfigTab({
  config,
  onChange,
}: {
  config: AppConfig;
  onChange: (config: AppConfig) => void;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)] gap-5">
      <div className="grid gap-5">
        <ConfigSection title="Camera" detail="แหล่งภาพและการกลับภาพ">
          <CameraSourceField
            value={config.camera.source ?? "auto"}
            device={config.camera.device ?? ""}
            onChange={(source, device) =>
              onChange({ ...config, camera: { ...config.camera, source, device } })
            }
          />
          <div className="grid grid-cols-[minmax(0,1fr)_14rem] gap-4">
            <PreviewQualityField
              width={config.camera.width}
              height={config.camera.height}
              onChange={(width, height) =>
                onChange({ ...config, camera: { ...config.camera, width, height } })
              }
            />
            <div className="grid content-start gap-3">
              <StepperField
                label="Warmup frames"
                value={config.camera.warmup_frames}
                min={0}
                max={30}
                smallStep={1}
                largeStep={5}
                onChange={(value) =>
                  onChange({
                    ...config,
                    camera: { ...config.camera, warmup_frames: value },
                  })
                }
              />
              <div className="grid grid-cols-2 gap-2">
                <ToggleField
                  label="Flip H"
                  checked={config.camera.flip_horizontal}
                  onChange={(checked) =>
                    onChange({
                      ...config,
                      camera: { ...config.camera, flip_horizontal: checked },
                    })
                  }
                />
                <ToggleField
                  label="Flip V"
                  checked={config.camera.flip_vertical}
                  onChange={(checked) =>
                    onChange({
                      ...config,
                      camera: { ...config.camera, flip_vertical: checked },
                    })
                  }
                />
              </div>
            </div>
          </div>
        </ConfigSection>

        <ConfigSection title="Model" detail="เครื่องนับและไฟล์โมเดล">
        <EngineSelector
          value={config.model.engine}
          onChange={(engine) =>
            onChange({ ...config, model: { ...config.model, engine } })
          }
        />
        <ModelSlotField
          config={config}
          onChange={(model) => onChange({ ...config, model })}
        />
        <ModelFileManager
          config={config}
          onChange={(model) => onChange({ ...config, model })}
        />
        <StepperField
          label="Confidence"
          value={config.model.confidence_threshold}
          min={0.1}
          max={0.95}
          smallStep={0.01}
          largeStep={0.05}
          precision={2}
          onChange={(value) =>
            onChange({
              ...config,
              model: { ...config.model, confidence_threshold: value },
            })
          }
        />
        </ConfigSection>
      </div>

      <div className="grid content-start gap-5">
        <ConfigSection title="GPIO" detail="ขาเซนเซอร์และ relay">
          <PinSelector
            label="Tray sensor GPIO"
            value={config.gpio.tray_sensor_pin}
            onChange={(value) =>
              onChange({
                ...config,
                gpio: { ...config.gpio, tray_sensor_pin: value },
              })
            }
          />
          <PinSelector
            label="Relay GPIO"
            value={config.gpio.relay_pin}
            onChange={(value) =>
              onChange({ ...config, gpio: { ...config.gpio, relay_pin: value } })
            }
          />
          <StepperField
            label="Debounce ms"
            value={config.gpio.debounce_ms}
            unit="ms"
            min={0}
            max={1000}
            smallStep={5}
            largeStep={25}
            onChange={(value) =>
              onChange({
                ...config,
                gpio: { ...config.gpio, debounce_ms: value },
              })
            }
          />
          <ToggleField
            label="Active low"
            checked={config.gpio.active_low}
            onChange={(checked) =>
              onChange({
                ...config,
                gpio: { ...config.gpio, active_low: checked },
              })
            }
          />
        </ConfigSection>

        <ConfigSection title="Counting" detail="จังหวะยืนยันผลนับ">
          <StepperField
            label="Stable frames"
            value={config.counting.stable_frames}
            min={1}
            max={30}
            smallStep={1}
            largeStep={5}
            onChange={(value) =>
              onChange({
                ...config,
                counting: { ...config.counting, stable_frames: value },
              })
            }
          />
          <StepperField
            label="Timeout ms"
            value={config.counting.timeout_ms}
            unit="ms"
            min={500}
            max={20000}
            smallStep={100}
            largeStep={500}
            onChange={(value) =>
              onChange({
                ...config,
                counting: { ...config.counting, timeout_ms: value },
              })
            }
          />
          <ToggleField
            label="Force safe mode"
            checked={config.safe_mode}
            onChange={(checked) => onChange({ ...config, safe_mode: checked })}
          />
        </ConfigSection>
      </div>
    </div>
  );
}

function TestTab({
  isBusy,
  onLightTest,
  onCountTest,
  onTrayTest,
}: {
  isBusy: boolean;
  onLightTest: (lightOn: boolean) => Promise<void>;
  onCountTest: () => Promise<void>;
  onTrayTest: (present: boolean) => Promise<void>;
}) {
  return (
    <div className="grid grid-cols-3 gap-5">
      <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)] p-4">
        <h3 className="mb-4 flex min-h-10 items-center gap-2 border-b border-[var(--machine-line)] pb-3 text-[11px] font-black uppercase tracking-[0.22em] text-[var(--machine-muted)]">
          <Zap className="h-4 w-4" />
          Relay
        </h3>
        <div className="grid gap-3">
          <button
            type="button"
            disabled={isBusy}
            onClick={() => void onLightTest(true)}
            className="min-h-14 rounded-[0.2rem] bg-[var(--machine-accent)] px-5 text-base font-black text-[var(--machine-ink)] disabled:opacity-50"
          >
            เปิดไฟ
          </button>
          <button
            type="button"
            disabled={isBusy}
            onClick={() => void onLightTest(false)}
            className="min-h-14 rounded-[0.2rem] bg-[var(--machine-ink)] px-5 text-base font-black text-[var(--machine-light)] disabled:opacity-50"
          >
            ปิดไฟ
          </button>
        </div>
      </section>

      <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)] p-4">
        <h3 className="mb-4 flex min-h-10 items-center gap-2 border-b border-[var(--machine-line)] pb-3 text-[11px] font-black uppercase tracking-[0.22em] text-[var(--machine-muted)]">
          <Box className="h-4 w-4" />
          Tray
        </h3>
        <div className="grid gap-3">
          <button
            type="button"
            disabled={isBusy}
            onClick={() => void onTrayTest(true)}
            className="min-h-14 rounded-[0.2rem] bg-[var(--machine-accent)] px-5 text-base font-black text-[var(--machine-ink)] disabled:opacity-50"
          >
            วางถาด
          </button>
          <button
            type="button"
            disabled={isBusy}
            onClick={() => void onTrayTest(false)}
            className="min-h-14 rounded-[0.2rem] bg-[var(--machine-ink)] px-5 text-base font-black text-[var(--machine-light)] disabled:opacity-50"
          >
            ถอดถาด
          </button>
        </div>
      </section>

      <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)] p-4">
        <h3 className="mb-4 flex min-h-10 items-center gap-2 border-b border-[var(--machine-line)] pb-3 text-[11px] font-black uppercase tracking-[0.22em] text-[var(--machine-muted)]">
          <Camera className="h-4 w-4" />
          Count
        </h3>
        <button
          type="button"
          disabled={isBusy}
          onClick={() => void onCountTest()}
          className="min-h-14 w-full rounded-[0.2rem] bg-[var(--machine-ink)] px-5 text-base font-black text-[var(--machine-light)] disabled:opacity-50"
        >
          ทดสอบนับ
        </button>
      </section>
    </div>
  );
}

function TabButton({
  active,
  icon,
  label,
  detail,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-16 items-center gap-3 rounded-[0.2rem] border px-3 text-left transition-colors duration-100 ${
        active
          ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
          : "border-transparent text-[var(--machine-muted)] hover:border-[var(--machine-line)] hover:bg-[var(--machine-panel)] hover:text-[var(--machine-ink)]"
      }`}
    >
      {icon}
      <span className="min-w-0">
        <span className="block text-sm font-black leading-tight">{label}</span>
        <span className="mt-1 block truncate text-xs font-bold leading-tight opacity-75">
          {detail}
        </span>
      </span>
    </button>
  );
}

function MetricCell({
  label,
  value,
  last,
}: {
  label: string;
  value: string;
  last?: boolean;
}) {
  return (
    <div
      className={`px-4 py-3 ${last ? "" : "border-r border-[var(--machine-line)]"}`}
    >
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--machine-muted)]">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  );
}

const GPIO_PIN_OPTIONS = [
  5, 6, 12, 13, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27,
];

const PREVIEW_QUALITY_OPTIONS = [
  { label: "เบาเครื่อง", width: 720, height: 720 },
  { label: "คมชัด", width: 1080, height: 1080 },
];

const MODEL_SLOTS = [
  {
    label: "Mock Model",
    detail: "Dev / safe mode",
    engine: "mock",
    model_path: "",
    hef_path: "",
    labels_path: "",
  },
  {
    label: "ONNX Production",
    detail: "/var/lib/nut-counter/models/production/model.onnx",
    engine: "onnx",
    model_path: "/var/lib/nut-counter/models/production/model.onnx",
    hef_path: "",
    labels_path: "/var/lib/nut-counter/models/production/labels.txt",
  },
  {
    label: "ONNX Test",
    detail: "/var/lib/nut-counter/models/test/model.onnx",
    engine: "onnx",
    model_path: "/var/lib/nut-counter/models/test/model.onnx",
    hef_path: "",
    labels_path: "/var/lib/nut-counter/models/test/labels.txt",
  },
  {
    label: "YOLO11N Production",
    detail: "/var/lib/nut-counter/models/production",
    engine: "hailo",
    model_path: "",
    hef_path: "/var/lib/nut-counter/models/production/model.hef",
    labels_path: "/var/lib/nut-counter/models/production/labels.txt",
  },
  {
    label: "YOLO11N Test",
    detail: "/var/lib/nut-counter/models/test",
    engine: "hailo",
    model_path: "",
    hef_path: "/var/lib/nut-counter/models/test/model.hef",
    labels_path: "/var/lib/nut-counter/models/test/labels.txt",
  },
];

function ConfigSection({
  title,
  detail,
  children,
}: {
  title: string;
  detail: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[0.2rem] border border-[var(--machine-line)] bg-[var(--machine-light)]">
      <header className="border-b border-[var(--machine-line)] px-4 py-3">
        <h3 className="text-[11px] font-black uppercase tracking-[0.22em] text-[var(--machine-muted)]">
          {title}
        </h3>
        <div className="mt-1 text-sm font-bold text-[var(--machine-ink)]">
          {detail}
        </div>
      </header>
      <div className="grid gap-4 p-4">{children}</div>
    </section>
  );
}

function PinSelector({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const options = GPIO_PIN_OPTIONS.includes(value)
    ? GPIO_PIN_OPTIONS
    : [value, ...GPIO_PIN_OPTIONS];

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3 text-sm font-semibold text-[var(--machine-muted)]">
        <span>{label}</span>
        <span className="font-mono text-base font-bold text-[var(--machine-ink)]">
          GPIO {value}
        </span>
      </div>
      <div className="grid grid-cols-5 gap-2">
        {options.map((pin) => (
          <button
            key={pin}
            type="button"
            onClick={() => onChange(pin)}
            className={`h-11 rounded-[0.15rem] border text-sm font-bold ${
              pin === value
                ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                : "border-[var(--machine-line)] bg-[var(--machine-panel)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-strong)]"
            }`}
          >
            {pin}
          </button>
        ))}
      </div>
    </div>
  );
}

function CameraSourceField({
  value,
  device,
  onChange,
}: {
  value: AppConfig["camera"]["source"];
  device: string;
  onChange: (source: AppConfig["camera"]["source"], device: string) => void;
}) {
  const [sources, setSources] = useState<CameraSource[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState("");

  async function scan() {
    setIsScanning(true);
    setScanError("");
    try {
      setSources(await fetchCameraSources());
    } catch (caught) {
      setScanError(caught instanceof Error ? caught.message : "สแกนกล้องไม่สำเร็จ");
    } finally {
      setIsScanning(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void scan(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const activeId = device ? `${value}:${device}` : value;

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3 text-sm font-semibold text-[var(--machine-muted)]">
        <span>Camera source</span>
        <button
          type="button"
          onClick={() => void scan()}
          disabled={isScanning}
          className="rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel-strong)] px-3 py-1.5 text-xs font-black text-[var(--machine-ink)] disabled:opacity-50"
        >
          {isScanning ? "กำลังสแกน" : "สแกน"}
        </button>
      </div>
      {scanError && (
        <div className="rounded-[0.15rem] border border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-3 py-2 text-xs font-bold text-[var(--machine-danger)]">
          {scanError}
        </div>
      )}
      <div className="grid gap-2">
        {sources.map((source) => {
          const sourceId = source.device ? `${source.source}:${source.device}` : source.source;
          const active = sourceId === activeId;
          return (
            <button
              key={source.id}
              type="button"
              disabled={!source.available}
              onClick={() => onChange(source.source, source.device)}
              className={`min-h-14 rounded-[0.15rem] border px-3 py-2 text-left ${
                active
                  ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                  : "border-[var(--machine-line)] bg-[var(--machine-panel-strong)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-pressed)] disabled:opacity-45"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-black">{source.label}</div>
                <div className="font-mono text-[11px] font-bold uppercase">
                  {source.source}
                </div>
              </div>
              <div className="mt-1 truncate text-[11px] font-semibold leading-tight">
                {source.available ? source.detail : `${source.detail} / ไม่พร้อม`}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PreviewQualityField({
  width,
  height,
  onChange,
}: {
  width: number;
  height: number;
  onChange: (width: number, height: number) => void;
}) {
  const currentOption = PREVIEW_QUALITY_OPTIONS.find(
    (option) => option.width === width && option.height === height,
  );
  const currentLabel = currentOption?.label ?? `${width} x ${height}`;

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3 text-sm font-semibold text-[var(--machine-muted)]">
        <span>คุณภาพภาพพรีวิว</span>
        <span className="text-base font-bold text-[var(--machine-ink)]">
          {currentLabel}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {PREVIEW_QUALITY_OPTIONS.map((option) => {
          const active = option.width === width && option.height === height;
          return (
            <button
              key={`${option.width}x${option.height}`}
              type="button"
              onClick={() => onChange(option.width, option.height)}
              className={`min-h-14 rounded-[0.15rem] border px-3 py-2 text-left ${
                active
                  ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                  : "border-[var(--machine-line)] bg-[var(--machine-panel-strong)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-pressed)]"
              }`}
            >
              <div className="text-sm font-black">{option.label}</div>
              <div className="font-mono text-xs font-semibold">
                {option.width} x {option.height}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EngineSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (engine: string) => void;
}) {
  const engines = ["mock", "onnx", "hailo", "external"];

  return (
    <div className="grid gap-2">
      <div className="text-sm font-semibold text-[var(--machine-muted)]">
        Engine
      </div>
      <div className="grid grid-cols-4 gap-2">
        {engines.map((engine) => (
          <button
            key={engine}
            type="button"
            onClick={() => onChange(engine)}
            className={`h-12 rounded-[0.15rem] border text-sm font-bold capitalize ${
              value === engine
                ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                : "border-[var(--machine-line)] bg-[var(--machine-panel)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-strong)]"
            }`}
          >
            {engine}
          </button>
        ))}
      </div>
    </div>
  );
}

function ModelSlotField({
  config,
  onChange,
}: {
  config: AppConfig;
  onChange: (model: AppConfig["model"]) => void;
}) {
  const slots = getModelSlots(config);

  return (
    <div className="grid gap-2">
      <div className="text-sm font-semibold text-[var(--machine-muted)]">
        Model slot
      </div>
      <div className="grid gap-2">
        {slots.map((slot) => {
          const active =
            config.model.engine === slot.engine &&
            config.model.model_path === slot.model_path &&
            config.model.hef_path === slot.hef_path &&
            config.model.labels_path === slot.labels_path;

          return (
            <button
              key={`${slot.engine}:${slot.model_path}:${slot.hef_path}:${slot.labels_path}`}
              type="button"
              onClick={() =>
                onChange({
                  ...config.model,
                  engine: slot.engine,
                  model_path: slot.model_path,
                  hef_path: slot.hef_path,
                  labels_path: slot.labels_path,
                })
              }
              className={`min-h-14 rounded-[0.15rem] border px-3 py-2 text-left ${
                active
                  ? "border-[var(--machine-accent-pressed)] bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                  : "border-[var(--machine-line)] bg-[var(--machine-panel)] text-[var(--machine-muted)] hover:bg-[var(--machine-panel-strong)]"
              }`}
            >
              <div className="text-sm font-black">{slot.label}</div>
              <div className="truncate font-mono text-[11px] font-semibold">
                {slot.detail}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

type PickerKind = "model" | "labels";

function ModelFileManager({
  config,
  onChange,
}: {
  config: AppConfig;
  onChange: (model: AppConfig["model"]) => void;
}) {
  const [picker, setPicker] = useState<PickerKind | null>(null);
  const [browser, setBrowser] = useState<FileBrowserResult | null>(null);
  const [browserError, setBrowserError] = useState("");
  const [isBrowsing, setIsBrowsing] = useState(false);
  const [validation, setValidation] = useState<ModelValidationResult | null>(null);
  const [validationError, setValidationError] = useState("");
  const [isValidating, setIsValidating] = useState(false);

  const modelPath = config.model.engine === "onnx"
    ? config.model.model_path
    : config.model.hef_path;

  async function openPicker(kind: PickerKind, path: string) {
    setPicker(kind);
    await loadPath(kind, path);
  }

  async function loadPath(kind: PickerKind, path: string) {
    setIsBrowsing(true);
    setBrowserError("");
    try {
      setBrowser(await browseFiles(path, kind));
    } catch (caught) {
      setBrowserError(caught instanceof Error ? caught.message : "เปิดรายการไฟล์ไม่ได้");
    } finally {
      setIsBrowsing(false);
    }
  }

  function selectFile(path: string) {
    if (picker === "labels") {
      onChange({ ...config.model, labels_path: path });
    } else if (path.toLowerCase().endsWith(".onnx")) {
      onChange({ ...config.model, engine: "onnx", model_path: path, hef_path: "" });
    } else if (path.toLowerCase().endsWith(".hef")) {
      onChange({ ...config.model, engine: "hailo", model_path: "", hef_path: path });
    } else {
      onChange({ ...config.model, model_path: path });
    }
    setValidation(null);
    setValidationError("");
    setPicker(null);
  }

  async function runValidation() {
    setIsValidating(true);
    setValidationError("");
    try {
      setValidation(await validateModel(config.model));
    } catch (caught) {
      setValidationError(caught instanceof Error ? caught.message : "ตรวจโมเดลไม่สำเร็จ");
    } finally {
      setIsValidating(false);
    }
  }

  return (
    <div className="grid gap-3">
      <PathField
        label="ไฟล์โมเดล"
        value={modelPath}
        onBrowse={() => void openPicker("model", modelPath)}
      />
      <PathField
        label="ไฟล์ labels"
        value={config.model.labels_path}
        onBrowse={() => void openPicker("labels", config.model.labels_path)}
      />

      {picker && (
        <div className="rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel-strong)]">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--machine-line)] px-3 py-2">
            <div className="min-w-0">
              <div className="text-xs font-black text-[var(--machine-ink)]">
                {picker === "model" ? "เลือกไฟล์โมเดล" : "เลือกไฟล์ labels"}
              </div>
              <div className="truncate font-mono text-[11px] font-semibold text-[var(--machine-muted)]">
                {browser?.path ?? ""}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setPicker(null)}
              className="h-9 rounded-[0.15rem] border border-[var(--machine-line)] px-3 text-xs font-bold text-[var(--machine-muted)] hover:bg-[var(--machine-panel-pressed)]"
            >
              ปิด
            </button>
          </div>

          <div className="flex flex-wrap gap-2 border-b border-[var(--machine-line)] px-3 py-2">
            {browser?.roots.map((root) => (
              <button
                key={root.path}
                type="button"
                onClick={() => void loadPath(picker, root.path)}
                className="rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] px-3 py-1.5 text-xs font-bold text-[var(--machine-ink)]"
              >
                {root.label}
              </button>
            ))}
            {browser?.parent && (
              <button
                type="button"
                onClick={() => void loadPath(picker, browser.parent)}
                className="rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] px-3 py-1.5 text-xs font-bold text-[var(--machine-ink)]"
              >
                ขึ้นหนึ่งชั้น
              </button>
            )}
          </div>

          <div className="max-h-56 overflow-auto p-2">
            {isBrowsing && (
              <div className="flex items-center gap-2 px-2 py-3 text-sm font-bold text-[var(--machine-muted)]">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                กำลังอ่านไฟล์
              </div>
            )}
            {browserError && (
              <div className="rounded-[0.15rem] border border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-3 py-2 text-xs font-bold text-[var(--machine-danger)]">
                {browserError}
              </div>
            )}
            {!isBrowsing && browser?.entries.length === 0 && (
              <div className="px-2 py-3 text-sm font-bold text-[var(--machine-muted)]">
                ไม่พบไฟล์ที่เลือกได้
              </div>
            )}
            {browser?.entries.map((entry) => (
              <button
                key={entry.path}
                type="button"
                onClick={() =>
                  entry.type === "directory"
                    ? void loadPath(picker, entry.path)
                    : selectFile(entry.path)
                }
                className="flex min-h-11 w-full items-center gap-3 rounded-[0.15rem] px-2 text-left hover:bg-[var(--machine-panel-pressed)]"
              >
                {entry.type === "directory" ? (
                  <FolderOpen className="h-4 w-4 shrink-0 text-[var(--machine-muted)]" />
                ) : (
                  <File className="h-4 w-4 shrink-0 text-[var(--machine-muted)]" />
                )}
                <span className="min-w-0 flex-1 truncate text-sm font-bold text-[var(--machine-ink)]">
                  {entry.name}
                </span>
                {entry.type === "file" && (
                  <span className="font-mono text-[11px] font-semibold text-[var(--machine-muted)]">
                    {formatBytes(entry.size)}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => void runValidation()}
          disabled={isValidating}
          className="flex h-11 items-center gap-2 rounded-[0.15rem] bg-[var(--machine-ink)] px-4 text-sm font-bold text-[var(--machine-light)] disabled:opacity-50"
        >
          {isValidating ? (
            <LoaderCircle className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          ตรวจโมเดล
        </button>
        {validation && (
          <span className={`text-sm font-black ${validation.ok ? "text-[#476119]" : "text-[var(--machine-danger)]"}`}>
            {validation.ok ? "พร้อมใช้" : "ยังไม่พร้อม"}
          </span>
        )}
      </div>

      {validationError && (
        <div className="rounded-[0.15rem] border border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-3 py-2 text-xs font-bold text-[var(--machine-danger)]">
          {validationError}
        </div>
      )}
      {validation && (
        <div className="grid gap-2">
          {validation.checks.map((check) => (
            <div
              key={check.key}
              className="grid grid-cols-[1.5rem_8rem_1fr] items-start gap-2 rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] px-3 py-2"
            >
              <ValidationIcon status={check.status} />
              <div className="text-xs font-black text-[var(--machine-ink)]">
                {check.label}
              </div>
              <div className="min-w-0 break-words font-mono text-[11px] font-semibold text-[var(--machine-muted)]">
                {check.detail}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PathField({
  label,
  value,
  onBrowse,
}: {
  label: string;
  value: string;
  onBrowse: () => void;
}) {
  return (
    <div className="grid gap-2">
      <div className="text-sm font-semibold text-[var(--machine-muted)]">
        {label}
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <div className="min-h-11 truncate rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-light)] px-3 py-2.5 font-mono text-xs font-bold text-[var(--machine-ink)]">
          {value || "ยังไม่ได้เลือกไฟล์"}
        </div>
        <button
          type="button"
          onClick={onBrowse}
          className="flex h-11 items-center gap-2 rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] px-4 text-sm font-bold text-[var(--machine-ink)] hover:bg-[var(--machine-panel-strong)]"
        >
          <FolderOpen className="h-4 w-4" />
          เลือก
        </button>
      </div>
    </div>
  );
}

function ValidationIcon({ status }: { status: "ok" | "warn" | "error" }) {
  if (status === "ok") {
    return <CheckCircle2 className="h-4 w-4 text-[#476119]" />;
  }
  if (status === "warn") {
    return <TriangleAlert className="h-4 w-4 text-[oklch(0.53_0.11_78)]" />;
  }
  return <XCircle className="h-4 w-4 text-[var(--machine-danger)]" />;
}

function formatBytes(size: number | null) {
  if (size === null) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function StepperField({
  label,
  value,
  unit,
  min,
  max,
  smallStep,
  largeStep,
  precision = 0,
  onChange,
}: {
  label: string;
  value: number;
  unit?: string;
  min: number;
  max: number;
  smallStep: number;
  largeStep: number;
  precision?: number;
  onChange: (value: number) => void;
}) {
  const formattedValue = value.toFixed(precision);
  const update = (delta: number) => {
    onChange(clampNumber(roundNumber(value + delta, precision), min, max));
  };

  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between gap-3 text-sm font-semibold text-[var(--machine-muted)]">
        <span>{label}</span>
        <span className="font-mono text-base font-bold text-[var(--machine-ink)]">
          {formattedValue}
          {unit ? ` ${unit}` : ""}
        </span>
      </div>
      <div className="grid grid-cols-[1fr_1fr_1.4fr_1fr_1fr] gap-2">
        <StepperButton
          label={`-${largeStep}`}
          onClick={() => update(-largeStep)}
        />
        <StepperButton
          label={`-${smallStep}`}
          onClick={() => update(-smallStep)}
        />
        <div className="flex h-11 items-center justify-center rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-light)] font-mono text-base font-black text-[var(--machine-ink)]">
          {formattedValue}
        </div>
        <StepperButton
          label={`+${smallStep}`}
          onClick={() => update(smallStep)}
        />
        <StepperButton
          label={`+${largeStep}`}
          onClick={() => update(largeStep)}
        />
      </div>
    </div>
  );
}

function StepperButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-11 rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] font-mono text-sm font-black text-[var(--machine-ink)] hover:bg-[var(--machine-panel-strong)] active:bg-[var(--machine-panel-pressed)]"
    >
      {label}
    </button>
  );
}

function getModelSlots(config: AppConfig) {
  const currentSlot = {
    label: "Current custom",
    detail: config.model.model_path || config.model.hef_path || "No model path",
    engine: config.model.engine,
    model_path: config.model.model_path,
    hef_path: config.model.hef_path,
    labels_path: config.model.labels_path,
  };
  const known = MODEL_SLOTS.some(
    (slot) =>
      slot.engine === currentSlot.engine &&
      slot.model_path === currentSlot.model_path &&
      slot.hef_path === currentSlot.hef_path &&
      slot.labels_path === currentSlot.labels_path,
  );

  return known ? MODEL_SLOTS : [currentSlot, ...MODEL_SLOTS];
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function roundNumber(value: number, precision: number) {
  const multiplier = 10 ** precision;
  return Math.round(value * multiplier) / multiplier;
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-[0.15rem] border border-[var(--machine-line)] bg-[var(--machine-panel-strong)] px-3 py-2 text-sm font-bold text-[var(--machine-muted)]">
      {label}
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-5 accent-[var(--machine-accent)]"
      />
    </label>
  );
}
