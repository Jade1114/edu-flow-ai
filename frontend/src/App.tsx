import { Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import { Toaster } from "sonner";

function App() {
  return (
    <>
      <Outlet />
      <Toaster />
      <TanStackRouterDevtools />
    </>
  );
}
export default App;
