import { useEffect, useState } from "react";
import KioskPage from "./components/kiosk/KioskPage";

export default function App() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsLoading(false), 1);
    return () => window.clearTimeout(timer);
  }, []);

  return <KioskPage isLoading={isLoading} />;
}
