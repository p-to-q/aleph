import { createRoot } from "react-dom/client";
import { AlephConsole } from "./components/AlephConsole";
import { useAlephRun } from "./lib/useAlephRun";
import "./styles.css";

function App() {
  return <AlephConsole state={useAlephRun()} />;
}

createRoot(document.getElementById("root")!).render(<App />);
