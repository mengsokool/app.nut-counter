import {
  AlertTriangle,
  Box,
  KeyRound,
  LoaderCircle,
  Power,
  Settings,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  type SystemStatus,
  fetchStatus,
  powerOff,
  selectPartType,
} from "../../api/client";
import { FASTENER_TYPES } from "../../domain/fasteners";
import OperatorPanel from "../operator/OperatorPanel";
import CameraFeed from "./CameraFeed";

export default function KioskPage({ isLoading }: { isLoading: boolean }) {
  const [selectedFastenerId, setSelectedFastenerId] = useState(
    FASTENER_TYPES[0]?.id ?? "",
  );
  const [isPoweringOff, setIsPoweringOff] = useState(false);
  const [showConfirmShutdown, setShowConfirmShutdown] = useState(false);
  const [showPasswordPrompt, setShowPasswordPrompt] = useState(false);
  const [showOperatorPanel, setShowOperatorPanel] = useState(false);
  const [password, setPassword] = useState("");
  const [powerError, setPowerError] = useState("");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [displayCount, setDisplayCount] = useState("000");
  const [partTypeError, setPartTypeError] = useState("");

  const selectedFastener = useMemo(
    () =>
      FASTENER_TYPES.find((item) => item.id === selectedFastenerId) ??
      FASTENER_TYPES[0],
    [selectedFastenerId],
  );

  useEffect(() => {
    let es: EventSource | null = null;
    let errorTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let probeTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectDelay = 500;
    let probeDelay = 500;
    let isMounted = true;

    function applyStatus(status: SystemStatus) {
      if (!isMounted) return;
      if (errorTimer) {
        clearTimeout(errorTimer);
        errorTimer = null;
      }
      reconnectDelay = 500;
      probeDelay = 500;
      setSystemStatus(status);
      setDisplayCount(status.count.toString().padStart(3, "0"));
      if (FASTENER_TYPES.some((item) => item.id === status.selectedPartType)) {
        setSelectedFastenerId(status.selectedPartType);
      }
    }

    function markMissingSoon() {
      if (errorTimer) return;
      errorTimer = setTimeout(() => {
        if (!isMounted) return;
        setSystemStatus(null);
        setDisplayCount("000");
      }, 5000);
    }

    function scheduleReconnect() {
      if (reconnectTimer || !isMounted) return;
      const delay = reconnectDelay;
      reconnectDelay = Math.min(reconnectDelay * 2, 5000);
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectEvents();
      }, delay);
    }

    function scheduleProbe() {
      if (probeTimer || !isMounted) return;
      const delay = probeDelay;
      probeDelay = Math.min(probeDelay * 2, 5000);
      probeTimer = setTimeout(() => {
        probeTimer = null;
        void probeStatus();
      }, delay);
    }

    function connectEvents() {
      es?.close();
      es = new EventSource("/api/events");

      es.onopen = () => {
        reconnectDelay = 500;
      };

      es.onmessage = (e) => {
        try {
          applyStatus(JSON.parse(e.data as string) as SystemStatus);
        } catch {
          // ignore malformed event
        }
      };

      es.onerror = () => {
        markMissingSoon();
        es?.close();
        es = null;
        scheduleReconnect();
        scheduleProbe();
      };
    }

    async function probeStatus() {
      try {
        applyStatus(await fetchStatus());
        scheduleReconnect();
      } catch {
        markMissingSoon();
        scheduleProbe();
      }
    }

    connectEvents();

    return () => {
      isMounted = false;
      es?.close();
      if (errorTimer) clearTimeout(errorTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (probeTimer) clearTimeout(probeTimer);
    };
  }, []);

  const handlePowerOff = async (pwd?: string) => {
    setIsPoweringOff(true);
    setPowerError("");

    const result = await powerOff(pwd);

    if (result.success) {
      setShowPasswordPrompt(false);
      setShowConfirmShutdown(false);
      return;
    }

    if ("needsAuth" in result && result.needsAuth) {
      setShowPasswordPrompt(true);
      setShowConfirmShutdown(false);
      setIsPoweringOff(false);
      return;
    }

    setPowerError(
      "error" in result ? result.error : "เกิดข้อผิดพลาดในการปิดเครื่อง",
    );
    setIsPoweringOff(false);
  };

  const handleSelectFastener = async (partType: string) => {
    const previous = selectedFastenerId;
    setSelectedFastenerId(partType);
    setPartTypeError("");
    try {
      const status = await selectPartType(partType);
      setSystemStatus(status);
      setDisplayCount(status.count.toString().padStart(3, "0"));
    } catch (caught) {
      setSelectedFastenerId(previous);
      setPartTypeError(
        caught instanceof Error ? caught.message : "เปลี่ยนชนิดชิ้นงานไม่สำเร็จ",
      );
    }
  };

  const hasFault =
    systemStatus === null ||
    systemStatus.safeMode ||
    systemStatus.camera === "error" ||
    systemStatus.camera === "missing" ||
    systemStatus.gpio === "error" ||
    systemStatus.gpio === "missing" ||
    systemStatus.model === "error" ||
    systemStatus.model === "missing";
  const displayState = hasFault
    ? "error"
    : systemStatus.trayPresent
      ? "complete"
      : "waiting";
  const displayTitle =
    displayState === "error"
      ? "เครื่องขัดข้อง"
      : displayState === "waiting"
        ? "พร้อมนับ"
        : "นับได้";
  const displaySubtitle =
    displayState === "error"
      ? getFaultMessage(systemStatus)
      : displayState === "waiting"
        ? (selectedFastener?.name ?? "")
        : "ชิ้น";

  return (
    <>
      <main
        className={`relative h-svh w-screen select-none overflow-hidden bg-[var(--machine-shell)] text-[var(--machine-ink)] grid transition-all ${isLoading ? "opacity-0" : "animate-fade-in opacity-100"}`}
        style={{
          gridTemplateColumns:
            "minmax(12rem, 1fr) min(100svh, calc(100vw - 24rem)) minmax(12rem, 1fr)",
        }}
      >
        <aside className="flex min-w-0 flex-col border-r border-[var(--machine-line)] bg-[var(--machine-panel)]">
          <header className="flex h-16 items-center border-b border-[var(--machine-line)] px-4">
            <div className="flex items-center gap-2 text-xs font-bold uppercase text-[var(--machine-muted)]">
              <Box className="h-4 w-4" />
              <h1>ชนิดชิ้นงาน</h1>
            </div>
          </header>
          {partTypeError && (
            <div className="border-b border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-4 py-2 text-xs font-bold text-[var(--machine-danger)]">
              {partTypeError}
            </div>
          )}

          <div
            className="grid flex-1"
            style={{
              gridTemplateRows: `repeat(${FASTENER_TYPES.length}, minmax(0, 1fr))`,
            }}
          >
            {FASTENER_TYPES.map((item) => {
              const isActive = item.id === selectedFastenerId;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => void handleSelectFastener(item.id)}
                  aria-pressed={isActive}
                  className={`grid min-h-0 grid-rows-[1fr_auto] border-b border-[var(--machine-line)] px-4 py-5 text-left outline-none transition-colors duration-150 focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-[var(--machine-accent)] ${
                    isActive
                      ? "bg-[var(--machine-accent)] text-[var(--machine-ink)]"
                      : "bg-[var(--machine-panel)] text-[var(--machine-ink)] hover:bg-[var(--machine-panel-strong)] active:bg-[var(--machine-panel-pressed)]"
                  }`}
                >
                  <div
                    className={`relative mx-auto aspect-square w-full max-w-[9.5rem] ${
                      isActive ? "opacity-100" : "opacity-85"
                    }`}
                  >
                    <img
                      src={item.image}
                      alt=""
                      sizes="(max-width: 1024px) 8rem, 9rem"
                      className={`h-full w-full object-contain ${
                        isActive ? "" : "mix-blend-multiply"
                      }`}
                    />
                  </div>

                  <span className="text-center text-lg font-bold leading-tight text-[var(--machine-ink)]">
                    {item.name}
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="min-w-0 bg-[var(--machine-dark)]">
          <div className="relative h-svh w-full overflow-hidden bg-[var(--machine-dark)]">
            <CameraFeed />
          </div>
        </section>

        <aside className="flex min-w-0 flex-col border-l border-[var(--machine-line)] bg-[var(--machine-panel)]">
          <header className="flex h-16 items-center justify-between border-b border-[var(--machine-line)] px-4">
            <span className="text-xs font-bold uppercase text-[var(--machine-muted)]">
              ผลนับ
            </span>
            <span className="truncate text-sm font-semibold text-[var(--machine-ink)]">
              {selectedFastener?.name ?? ""}
            </span>
          </header>

          <div
            className={`flex flex-1 items-center justify-center px-3 text-center transition-colors duration-300 ${
              displayState === "error"
                ? "bg-[var(--machine-danger)]"
                : "bg-[var(--machine-display)]"
            }`}
          >
            <div
              key={displayState}
              className="animate-fade-in flex w-full flex-col items-center justify-center"
            >
              <span
                className={`text-[18px] font-semibold uppercase tracking-[0.1em] ${
                  displayState === "error"
                    ? "text-[var(--machine-danger-soft)]"
                    : "text-[var(--machine-display-label)]"
                }`}
              >
                {displayTitle}
              </span>

              {displayState === "complete" && (
                <div
                  key={displayCount}
                  className="animate-count-stamp text-[clamp(5rem,11vw,8rem)] font-semibold leading-none text-[var(--machine-display-accent)] tabular-nums"
                  aria-live="polite"
                  style={{ fontFamily: "var(--font-machine-mono)" }}
                >
                  {displayCount}
                </div>
              )}

              {displayState === "waiting" && (
                <div className="max-w-[11rem] py-4 text-[clamp(3rem,5.5vw,4.6rem)] font-black leading-[0.95] text-[var(--machine-display-accent)]">
                  วางถาด
                </div>
              )}

              {displayState === "error" && (
                <div className="max-w-[12rem] py-5 text-[clamp(2rem,4.2vw,3.25rem)] font-black leading-tight text-[var(--machine-light)]">
                  ตรวจเครื่อง
                </div>
              )}

              <span
                className={`text-[18px] font-semibold uppercase tracking-[0.1em] ${
                  displayState === "error"
                    ? "text-[var(--machine-danger-soft)]"
                    : "text-[var(--machine-display-label)]"
                }`}
              >
                {displaySubtitle}
              </span>
            </div>
          </div>

          <div className="grid h-[5.5rem] grid-cols-2 border-t border-[var(--machine-line)] bg-[var(--machine-panel-strong)] text-[var(--machine-ink)]">
            <button
              type="button"
              onClick={() => setShowOperatorPanel(true)}
              className="flex h-full items-center justify-center gap-3 border-r border-[var(--machine-line)] outline-none transition-colors duration-100 hover:bg-[var(--machine-panel-pressed)] active:bg-[var(--machine-panel-pressed)] focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-[var(--machine-accent)]"
              aria-label="ตั้งค่าเครื่อง"
            >
              <Settings className="h-6 w-6" />
            </button>
            <button
              type="button"
              onClick={() => setShowConfirmShutdown(true)}
              disabled={isPoweringOff}
              aria-label="ปิดเครื่อง"
              className="flex items-center justify-center gap-3 outline-none transition-colors duration-100 hover:bg-[var(--machine-panel-pressed)] active:bg-[var(--machine-panel-pressed)] focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-[var(--machine-accent)] disabled:opacity-50"
            >
              {isPoweringOff ? (
                <LoaderCircle className="h-6 w-6 animate-spin text-[var(--machine-danger)]" />
              ) : (
                <Power
                  className="h-6 w-6 text-[var(--machine-danger)]"
                  aria-hidden="true"
                />
              )}
            </button>
          </div>
        </aside>

        {isPoweringOff && !showPasswordPrompt && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/80 text-white backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4">
              <LoaderCircle className="h-12 w-12 animate-spin text-white/70" />
              <div className="text-[11px] font-semibold uppercase tracking-[0.32em] text-white/55">
                system
              </div>
              <div className="text-2xl font-bold">กำลังปิดเครื่อง...</div>
            </div>
          </div>
        )}
      </main>

      {showConfirmShutdown && (
        <div className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-5 backdrop-blur-sm">
          <div className="animate-dialog-pop w-full max-w-sm overflow-hidden rounded-[1.25rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] shadow-2xl">
            <div className="flex items-center gap-3 border-b border-[var(--machine-line)] px-5 py-4 text-[var(--machine-danger)]">
              <AlertTriangle className="h-6 w-6" />
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[var(--machine-muted)]">
                  power
                </div>
                <h2 className="text-xl font-bold text-[var(--machine-ink)]">
                  ยืนยันปิดเครื่อง
                </h2>
              </div>
            </div>

            <div className="px-5 py-5">
              <p className="mb-5 text-[15px] leading-relaxed text-[var(--machine-muted)]">
                เครื่องจะหยุดทำงานทันทีหลังยืนยัน และต้องเปิดใหม่ด้วยตนเอง
              </p>

              {powerError && (
                <div className="mb-4 rounded-2xl border border-[#dfc0b6] bg-[var(--machine-danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--machine-danger)]">
                  {powerError}
                </div>
              )}

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowConfirmShutdown(false);
                    setPowerError("");
                  }}
                  disabled={isPoweringOff}
                  className="rounded-2xl px-5 py-2.5 text-sm font-bold text-[var(--machine-muted)] transition-colors hover:bg-black/5"
                >
                  ยกเลิก
                </button>

                <button
                  type="button"
                  onClick={() => handlePowerOff()}
                  disabled={isPoweringOff}
                  className="flex items-center gap-2 rounded-2xl bg-[var(--machine-danger)] px-5 py-2.5 text-sm font-bold text-white transition-opacity disabled:opacity-50"
                >
                  {isPoweringOff && (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  )}
                  ปิดเครื่อง
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showPasswordPrompt && (
        <div className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-5 backdrop-blur-sm">
          <div className="animate-dialog-pop w-full max-w-sm overflow-hidden rounded-[1.25rem] border border-[var(--machine-line)] bg-[var(--machine-panel)] shadow-2xl">
            <div className="flex items-center gap-3 border-b border-[var(--machine-line)] px-5 py-4 text-[var(--machine-ink)]">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black/5">
                <KeyRound className="h-5 w-5 text-[var(--machine-muted)]" />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[var(--machine-muted)]">
                  admin
                </div>
                <h2 className="text-lg font-bold">
                  ต้องการรหัสผ่านผู้ดูแลระบบ
                </h2>
              </div>
            </div>

            <form
              className="px-5 py-5"
              onSubmit={(event) => {
                event.preventDefault();
                void handlePowerOff(password);
              }}
            >
              <p className="mb-4 text-sm leading-relaxed text-[var(--machine-muted)]">
                ระบบนี้ต้องใช้รหัสผ่านระดับผู้ดูแลก่อนสั่งปิดเครื่อง
              </p>

              <input
                type="password"
                placeholder="รหัสผ่าน"
                autoComplete="off"
                autoSave="off"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoFocus
                className="mb-2 w-full rounded-2xl border border-[var(--machine-line)] bg-white px-4 py-3 text-[var(--machine-ink)] outline-none focus:border-[var(--machine-ink)]"
              />

              {powerError && (
                <div className="mb-3 text-xs font-semibold text-[var(--machine-danger)]">
                  {powerError}
                </div>
              )}

              <div className="mt-6 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowPasswordPrompt(false);
                    setPassword("");
                    setPowerError("");
                  }}
                  className="rounded-2xl px-4 py-2 text-sm font-bold text-[var(--machine-muted)] transition-colors hover:bg-black/5"
                >
                  ยกเลิก
                </button>

                <button
                  type="submit"
                  disabled={!password || isPoweringOff}
                  className="flex items-center gap-2 rounded-2xl bg-[var(--machine-ink)] px-4 py-2 text-sm font-bold text-white transition-opacity disabled:opacity-50"
                >
                  {isPoweringOff && (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  )}
                  ยืนยันปิดเครื่อง
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showOperatorPanel && (
        <OperatorPanel onClose={() => setShowOperatorPanel(false)} />
      )}
    </>
  );
}

function getFaultMessage(status: SystemStatus | null) {
  if (!status) return "ไม่พบ backend";
  if (status.safeMode) return "safe mode";
  if (status.camera === "error" || status.camera === "missing") {
    return "กล้องขัดข้อง";
  }
  if (status.gpio === "error" || status.gpio === "missing") {
    return "GPIO ขัดข้อง";
  }
  if (status.model === "error" || status.model === "missing") {
    return "โมเดลไม่พร้อม";
  }
  return "ตรวจเครื่อง";
}
