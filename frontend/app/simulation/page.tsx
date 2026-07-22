import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { ScenarioControls } from "@/components/simulation/ScenarioControls";
import { ImpactReadout } from "@/components/simulation/ImpactReadout";

const room = ROOMS.find((r) => r.id === "simulation")!;

export default function SimulationPage() {
  return (
    <RoomScaffold room={room}>
      <div className="grid h-full grid-cols-1 gap-3 overflow-hidden p-4 blueprint lg:grid-cols-[320px_1fr]">
        <ScenarioControls />
        <div className="min-h-0 overflow-hidden">
          <ImpactReadout />
        </div>
      </div>
    </RoomScaffold>
  );
}
