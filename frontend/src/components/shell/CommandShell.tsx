import type { ReactNode } from "react";
import { NavRail } from "./NavRail";
import { StatusBar } from "./StatusBar";
import { NesiSync } from "./NesiSync";

/** The persistent command-center chrome wrapping every room. */
export function CommandShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative h-screen w-screen overflow-hidden bg-canvas text-ink font-sans transition-colors duration-300">
      <NesiSync />
      
      {/* Background Layer: Full-screen Workspace (Map) */}
      <main className="absolute inset-0 z-0 overflow-hidden">
        {children}
      </main>

      {/* Foreground Layer: Floating UI Chrome */}
      <div className="pointer-events-none absolute inset-0 z-40 flex flex-col">
        <div className="pointer-events-auto">
          <StatusBar />
        </div>
        <div className="flex min-h-0 flex-1">
          <div className="pointer-events-auto">
            <NavRail />
          </div>
          {/* The rest of the screen allows pointer events to pass through to the map */}
        </div>
      </div>
    </div>
  );
}
