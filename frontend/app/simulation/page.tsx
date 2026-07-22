"use client";

import { RoomPage } from "@/components/shell/RoomPage";
import { ScenarioControls } from "@/components/simulation/ScenarioControls";
import { ImpactReadout } from "@/components/simulation/ImpactReadout";
import { ROOMS } from "@/config/navigation";

const room = ROOMS.find((r) => r.id === "simulation")!;

export default function Page() {
  return (
    <RoomPage room={room}>
      <div className="grid h-full grid-cols-1 gap-3 overflow-hidden p-4 blueprint lg:grid-cols-[360px_1fr]">
        <div className="min-h-0">
          <ScenarioControls />
        </div>
        <div className="min-h-0 overflow-y-auto">
          <ImpactReadout />
        </div>
      </div>
    </RoomPage>
  );
}
