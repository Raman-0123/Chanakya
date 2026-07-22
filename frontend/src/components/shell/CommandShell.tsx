import type { ReactNode } from "react";
import { NavRail } from "./NavRail";
import { StatusBar } from "./StatusBar";
import { NesiSync } from "./NesiSync";

/** The persistent command-center chrome wrapping every room. */
export function CommandShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-void">
      <NesiSync />
      <NavRail />
      <div className="flex min-w-0 flex-1 flex-col">
        <StatusBar />
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
