import { ROOMS } from "@/config/navigation";
import { RoomScaffold } from "@/components/shell/RoomScaffold";
import { IntelligenceRoom } from "@/components/intelligence/IntelligenceRoom";

const room = ROOMS.find((r) => r.id === "intelligence")!;

export default function IntelligencePage() {
  return (
    <RoomScaffold room={room}>
      <IntelligenceRoom />
    </RoomScaffold>
  );
}
