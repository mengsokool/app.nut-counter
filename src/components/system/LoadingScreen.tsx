export default function LoadingScreen() {
  return (
    <div className="absolute inset-0 z-50 flex items-center bg-black justify-between py-16 flex-col h-svh">
      <div></div>
      <div className="space-y-16 w-full px-32">
        <img
          src="/logo.svg"
          alt="Logo"
          className="invert w-full max-w-2xl mx-auto"
          width={444}
          height={59}
        />
        <span className="loader"></span>
      </div>
      <div>
        <p className="text-sm font-semibold text-neutral-300 text-center">
          พัฒนาโดย
          <br />
          ทีมนักศึกษาวิทยาลัยเทคนิคสุรินทร์
        </p>
      </div>
    </div>
  );
}
